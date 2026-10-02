"""Crossref works API."""

from __future__ import annotations

from urllib.parse import quote

from app.models.metadata import SourceHit
from app.sources.mapping import (
    abstract_text,
    as_text,
    clean_pages,
    crossref_authors,
    first_list_item,
    looks_preprint,
    normalize_doi,
    year_from_parts,
)
from app.utils.http import HttpClient, SourceError

CROSSREF_TYPES = {
    "journal-article": "journal_article",
    "book": "book",
    "edited-book": "book",
    "monograph": "book",
    "book-chapter": "chapter",
    "reference-entry": "chapter",
    "proceedings-article": "conference",
    "proceedings": "conference",
    "posted-content": "preprint",
    "dissertation": "thesis",
    "report": "report",
    "report-component": "report",
    "dataset": "dataset",
}


def _date(message: dict, key: str) -> int | None:
    parts = ((message.get(key) or {}).get("date-parts") or [[]])[0]
    year, _month, _day = year_from_parts(parts)
    return year


def message_to_hit(message: dict, match_score: float = 1.0) -> SourceHit | None:
    if not isinstance(message, dict):
        return None
    title = first_list_item(message.get("title"))
    if not title and not message.get("DOI"):
        return None
    issued = ((message.get("issued") or {}).get("date-parts") or [[]])[0]
    year, month, day = year_from_parts(issued)
    online = _date(message, "published-online")
    printed = _date(message, "published-print")
    if year is None:
        year = printed or online
    alt_years = sorted({value for value in (online, printed) if value and value != year})
    raw_type = as_text(message.get("type")) or ""
    container = first_list_item(message.get("container-title"))
    subtype = as_text(message.get("subtype")) or ""
    preprint = looks_preprint(container, raw_type) or "preprint" in subtype
    updates = message.get("update-to") or []
    retracted = any(
        isinstance(item, dict) and "retract" in str(item.get("type", "")).lower()
        for item in updates
    )
    isbn = [str(item) for item in (message.get("ISBN") or []) if item]
    issn = [str(item) for item in (message.get("ISSN") or []) if item]
    doi = normalize_doi(as_text(message.get("DOI")))
    mapped = "preprint" if preprint else CROSSREF_TYPES.get(raw_type, "journal_article" if container else "misc")
    journal = None if mapped == "chapter" else container
    return SourceHit(
        source="crossref",
        source_id=doi,
        match_score=match_score,
        type=mapped,
        title=title,
        subtitle=first_list_item(message.get("subtitle")),
        authors=crossref_authors(message.get("author")),
        editors=crossref_authors(message.get("editor")),
        year=year,
        alt_years=alt_years,
        month=month,
        day=day,
        journal=journal,
        journal_abbrev=None if mapped == "chapter" else first_list_item(message.get("short-container-title")),
        volume=as_text(message.get("volume")),
        issue=as_text(message.get("issue")),
        pages=clean_pages(as_text(message.get("page"))),
        publisher=as_text(message.get("publisher")),
        container_title=container if mapped in {"chapter", "conference"} else None,
        doi=doi,
        isbn=isbn,
        issn=issn,
        url=as_text(message.get("URL")) or (f"https://doi.org/{doi}" if doi else None),
        abstract=abstract_text(as_text(message.get("abstract"))),
        retracted=retracted,
        preprint=preprint,
    )


async def fetch_doi(client: HttpClient, doi: str) -> SourceHit | None:
    url = f"https://api.crossref.org/works/{quote(doi, safe='')}"
    payload = await client.get_json(url, cache_key=f"crossref:doi:{doi.lower()}")
    if not payload:
        return None
    return message_to_hit((payload or {}).get("message") or {})


async def search_title(client: HttpClient, title: str, rows: int = 5) -> list[SourceHit]:
    payload = await client.get_json(
        "https://api.crossref.org/works",
        params={"query.bibliographic": title, "rows": rows},
        cache_key=f"crossref:title:{title.casefold()}:{rows}",
    )
    items = (((payload or {}).get("message") or {}).get("items")) or []
    hits: list[SourceHit] = []
    for item in items:
        hit = message_to_hit(item, match_score=0.0)
        if hit:
            hits.append(hit)
    return hits


async def search_isbn(client: HttpClient, isbn: str) -> list[SourceHit]:
    try:
        payload = await client.get_json(
            "https://api.crossref.org/works",
            params={"query.bibliographic": isbn, "filter": f"isbn:{isbn}", "rows": 3},
            cache_key=f"crossref:isbn:{isbn}",
        )
    except SourceError:
        return []
    items = (((payload or {}).get("message") or {}).get("items")) or []
    return [hit for item in items if (hit := message_to_hit(item))]
