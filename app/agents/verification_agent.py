"""Turn field evidence into a confidence score and publication flags."""

from __future__ import annotations

from app.models.metadata import CanonicalRecord, FieldValue


def verify(record: CanonicalRecord) -> CanonicalRecord:
    """Score the reconciled record. Missing applicable fields lower confidence."""
    if record.isbn:
        record.fields["isbn"] = FieldValue(
            selected=", ".join(record.isbn),
            confidence=0.93,
            sources=record.sources_used,
            status="verified" if len(record.sources_used) > 1 else "partially_verified",
        )
    elif "isbn" not in record.fields:
        record.fields["isbn"] = FieldValue(status="missing")
    weights = _weights(record)
    total = 0.0
    used = 0.0
    for name, weight in weights:
        field = record.fields.get(name) or FieldValue(status="missing", confidence=0.0)
        total += weight * field.confidence
        used += weight
    record.confidence = round(total / used, 4) if used else 0.0
    if record.retracted and "retracted" not in record.status_flags:
        record.status_flags.insert(0, "retracted")
    if record.confidence < 0.70 and "low_confidence" not in record.status_flags:
        record.status_flags.append("low_confidence")
    elif 0.70 <= record.confidence < 0.90 and "review_recommended" not in record.status_flags:
        record.status_flags.append("review_recommended")
    return record


def _weights(record: CanonicalRecord) -> list[tuple[str, float]]:
    if record.type == "book":
        return [("title", 0.28), ("authors", 0.24), ("year", 0.18), ("publisher", 0.14), ("isbn", 0.16)]
    if record.type == "website":
        return [("title", 0.34), ("authors", 0.16), ("year", 0.16), ("publisher", 0.14), ("doi", 0.20)]
    if record.type == "chapter":
        return [
            ("title", 0.24),
            ("authors", 0.22),
            ("year", 0.16),
            ("container_title", 0.16),
            ("pages", 0.10),
            ("doi", 0.12),
        ]
    if record.type == "dataset":
        return [("title", 0.30), ("authors", 0.22), ("year", 0.16), ("publisher", 0.12), ("doi", 0.20)]
    return [
        ("title", 0.22),
        ("authors", 0.20),
        ("year", 0.16),
        ("journal", 0.16),
        ("doi", 0.16),
        ("pages", 0.10),
    ]


def field_checklist(record: CanonicalRecord) -> list[dict]:
    order = ["doi", "title", "authors", "journal", "year", "volume", "issue", "pages", "publisher", "pmid", "isbn"]
    items = []
    for name in order:
        field = record.fields.get(name)
        if name == "isbn":
            selected = ", ".join(record.isbn) if record.isbn else None
            status = "verified" if record.isbn else "missing"
            items.append({"field": name, "status": status, "value": selected, "conflict": False})
            continue
        if field is None:
            continue
        if name == "journal" and record.type not in {"journal_article", "preprint", "conference"}:
            continue
        items.append(
            {
                "field": name,
                "status": field.status,
                "value": field.selected,
                "conflict": field.conflict,
                "alternatives": field.alternatives,
                "sources": field.sources,
                "confidence": field.confidence,
            }
        )
    return items
