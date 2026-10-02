"""Style-output checks against canonical metadata."""

from __future__ import annotations

from app.models.metadata import CanonicalRecord
from app.validators.hallucination import check_citation
from app.validators.report import Issue


def validate_citations(record: CanonicalRecord, citations: dict[str, str]) -> list[Issue]:
    issues: list[Issue] = []
    for style, text in citations.items():
        if not (text or "").strip():
            issues.append(Issue("empty_citation", f"{style} citation is empty.", style=style))
            continue
        issues.extend(check_citation(style, text, record))
    return issues
