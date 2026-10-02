"""PubMed E-utilities."""

from __future__ import annotations

import re

from app.models.metadata import SourceHit
from app.sources.mapping import as_text, clean_pages, looks_preprint, normalize_doi
from app.utils.authors import parse_pubmed_name
from app.utils.http import HttpClient

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


def _year_from_pubdate(value: str | None) -> tuple[int | None, int | None, int | None]:
    if not value:
        return None, None, None
    match = re.search(r"(1[5-9]\d{2}|20\d{2}|2100)", value)
    year = int(match.group(1)) if match else None
    return year, None, None


def summary_to_hit(uid: str, summary: dict, match_score: float = 1.0) -> SourceHit | None:
    if not isinstance(summary, dict) or summary.get("error"):
        return None
    title = as_text(summary.get("title"))
    if title and title.endswith("."):
        title = title[:-1]
    authors = []
    for entry in summary.get("authors") or []:
        parsed = parse_pubmed_name(str(entry.get("name") or ""))
        if parsed:
            authors.append(parsed)
    doi = None
    pmid = uid
    for article_id in summary.get("articleids") or []:
        id_type = str(article_id.get("idtype") or "").lower()
        value = as_text(article_id.get("value"))
        if id_type == "doi":
            doi = normalize_doi(value)
        elif id_type == "pubmed" and value:
            pmid = value
    journal = as_text(summary.get("fulljournalname")) or as_text(summary.get("source"))
    abbrev = as_text(summary.get("source"))
    pubtypes = [str(item).lower() for item in (summary.get("pubtype") or [])]
    retracted = any("retract" in item for item in pubtypes)
    preprint = any("preprint" in item for item in pubtypes) or looks_preprint(journal, None)
    year, month, day = _year_from_pubdate(as_text(summary.get("pubdate")) or as_text(summary.get("epubdate")))
    return SourceHit(
        source="pubmed",
        source_id=pmid,
        match_score=match_score,
        type="preprint" if preprint else "journal_article",
        title=title,
        authors=authors,
        year=year,
        month=month,
        day=day,
        journal=journal,
        journal_abbrev=abbrev if abbrev and abbrev != journal else abbrev,
        volume=as_text(summary.get("volume")),
        issue=as_text(summary.get("issue")),
        pages=clean_pages(as_text(summary.get("pages"))),
        doi=doi,
        pmid=pmid,
        url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else None,
        retracted=retracted,
        preprint=preprint,
    )


def _ids_from_search(payload: dict | None) -> list[str]:
    result = ((payload or {}).get("esearchresult") or {})
    return [str(item) for item in result.get("idlist") or []]


def _summaries(payload: dict | None) -> list[tuple[str, dict]]:
    result = (payload or {}).get("result") or {}
    uids = result.get("uids") or []
    pairs = []
    for uid in uids:
        summary = result.get(str(uid))
        if isinstance(summary, dict):
            pairs.append((str(uid), summary))
    return pairs


async def _get(client: HttpClient, endpoint: str, params: dict, mailto: str) -> dict | None:
    query = {
        "retmode": "json",
        "tool": "bibliography_agent",
        "email": mailto,
        **params,
    }
    cache_key = "pubmed:" + endpoint + ":" + "&".join(f"{key}={query[key]}" for key in sorted(query))
    return await client.get_json(
        f"{EUTILS}/{endpoint}",
        params=query,
        cache_key=cache_key,
        pace_key="ncbi",
        pace_seconds=0.34,
    )


async def fetch_pmid(client: HttpClient, pmid: str, mailto: str) -> SourceHit | None:
    payload = await _get(client, "esummary.fcgi", {"db": "pubmed", "id": pmid}, mailto)
    pairs = _summaries(payload)
    if not pairs:
        return None
    return summary_to_hit(pairs[0][0], pairs[0][1])


async def fetch_doi(client: HttpClient, doi: str, mailto: str) -> SourceHit | None:
    search = await _get(
        client,
        "esearch.fcgi",
        {"db": "pubmed", "term": f"{doi}[doi]", "retmax": 1},
        mailto,
    )
    ids = _ids_from_search(search)
    if not ids:
        return None
    return await fetch_pmid(client, ids[0], mailto)


async def search_title(client: HttpClient, title: str, mailto: str, limit: int = 5) -> list[SourceHit]:
    search = await _get(
        client,
        "esearch.fcgi",
        {"db": "pubmed", "term": f"{title}[Title]", "retmax": limit},
        mailto,
    )
    ids = _ids_from_search(search)
    if not ids:
        return []
    payload = await _get(
        client,
        "esummary.fcgi",
        {"db": "pubmed", "id": ",".join(ids)},
        mailto,
    )
    hits = []
    for uid, summary in _summaries(payload):
        hit = summary_to_hit(uid, summary, match_score=0.0)
        if hit:
            hits.append(hit)
    return hits
