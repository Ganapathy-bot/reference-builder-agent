"""Open Library ISBN and title search."""

from __future__ import annotations

from app.models.metadata import SourceHit
from app.sources.mapping import as_text
from app.utils.authors import parse_display_name
from app.utils.doi import extract_isbns
from app.utils.http import HttpClient


def doc_to_hit(doc: dict, match_score: float = 1.0) -> SourceHit | None:
    if not isinstance(doc, dict):
        return None
    title = as_text(doc.get("title"))
    if not title:
        return None
    authors = []
    for name in doc.get("author_name") or []:
        parsed = parse_display_name(str(name))
        if parsed:
            authors.append(parsed)
    isbn_values = []
    for key in ("isbn", "isbn_13", "isbn_10"):
        for item in doc.get(key) or []:
            extracted = extract_isbns(str(item)) or ([re_digits(str(item))] if re_digits(str(item)) else [])
            for value in extracted:
                if value not in isbn_values:
                    isbn_values.append(value)
    publishers = doc.get("publisher") or []
    year = doc.get("first_publish_year")
    if not isinstance(year, int):
        year = None
    return SourceHit(
        source="openlibrary",
        source_id=as_text(doc.get("key")),
        match_score=match_score,
        type="book",
        title=title,
        authors=authors,
        year=year,
        publisher=as_text(publishers[0]) if publishers else None,
        isbn=isbn_values[:8],
        url=f"https://openlibrary.org{doc['key']}" if doc.get("key") else None,
    )


def re_digits(value: str) -> str | None:
    digits = "".join(ch for ch in value if ch.isdigit() or ch in "Xx")
    if len(digits) in {10, 13}:
        return digits.upper()
    return None


async def fetch_isbn(client: HttpClient, isbn: str) -> list[SourceHit]:
    payload = await client.get_json(
        "https://openlibrary.org/search.json",
        params={"isbn": isbn, "limit": 3},
        cache_key=f"openlibrary:isbn:{isbn}",
    )
    docs = (payload or {}).get("docs") or []
    return [hit for doc in docs if (hit := doc_to_hit(doc))]


async def search_title(client: HttpClient, title: str) -> list[SourceHit]:
    payload = await client.get_json(
        "https://openlibrary.org/search.json",
        params={"title": title, "limit": 3},
        cache_key=f"openlibrary:title:{title.casefold()}",
    )
    docs = (payload or {}).get("docs") or []
    return [hit for doc in docs if (hit := doc_to_hit(doc, match_score=0.0))]
