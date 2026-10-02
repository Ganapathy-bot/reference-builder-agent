"""Compare a generated citation with the canonical record.

A formatter must not introduce a year, page range, DOI, or author
that the verified record does not contain.
"""

from __future__ import annotations

import re

from app.formats.common import split_pages
from app.models.metadata import Author, CanonicalRecord
from app.utils.doi import extract_dois
from app.validators.report import Issue

_YEAR_RE = re.compile(r"\b(1[5-9]\d{2}|20\d{2}|2100)\b")
_RANGE_RE = re.compile(r"\b(\d{1,5})\s*[-–—]\s*(\d{1,5})\b")


def listed_authors(style: str, authors: list[Author]) -> list[Author]:
    count = len(authors)
    if count == 0:
        return []
    if style == "apa":
        return authors[:19] + [authors[-1]] if count >= 21 else authors
    if style == "vancouver":
        return authors[:6]
    if style == "mla":
        return authors[:1] if count >= 3 else authors
    if style == "chicago":
        return authors[:7] if count >= 11 else authors
    if style == "harvard":
        return authors[:1] if count >= 4 else authors
    return authors


def check_citation(style: str, citation: str, record: CanonicalRecord) -> list[Issue]:
    issues: list[Issue] = []
    text = citation or ""
    lowered = text.casefold()
    for author in listed_authors(style, record.authors):
        if author.family and author.family.casefold() not in lowered:
            issues.append(
                Issue(
                    "missing_author",
                    f"Author {author.family} is missing from the {style} citation.",
                    style=style,
                )
            )
    if len(record.authors) == 1 and re.search(r"\bet al\.?", lowered):
        issues.append(Issue("invented_authors", "Citation uses et al. for a single verified author.", style=style))

    if record.year and str(record.year) not in text:
        issues.append(Issue("missing_year", "Publication year is missing from the citation.", style=style))

    allowed_years = set(_YEAR_RE.findall(record.title or ""))
    allowed_years.update(_YEAR_RE.findall(record.subtitle or ""))
    if record.year:
        allowed_years.add(str(record.year))
    if record.volume and _YEAR_RE.fullmatch(str(record.volume)):
        allowed_years.add(str(record.volume))
    scan = text
    if record.doi:
        scan = re.sub(re.escape(record.doi), " ", scan, flags=re.IGNORECASE)
    for year in _YEAR_RE.findall(scan):
        if year not in allowed_years:
            issues.append(
                Issue(
                    "year_mismatch",
                    f"Generated year {year} is not in the verified record.",
                    style=style,
                )
            )

    if record.doi:
        found = extract_dois(text)
        if not found:
            issues.append(Issue("missing_doi", "Verified DOI is missing from the citation.", style=style))
        elif found[0].lower() != record.doi.lower():
            issues.append(
                Issue(
                    "doi_mismatch",
                    f"Citation DOI {found[0]} does not match verified DOI {record.doi}.",
                    style=style,
                )
            )
    elif extract_dois(text):
        issues.append(Issue("invented_doi", "Citation contains a DOI that is not in the verified record.", style=style))

    start, end = split_pages(record.pages)
    if start and end and start.isdigit() and end.isdigit():
        ranges = []
        for left, right in _RANGE_RE.findall(text):
            if int(left) >= 1500 and int(right) >= 1500:
                continue
            ranges.append((left, right))
        if ranges and not any(_pages_match(start, end, left, right) for left, right in ranges):
            shown = ", ".join(f"{left}-{right}" for left, right in ranges)
            issues.append(
                Issue(
                    "page_mismatch",
                    f"Generated page range {shown} does not match verified pages {start}-{end}.",
                    style=style,
                )
            )
        elif not ranges and start not in text:
            issues.append(Issue("missing_pages", "Verified page range is missing from the citation.", style=style))

    journal = record.journal or ""
    if journal and record.type in {"journal_article", "preprint", "conference"}:
        abbrev = (record.journal_abbrev or "").casefold()
        if journal.casefold() not in lowered and (not abbrev or abbrev not in lowered):
            issues.append(Issue("missing_journal", "Verified journal is missing from the citation.", style=style))
    return issues


def _pages_match(start: str, end: str, left: str, right: str) -> bool:
    if left != start:
        return False
    return right == end or end.endswith(right)


def repair_citation(style: str, citation: str, record: CanonicalRecord, issues: list[Issue]) -> str:
    """Replace invented pages, years, or a missing DOI with verified values."""
    from app.formats.common import en_dash_pages, hyphen_pages, mla_pages

    updated = citation
    codes = {issue.code for issue in issues if issue.style in {style, None}}
    if "page_mismatch" in codes and record.pages:
        def replace(match: re.Match[str]) -> str:
            left, right = match.group(1), match.group(2)
            if left.isdigit() and right.isdigit() and int(left) >= 1500 and int(right) >= 1500:
                return match.group(0)
            if style == "mla":
                return mla_pages(record.pages)
            if style == "vancouver":
                return hyphen_pages(record.pages)
            return en_dash_pages(record.pages)

        updated = _RANGE_RE.sub(replace, updated, count=1)
    if "year_mismatch" in codes and record.year:
        allowed = set(_YEAR_RE.findall(record.title or ""))
        if record.volume and _YEAR_RE.fullmatch(str(record.volume)):
            allowed.add(str(record.volume))
        allowed.add(str(record.year))

        def replace_year(match: re.Match[str]) -> str:
            if match.group(1) in allowed:
                return match.group(0)
            return str(record.year)

        scan_doi = record.doi or ""
        protected = updated.replace(scan_doi, " ") if scan_doi else updated
        # Replace only on the working string, then keep DOI intact by operating with a placeholder.
        token = "\u0000DOI\u0000"
        shielded = updated.replace(record.doi, token) if record.doi else updated
        shielded = _YEAR_RE.sub(replace_year, shielded)
        updated = shielded.replace(token, record.doi or "")
        _ = protected
    if "missing_doi" in codes and record.doi and record.doi.lower() not in updated.lower():
        if style == "vancouver":
            updated = updated.rstrip() + f" doi:{record.doi}"
        elif style == "harvard":
            updated = updated.rstrip().rstrip(".") + f". doi: {record.doi}."
        else:
            updated = updated.rstrip() + f" https://doi.org/{record.doi}"
    if "missing_year" in codes and record.year and str(record.year) not in updated:
        updated = updated.rstrip() + f" {record.year}."
    return updated
