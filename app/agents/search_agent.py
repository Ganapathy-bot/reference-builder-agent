"""Search authoritative sources and refuse to blindly accept the first title hit."""

from __future__ import annotations

import asyncio
from typing import Awaitable

from app.agents.reconciliation_agent import group_hits, reconcile
from app.agents.verification_agent import verify
from app.config import Settings
from app.models.metadata import CanonicalRecord, ParsedInput, SourceHit
from app.sources import crossref, datacite, openalex, openlibrary, publisher, pubmed
from app.utils.http import HttpClient, SourceError
from app.utils.similarity import score_title_match


class SearchOutcome:
    def __init__(self) -> None:
        self.candidates: list[CanonicalRecord] = []
        self.errors: list[dict] = []
        self.source_timings: list[dict] = []
        self.decision: str = "not_found"
        self.selected: CanonicalRecord | None = None
        self.warning: str | None = None


async def search(parsed: ParsedInput, client: HttpClient, settings: Settings) -> SearchOutcome:
    outcome = SearchOutcome()
    hits, timings, errors = await _collect(parsed, client, settings)
    outcome.source_timings = timings
    outcome.errors = errors
    groups = group_hits(hits)
    candidates: list[CanonicalRecord] = []
    for group in groups:
        try:
            record = verify(reconcile(group))
        except ValueError:
            continue
        if parsed.source_type == "title":
            record.match_score = score_title_match(parsed.source_value, record)
        else:
            record.match_score = 1.0
        candidates.append(record)
    if parsed.source_type == "title":
        candidates.sort(key=lambda record: (record.match_score, record.confidence), reverse=True)
    else:
        candidates.sort(key=lambda record: (record.confidence, len(record.sources_used)), reverse=True)
    outcome.candidates = candidates
    outcome.decision, outcome.selected, outcome.warning = decide_selection(
        candidates,
        parsed.source_type,
        settings,
    )
    return outcome


def decide_selection(
    candidates: list[CanonicalRecord],
    source_type: str,
    settings: Settings,
) -> tuple[str, CanonicalRecord | None, str | None]:
    if not candidates:
        return "not_found", None, None
    if source_type != "title":
        best = candidates[0]
        warning = None
        if best.confidence < settings.warn_threshold:
            warning = "The identifier resolved, but several bibliographic fields are incomplete."
        elif best.confidence < settings.auto_threshold:
            warning = "Review the record. Metadata confidence is below the automatic threshold."
        return "selected", best, warning

    top = candidates[0]
    second = candidates[1] if len(candidates) > 1 else None
    ambiguous = bool(
        second
        and second.match_score >= 0.55
        and (top.match_score - second.match_score) < settings.ambiguity_gap
    )
    if top.match_score < settings.min_match:
        return "not_found", None, "No bibliographic record was close enough to that title."
    if ambiguous or top.match_score < settings.warn_threshold:
        return "needs_confirmation", None, "More than one record could match. Choose the correct publication."
    if top.match_score < settings.auto_threshold:
        return (
            "selected",
            top,
            "The title match is plausible but below the automatic threshold. Review it before citing.",
        )
    return "selected", top, None


async def _collect(
    parsed: ParsedInput,
    client: HttpClient,
    settings: Settings,
) -> tuple[list[SourceHit], list[dict], list[dict]]:
    jobs: list[tuple[str, Awaitable]] = []
    if parsed.source_type == "doi":
        doi = parsed.source_value
        jobs = [
            ("crossref", crossref.fetch_doi(client, doi)),
            ("openalex", openalex.fetch_doi(client, doi, settings.mailto)),
            ("datacite", datacite.fetch_doi(client, doi)),
            ("pubmed", pubmed.fetch_doi(client, doi, settings.mailto)),
        ]
    elif parsed.source_type == "pmid":
        jobs = [("pubmed", pubmed.fetch_pmid(client, parsed.source_value, settings.mailto))]
    elif parsed.source_type == "isbn":
        jobs = [
            ("openlibrary", openlibrary.fetch_isbn(client, parsed.source_value)),
            ("crossref", crossref.search_isbn(client, parsed.source_value)),
        ]
    elif parsed.source_type == "url":
        jobs = [("publisher", publisher.fetch_url(client, parsed.source_value))]
    else:
        query = parsed.source_value
        jobs = [
            ("crossref", crossref.search_title(client, query)),
            ("openalex", openalex.search_title(client, query, settings.mailto)),
            ("pubmed", pubmed.search_title(client, query, settings.mailto)),
        ]
        if _looks_like_book(query):
            jobs.append(("openlibrary", openlibrary.search_title(client, query)))

    results = await asyncio.gather(*(_timed(name, job) for name, job in jobs))
    hits: list[SourceHit] = []
    timings: list[dict] = []
    errors: list[dict] = []
    follow_dois: list[str] = []
    for name, result, error, elapsed in results:
        timings.append({"source": name, "ms": elapsed, "ok": error is None})
        if error:
            errors.append({"source": name, "message": _public_error(error)})
            continue
        batch = _as_hits(result)
        hits.extend(batch)
        if parsed.source_type in {"pmid", "url", "isbn"}:
            for hit in batch:
                if hit.doi:
                    follow_dois.append(hit.doi)
    if follow_dois:
        doi = follow_dois[0]
        extra_jobs = []
        have = {hit.source for hit in hits}
        if "crossref" not in have:
            extra_jobs.append(("crossref", crossref.fetch_doi(client, doi)))
        if "openalex" not in have:
            extra_jobs.append(("openalex", openalex.fetch_doi(client, doi, settings.mailto)))
        if "datacite" not in have and parsed.source_type != "isbn":
            extra_jobs.append(("datacite", datacite.fetch_doi(client, doi)))
        if extra_jobs:
            extra = await asyncio.gather(*(_timed(name, job) for name, job in extra_jobs))
            for name, result, error, elapsed in extra:
                timings.append({"source": name, "ms": elapsed, "ok": error is None})
                if error:
                    errors.append({"source": name, "message": _public_error(error)})
                else:
                    hits.extend(_as_hits(result))
    return hits, timings, errors


def _as_hits(result: object) -> list[SourceHit]:
    if result is None:
        return []
    if isinstance(result, SourceHit):
        return [result]
    if isinstance(result, list):
        return [item for item in result if isinstance(item, SourceHit)]
    return []


async def _timed(name: str, job: Awaitable) -> tuple[str, object, str | None, int]:
    import time

    started = time.perf_counter()
    try:
        result = await job
        elapsed = int((time.perf_counter() - started) * 1000)
        return name, result, None, elapsed
    except (SourceError, Exception) as exc:
        elapsed = int((time.perf_counter() - started) * 1000)
        return name, None, str(exc), elapsed


def _public_error(message: str) -> str:
    text = message.strip() or "request failed"
    if len(text) > 180:
        return text[:177] + "..."
    return text


def _looks_like_book(query: str) -> bool:
    lowered = query.casefold()
    return "isbn" in lowered or "edition" in lowered
