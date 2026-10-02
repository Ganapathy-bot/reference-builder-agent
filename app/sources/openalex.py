"""OpenAlex works API."""

from __future__ import annotations

from app.models.metadata import SourceHit
from app.sources.mapping import as_text, join_pages, looks_preprint, normalize_doi
from app.utils.authors import parse_display_name
from app.utils.http import HttpClient

OPENALEX_TYPES = {
    "article": "journal_article",
    "review": "journal_article",
    "letter": "journal_article",
    "book": "book",
    "book-chapter": "chapter",
    "dissertation": "thesis",
    "preprint": "preprint",
    "dataset": "dataset",
    "report": "report",
    "paratext": "misc",
}


def _pmid(work: dict) -> str | None:
    ids = work.get("ids") or {}
    raw = ids.get("pmid") or ""
    if isinstance(raw, str) and raw:
        digits = raw.rstrip("/").split("/")[-1]
        if digits.isdigit():
            return digits
    return None


def work_to_hit(work: dict, match_score: float = 1.0) -> SourceHit | None:
    if not isinstance(work, dict):
        return None
    title = as_text(work.get("display_name") or work.get("title"))
    doi = normalize_doi(as_text(work.get("doi")))
    if not title and not doi:
        return None
    authors = []
    for authorship in work.get("authorships") or []:
        author = authorship.get("author") or {}
        name = as_text(authorship.get("raw_author_name")) or as_text(author.get("display_name"))
        institutions = authorship.get("institutions") or []
        group = bool(authorship.get("is_corresponding")) and False
        # OpenAlex marks consortia with author_position and a display name without a given name split.
        if name and not author.get("display_name") and len(name.split()) > 3:
            group = True
        parsed = parse_display_name(name or "", orcid=as_text(author.get("orcid")), group=group)
        if parsed:
            authors.append(parsed)
        _ = institutions
    location = work.get("primary_location") or {}
    source = location.get("source") or {}
    biblio = work.get("biblio") or {}
    journal = as_text(source.get("display_name"))
    raw_type = as_text(work.get("type")) or ""
    preprint = looks_preprint(journal, raw_type)
    mapped = "preprint" if preprint else OPENALEX_TYPES.get(raw_type, "journal_article" if journal else "misc")
    issn = []
    if source.get("issn_l"):
        issn.append(str(source["issn_l"]))
    isbn = [str(item) for item in (work.get("isbn") or biblio.get("isbn") or []) if item] if isinstance(work.get("isbn"), list) else []
    return SourceHit(
        source="openalex",
        source_id=as_text(work.get("id")),
        match_score=match_score,
        type=mapped,
        title=title,
        authors=authors,
        year=work.get("publication_year") if isinstance(work.get("publication_year"), int) else None,
        journal=journal,
        volume=as_text(biblio.get("volume")),
        issue=as_text(biblio.get("issue")),
        pages=join_pages(as_text(biblio.get("first_page")), as_text(biblio.get("last_page"))),
        publisher=as_text((source.get("host_organization_name")) or work.get("host_venue")),
        doi=doi,
        pmid=_pmid(work),
        isbn=isbn,
        issn=issn,
        url=as_text(location.get("landing_page_url")) or (f"https://doi.org/{doi}" if doi else None),
        retracted=bool(work.get("is_retracted")),
        preprint=preprint,
    )


async def fetch_doi(client: HttpClient, doi: str, mailto: str) -> SourceHit | None:
    payload = await client.get_json(
        "https://api.openalex.org/works",
        params={"filter": f"doi:{doi}", "mailto": mailto},
        cache_key=f"openalex:doi:{doi.lower()}",
    )
    results = (payload or {}).get("results") or []
    if not results:
        return None
    return work_to_hit(results[0])


async def search_title(client: HttpClient, title: str, mailto: str, per_page: int = 5) -> list[SourceHit]:
    payload = await client.get_json(
        "https://api.openalex.org/works",
        params={"search": title, "per-page": per_page, "mailto": mailto},
        cache_key=f"openalex:title:{title.casefold()}:{per_page}",
    )
    results = (payload or {}).get("results") or []
    hits = []
    for item in results:
        hit = work_to_hit(item, match_score=0.0)
        if hit:
            hits.append(hit)
    return hits
