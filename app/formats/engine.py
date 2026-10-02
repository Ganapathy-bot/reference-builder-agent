"""Style engine. Each style stays in its own formatter."""

from __future__ import annotations

from app.formats.apa import format_apa, in_text_apa
from app.formats.chicago import format_chicago, in_text_chicago
from app.formats.common import FormatOptions, Markup
from app.formats.harvard import format_harvard, in_text_harvard
from app.formats.mla import format_mla, in_text_mla
from app.formats.vancouver import format_vancouver, in_text_vancouver
from app.models.metadata import CanonicalRecord
from app.models.response import STYLE_LABELS, STYLE_ORDER


def supported_styles() -> list[dict]:
    return [{"id": style_id, "label": STYLE_LABELS[style_id]} for style_id in STYLE_ORDER]


def normalize_styles(requested: list[str] | None) -> list[str]:
    if not requested:
        return ["apa"]
    chosen = []
    unknown = []
    for item in requested:
        key = (item or "").strip().lower().replace(" ", "")
        aliases = {
            "apa7": "apa",
            "mla9": "mla",
            "nlm": "vancouver",
            "icmje": "vancouver",
            "chicagoauthor-date": "chicago",
            "chicagoauthordate": "chicago",
        }
        key = aliases.get(key, key)
        if key in STYLE_LABELS and key not in chosen:
            chosen.append(key)
        elif key:
            unknown.append(item)
    if unknown:
        raise ValueError("Unknown citation style: " + ", ".join(unknown))
    return chosen or ["apa"]


def format_style(style: str, record: CanonicalRecord, options: FormatOptions | None = None) -> tuple[Markup, list[str]]:
    options = options or FormatOptions()
    if style in options.repaired:
        return Markup().add(options.repaired[style]), []
    if style == "apa":
        return format_apa(record)
    if style == "chicago":
        return format_chicago(record)
    if style == "mla":
        return format_mla(record)
    if style == "harvard":
        return format_harvard(record, options)
    if style == "vancouver":
        return format_vancouver(record)
    raise ValueError(f"Unknown citation style: {style}")


def format_in_text(style: str, record: CanonicalRecord) -> str:
    if style == "apa":
        return in_text_apa(record)
    if style == "chicago":
        return in_text_chicago(record)
    if style == "mla":
        return in_text_mla(record)
    if style == "harvard":
        return in_text_harvard(record)
    if style == "vancouver":
        return in_text_vancouver(record)
    raise ValueError(f"Unknown citation style: {style}")
