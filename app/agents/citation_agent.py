"""Generate citations, validate them, and self-correct up to MAX_RETRIES."""

from __future__ import annotations

from app.agents.validation_agent import validate_output
from app.formats.bibtex import citation_key, render_bibtex
from app.formats.common import FormatOptions
from app.formats.engine import format_in_text, format_style
from app.models.metadata import CanonicalRecord
from app.validators.hallucination import repair_citation
from app.validators.report import ValidationReport


def generate(
    record: CanonicalRecord,
    styles: list[str],
    *,
    include_bibtex: bool = True,
    validate: bool = True,
    max_retries: int = 2,
    used_keys: set[str] | None = None,
) -> dict:
    registry = used_keys if used_keys is not None else set()
    cite_key = citation_key(record, registry) if include_bibtex else None
    options = FormatOptions()
    corrections: list[str] = []
    best: dict | None = None
    report = ValidationReport()
    attempts = 0
    for attempt in range(1, max_retries + 2):
        attempts = attempt
        rendered = _render(record, styles, include_bibtex, options, cite_key)
        if not validate:
            report = ValidationReport(attempts=attempt)
            best = _pack(rendered, report, corrections)
            break
        report = validate_output(record, rendered["citations"], rendered["bibtex"])
        report.attempts = attempt
        report.corrections = list(corrections)
        best = _pack(rendered, report, corrections)
        if report.passed:
            break
        repaired, notes = _diagnose(record, rendered["citations"], report, options)
        if repaired is None:
            break
        corrections.extend(notes)
        options = repaired
    assert best is not None
    if not report.passed and validate:
        best["warnings"].append(
            "Validation did not fully pass after self-correction. Review the result before citing."
        )
    best["validation"]["attempts"] = attempts
    best["validation"]["corrections"] = corrections
    return best


def _render(
    record: CanonicalRecord,
    styles: list[str],
    include_bibtex: bool,
    options: FormatOptions,
    cite_key: str | None,
) -> dict:
    citations: dict[str, str] = {}
    citations_html: dict[str, str] = {}
    notes: dict[str, list[str]] = {}
    in_text: dict[str, str] = {}
    for style in styles:
        markup, style_notes = format_style(style, record, options)
        citations[style] = markup.plain()
        citations_html[style] = markup.html()
        notes[style] = style_notes
        in_text[style] = format_in_text(style, record)
    bibtex = render_bibtex(record, key=cite_key) if include_bibtex and cite_key else None
    return {
        "citations": citations,
        "citations_html": citations_html,
        "citation_notes": notes,
        "in_text": in_text,
        "bibtex": bibtex,
    }


def _diagnose(
    record: CanonicalRecord,
    citations: dict[str, str],
    report: ValidationReport,
    options: FormatOptions,
) -> tuple[FormatOptions | None, list[str]]:
    if options.repaired:
        return None, []
    repaired: dict[str, str] = {}
    notes: list[str] = []
    for style, text in citations.items():
        relevant = [issue for issue in report.errors if issue.style == style]
        if not relevant:
            continue
        updated = repair_citation(style, text, record, relevant)
        if updated != text:
            repaired[style] = updated
            notes.append(f"{style}: regenerated from verified metadata after {relevant[0].code}.")
    if not repaired:
        return None, []
    options.repaired = repaired
    return options, notes


def _pack(rendered: dict, report: ValidationReport, corrections: list[str]) -> dict:
    warnings = [issue.message for issue in report.warnings]
    return {
        **rendered,
        "validation": report.as_dict(),
        "warnings": warnings,
        "corrections": corrections,
    }
