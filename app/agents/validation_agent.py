"""Run metadata, citation, BibTeX, and hallucination checks together."""

from __future__ import annotations

from app.models.metadata import CanonicalRecord
from app.validators.bibtex import validate_bibtex
from app.validators.citation import validate_citations
from app.validators.metadata import validate_metadata
from app.validators.report import Issue, ValidationReport


def validate_output(
    record: CanonicalRecord,
    citations: dict[str, str],
    bibtex: str | None,
    *,
    check_metadata: bool = True,
) -> ValidationReport:
    errors: list[Issue] = []
    warnings: list[Issue] = []
    if check_metadata:
        for issue in validate_metadata(record):
            (errors if issue.severity == "error" else warnings).append(issue)
    for issue in validate_citations(record, citations):
        (errors if issue.severity == "error" else warnings).append(issue)
    for issue in validate_bibtex(bibtex, record):
        (errors if issue.severity == "error" else warnings).append(issue)
    return ValidationReport(errors=errors, warnings=warnings)
