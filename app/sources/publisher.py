"""Landing-page metadata. Page text is parsed as data and is never treated as instructions."""

from __future__ import annotations

from html.parser import HTMLParser

from app.models.metadata import SourceHit
from app.sources.mapping import as_text, clean_pages, join_pages, looks_preprint, normalize_doi
from app.utils.authors import parse_display_name, parse_inverted_name
from app.utils.http import HttpClient, SourceError
from app.utils.safety import UnsafeURL


class _MetaParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.metas: list[dict[str, str]] = []
        self._in_title = False
        self.title_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = {key.lower(): (value or "") for key, value in attrs}
        if tag.lower() == "meta":
            self.metas.append(attr)
        elif tag.lower() == "title":
            self._in_title = True

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title_parts.append(data)


def _meta_map(metas: list[dict[str, str]]) -> dict[str, list[str]]:
    found: dict[str, list[str]] = {}
    for meta in metas:
        key = (meta.get("name") or meta.get("property") or meta.get("itemprop") or "").strip().lower()
        content = (meta.get("content") or "").strip()
        if not key or not content:
            continue
        found.setdefault(key, []).append(content)
    return found


def html_to_hit(html: str, url: str) -> SourceHit | None:
    parser = _MetaParser()
    try:
        parser.feed(html or "")
    except Exception:
        return None
    meta = _meta_map(parser.metas)
    doi = normalize_doi(
        _first(meta, "citation_doi")
        or _first(meta, "dc.identifier")
        or _first(meta, "dc.identifier.doi")
    )
    title = _first(meta, "citation_title") or _first(meta, "dc.title") or _first(meta, "og:title")
    if not title:
        title = " ".join(parser.title_parts).strip() or None
    if not title and not doi:
        return None
    authors = []
    for name in meta.get("citation_author", []) + meta.get("dc.creator", []):
        parsed = parse_inverted_name(name) if "," in name else parse_display_name(name)
        if parsed:
            authors.append(parsed)
    journal = _first(meta, "citation_journal_title") or _first(meta, "prism.publicationname")
    date = _first(meta, "citation_publication_date") or _first(meta, "citation_date") or _first(meta, "dc.date")
    year = _year(date)
    pages = join_pages(_first(meta, "citation_firstpage"), _first(meta, "citation_lastpage"))
    if not pages:
        pages = clean_pages(_first(meta, "citation_pages"))
    publisher = _first(meta, "citation_publisher") or _first(meta, "dc.publisher") or _first(meta, "og:site_name")
    pmid = _first(meta, "citation_pmid")
    preprint = looks_preprint(journal, None)
    kind = "preprint" if preprint else "journal_article" if journal else "website"
    return SourceHit(
        source="publisher",
        source_id=url,
        match_score=1.0,
        type=kind,
        title=as_text(title),
        authors=authors,
        year=year,
        journal=journal,
        volume=as_text(_first(meta, "citation_volume")),
        issue=as_text(_first(meta, "citation_issue")),
        pages=pages,
        publisher=publisher,
        doi=doi,
        pmid=pmid if pmid and pmid.isdigit() else None,
        url=url,
        preprint=preprint,
    )


def _first(meta: dict[str, list[str]], key: str) -> str | None:
    values = meta.get(key) or []
    return values[0].strip() if values else None


def _year(value: str | None) -> int | None:
    if not value:
        return None
    import re

    match = re.search(r"(1[5-9]\d{2}|20\d{2}|2100)", value)
    return int(match.group(1)) if match else None


async def fetch_url(client: HttpClient, url: str) -> SourceHit | None:
    try:
        html = await client.get_text(url)
    except (SourceError, UnsafeURL):
        raise
    if not html:
        return None
    return html_to_hit(html, url)
