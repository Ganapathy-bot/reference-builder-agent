"""Structural BibTeX checks."""

from __future__ import annotations

from app.models.metadata import CanonicalRecord
from app.utils.doi import valid_doi_syntax
from app.validators.report import Issue


def validate_bibtex(bibtex: str | None, record: CanonicalRecord) -> list[Issue]:
    if not bibtex:
        return []
    issues: list[Issue] = []
    text = bibtex.strip()
    if not text.startswith("@"):
        issues.append(Issue("bibtex_type", "BibTeX entry does not start with an entry type.", style="bibtex"))
    if text.count("{") != text.count("}"):
        issues.append(Issue("bibtex_braces", "BibTeX braces are unbalanced.", style="bibtex"))
    if record.title and record.title.split(":")[0][:24].casefold() not in text.casefold() and record.title.casefold() not in text.casefold():
        # Escaped characters can change the title. Compare a short unescaped prefix of words.
        first_words = " ".join(record.title.split()[:3]).casefold()
        if first_words and first_words not in text.casefold():
            issues.append(Issue("bibtex_title", "BibTeX title does not match the verified title.", style="bibtex"))
    if record.year and str(record.year) not in text:
        issues.append(Issue("bibtex_year", "BibTeX is missing the verified year.", style="bibtex"))
    if record.doi:
        comparable = text.replace(r"\_", "_")
        if record.doi.lower() not in comparable.lower():
            issues.append(Issue("bibtex_doi", "BibTeX DOI does not match the verified DOI.", style="bibtex"))
        elif not valid_doi_syntax(record.doi):
            issues.append(Issue("bibtex_doi", "BibTeX DOI syntax is invalid.", style="bibtex"))
    for author in record.authors[:3]:
        if author.family and author.family.casefold() not in text.casefold():
            issues.append(Issue("bibtex_author", f"BibTeX is missing author {author.family}.", style="bibtex"))
    return issues
