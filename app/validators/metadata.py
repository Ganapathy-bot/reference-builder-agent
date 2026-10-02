"""Checks on the canonical record itself."""

from __future__ import annotations

from datetime import datetime

from app.formats.common import split_pages
from app.models.metadata import CanonicalRecord
from app.utils.doi import isbn10_valid, isbn13_valid, valid_doi_syntax
from app.validators.report import Issue


def validate_metadata(record: CanonicalRecord) -> list[Issue]:
    issues: list[Issue] = []
    if not (record.title or "").strip():
        issues.append(Issue("missing_title", "Title is missing.", severity="error"))
    if not record.authors:
        issues.append(Issue("missing_authors", "No authors were found.", severity="warning"))
    if record.year is None:
        issues.append(Issue("missing_year", "Publication year is missing.", severity="warning"))
    else:
        horizon = datetime.now().year + 1
        if record.year < 1400 or record.year > horizon:
            issues.append(Issue("year_range", f"Publication year {record.year} is outside a plausible range.", severity="error"))
    if record.doi and not valid_doi_syntax(record.doi):
        issues.append(Issue("doi_syntax", "DOI syntax is invalid.", severity="error"))
    if record.type in {"journal_article", "preprint", "conference"} and not record.journal:
        issues.append(Issue("missing_journal", "Journal or venue is missing.", severity="warning"))
    start, end = split_pages(record.pages)
    if start and end and start.isdigit() and end.isdigit() and int(start) > int(end) and len(start) == len(end):
        issues.append(Issue("page_order", "Page range ends before it starts.", severity="error"))
    for isbn in record.isbn:
        digits = "".join(ch for ch in isbn if ch.isdigit() or ch in "Xx")
        if len(digits) == 13 and not isbn13_valid(digits):
            issues.append(Issue("isbn_checksum", f"ISBN {isbn} failed its checksum.", severity="warning"))
        elif len(digits) == 10 and not isbn10_valid(digits.upper()):
            issues.append(Issue("isbn_checksum", f"ISBN {isbn} failed its checksum.", severity="warning"))
    if record.doi and record.pmid and not record.pmid.isdigit():
        issues.append(Issue("pmid_syntax", "PMID is not numeric.", severity="error"))
    return issues
