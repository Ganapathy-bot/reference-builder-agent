"""DataCite REST API."""

from __future__ import annotations

from urllib.parse import quote

from app.models.metadata import Author, SourceHit
from app.sources.mapping import as_text, join_pages, looks_preprint, normalize_doi
from app.utils.authors import parse_display_name
from app.utils.http import HttpClient

DATACITE_TYPES = {
    "JournalArticle": "journal_article",
    "Book": "book",
    "BookChapter": "chapter",
    "Dataset": "dataset",
    "Preprint": "preprint",
    "Dissertation": "thesis",
    "Report": "report",
    "ConferencePaper": "conference",
    "Text": "misc",
    "Software": "misc",
}


def _creators(entries: list | None) -> list[Author]:
    authors: list[Author] = []
    for entry in entries or []:
        if not isinstance(entry, dict):
            continue
        given = as_text(entry.get("givenName"))
        family = as_text(entry.get("familyName"))
        name = as_text(entry.get("name"))
        if family:
            authors.append(Author(family=family, given=given, is_group=not given and len(family.split()) > 2))
            continue
        parsed = parse_display_name(name or "", group=bool(name and "," not in name and len(name.split()) > 2))
        if parsed:
            authors.append(parsed)
    return authors


def attributes_to_hit(attributes: dict, match_score: float = 1.0) -> SourceHit | None:
    if not isinstance(attributes, dict):
        return None
    titles = attributes.get("titles") or []
    title = as_text((titles[0] or {}).get("title")) if titles else None
    doi = normalize_doi(as_text(attributes.get("doi")))
    if not title and not doi:
        return None
    types = attributes.get("types") or {}
    general = as_text(types.get("resourceTypeGeneral")) or "Text"
    container = attributes.get("container") or {}
    journal = as_text(container.get("title"))
    preprint = looks_preprint(journal, general.lower() if general else None) or general == "Preprint"
    mapped = "preprint" if preprint else DATACITE_TYPES.get(general, "misc")
    year_raw = attributes.get("publicationYear")
    try:
        year = int(year_raw) if year_raw else None
    except (TypeError, ValueError):
        year = None
    isbn = []
    for identifier in attributes.get("relatedIdentifiers") or []:
        if str(identifier.get("relatedIdentifierType") or "").upper() == "ISBN":
            value = as_text(identifier.get("relatedIdentifier"))
            if value:
                isbn.append(value)
    return SourceHit(
        source="datacite",
        source_id=doi,
        match_score=match_score,
        type=mapped,
        title=title,
        authors=_creators(attributes.get("creators")),
        year=year,
        journal=journal,
        volume=as_text(container.get("volume")),
        issue=as_text(container.get("issue")),
        pages=join_pages(as_text(container.get("firstPage")), as_text(container.get("lastPage"))),
        publisher=as_text(attributes.get("publisher")),
        doi=doi,
        isbn=isbn,
        url=as_text(attributes.get("url")) or (f"https://doi.org/{doi}" if doi else None),
        preprint=preprint,
    )


async def fetch_doi(client: HttpClient, doi: str) -> SourceHit | None:
    payload = await client.get_json(
        f"https://api.datacite.org/dois/{quote(doi, safe='')}",
        cache_key=f"datacite:doi:{doi.lower()}",
        headers={"Accept": "application/vnd.api+json"},
    )
    if not payload:
        return None
    attributes = ((payload.get("data") or {}).get("attributes")) or {}
    return attributes_to_hit(attributes)


async def search_title(client: HttpClient, title: str, rows: int = 5) -> list[SourceHit]:
    payload = await client.get_json(
        "https://api.datacite.org/dois",
        params={"query": title, "page[size]": rows},
        cache_key=f"datacite:title:{title.casefold()}:{rows}",
        headers={"Accept": "application/vnd.api+json"},
    )
    hits = []
    for item in (payload or {}).get("data") or []:
        hit = attributes_to_hit((item or {}).get("attributes") or {}, match_score=0.0)
        if hit:
            hits.append(hit)
    return hits
