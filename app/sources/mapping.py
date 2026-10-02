"""Shared mapping helpers for source adapters."""

from __future__ import annotations

import re

from app.models.metadata import Author
from app.utils.authors import clean_orcid, parse_display_name
from app.utils.doi import clean_doi, valid_doi_syntax
from app.utils.text import strip_tags

_PREPRINT_HINTS = ("biorxiv", "medrxiv", "arxiv", "ssrn", "preprints", "research square")


def as_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def year_from_parts(parts: list | None) -> tuple[int | None, int | None, int | None]:
    if not parts:
        return None, None, None
    year = int(parts[0]) if len(parts) > 0 and parts[0] else None
    month = int(parts[1]) if len(parts) > 1 and parts[1] else None
    day = int(parts[2]) if len(parts) > 2 and parts[2] else None
    return year, month, day


def clean_pages(value: str | None) -> str | None:
    if not value:
        return None
    text = value.strip()
    text = re.sub(r"^(pp?\.\s*)", "", text, flags=re.IGNORECASE)
    text = text.replace("–", "-").replace("—", "-").replace("−", "-")
    text = re.sub(r"\s+", "", text)
    text = text.strip(".,;")
    if not text:
        return None
    return text


def join_pages(first: str | None, last: str | None) -> str | None:
    if first and last:
        return clean_pages(f"{first}-{last}")
    return clean_pages(first or last)


def normalize_doi(value: str | None) -> str | None:
    if not value:
        return None
    doi = clean_doi(value)
    if not valid_doi_syntax(doi):
        return None
    return doi


def abstract_text(value: str | None) -> str | None:
    text = strip_tags(value)
    if not text:
        return None
    return text[:4000]


def crossref_authors(entries: list | None) -> list[Author]:
    authors: list[Author] = []
    for entry in entries or []:
        if not isinstance(entry, dict):
            continue
        orcid = clean_orcid(entry.get("ORCID") or entry.get("orcid"))
        if entry.get("name") and not entry.get("family"):
            parsed = parse_display_name(str(entry["name"]), orcid=orcid, group=True)
        else:
            family = as_text(entry.get("family"))
            given = as_text(entry.get("given"))
            if not family:
                continue
            parsed = Author(
                family=family,
                given=given,
                suffix=as_text(entry.get("suffix")),
                orcid=orcid,
                is_group=False,
            )
        if parsed:
            authors.append(parsed)
    return authors


def looks_preprint(journal: str | None, type_name: str | None) -> bool:
    if (type_name or "") in {"preprint", "posted-content"}:
        return True
    blob = (journal or "").casefold()
    return any(hint in blob for hint in _PREPRINT_HINTS)


def first_list_item(value: object) -> str | None:
    if isinstance(value, list):
        return as_text(value[0]) if value else None
    return as_text(value)
