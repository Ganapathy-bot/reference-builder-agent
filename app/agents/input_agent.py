"""Detect input type, requested styles, and batch requests."""

from __future__ import annotations

import re

from app.models.metadata import ParsedInput
from app.models.response import STYLE_ORDER
from app.utils.doi import extract_dois, extract_isbns, extract_pmids

_STYLE_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("apa", re.compile(r"\bapa(?:\s*7)?\b", re.I)),
    ("chicago", re.compile(r"\bchicago\b", re.I)),
    ("mla", re.compile(r"\bmla(?:\s*9)?\b", re.I)),
    ("harvard", re.compile(r"\bharvard\b", re.I)),
    ("vancouver", re.compile(r"\b(?:vancouver|nlm|icmje)\b", re.I)),
]

_URL_RE = re.compile(r"https?://[^\s<>\"']+", re.I)
_CHECK_RE = re.compile(
    r"\b(is this (citation|reference) correct|check whether|verify whether|check this citation|verify this citation)\b",
    re.I,
)
_BIBTEX_RE = re.compile(r"\bbib\s?tex\b", re.I)
_NUMBERED_RE = re.compile(r"^\s*(?:\d+[\).\]]\s+|[-*]\s+)")
_LEADING_REQUEST_RE = re.compile(
    r"^(?:please\s+)?(?:look\s+up|lookup|search\s+for|give\s+me|get\s+me|convert|generate|format|find|cite)\b[\s:,-]*",
    re.I,
)


def parse_input(raw: str) -> ParsedInput:
    text = (raw or "").strip()
    styles = _styles(text)
    outputs = ["citation"]
    if _BIBTEX_RE.search(text) or not text:
        outputs.append("bibtex")
    else:
        outputs.append("bibtex")
    intent = "check" if _CHECK_RE.search(text) else "cite"
    constraints: list[str] = []
    if intent == "check":
        constraints.append("compare the supplied citation with verified metadata")
    if styles:
        constraints.append("styles requested in natural language")

    items = _batch_items(text)
    if len(items) >= 2:
        return ParsedInput(
            raw_input=text,
            source_type="batch",
            source_value=text,
            requested_styles=styles,
            outputs=outputs,
            intent=intent,
            items=items,
            constraints=constraints,
        )

    dois = extract_dois(text)
    if len(dois) == 1:
        return _single(text, "doi", dois[0], styles, outputs, intent, constraints)
    pmids = extract_pmids(text)
    if len(pmids) == 1 and not dois:
        return _single(text, "pmid", pmids[0], styles, outputs, intent, constraints)
    isbns = extract_isbns(text)
    if len(isbns) == 1 and not dois and not pmids:
        return _single(text, "isbn", isbns[0], styles, outputs, intent, constraints)

    urls = _plain_urls(text)
    if len(urls) == 1 and not dois:
        return _single(text, "url", urls[0], styles, outputs, intent, constraints)

    title = _title_query(text)
    return _single(text, "title", title, styles, outputs, intent, constraints)


def _single(
    raw: str,
    source_type: str,
    source_value: str,
    styles: list[str],
    outputs: list[str],
    intent: str,
    constraints: list[str],
) -> ParsedInput:
    return ParsedInput(
        raw_input=raw,
        source_type=source_type,
        source_value=source_value,
        requested_styles=styles,
        outputs=outputs,
        intent=intent,
        items=[source_value] if source_value else [],
        constraints=constraints,
    )


def _styles(text: str) -> list[str]:
    found = []
    for style_id, pattern in _STYLE_PATTERNS:
        if pattern.search(text) and style_id not in found:
            found.append(style_id)
    return [style for style in STYLE_ORDER if style in found]


def _plain_urls(text: str) -> list[str]:
    urls = []
    for match in _URL_RE.finditer(text):
        url = match.group(0).rstrip(".,;:)")
        lowered = url.lower()
        if "doi.org/" in lowered or "pubmed.ncbi.nlm.nih.gov" in lowered:
            continue
        if url not in urls:
            urls.append(url)
    return urls


def _batch_items(text: str) -> list[str]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) < 2:
        dois = extract_dois(text)
        if len(dois) >= 2:
            return dois
        return []
    items = []
    for line in lines:
        cleaned = _NUMBERED_RE.sub("", line).strip()
        if not cleaned or _is_instruction_line(cleaned):
            continue
        if extract_dois(cleaned) or extract_pmids(cleaned) or extract_isbns(cleaned) or _plain_urls(cleaned):
            items.append(cleaned)
        elif len(cleaned) > 12 and not _STYLE_PATTERNS[0][1].fullmatch(cleaned):
            # A line that is only a style name is not a reference.
            if _looks_like_reference_line(cleaned):
                items.append(cleaned)
    identifier_items = [
        item
        for item in items
        if extract_dois(item) or extract_pmids(item) or extract_isbns(item) or _plain_urls(item)
    ]
    if len(identifier_items) >= 2:
        return identifier_items
    return []


def _is_instruction_line(line: str) -> bool:
    if extract_dois(line) or extract_pmids(line) or extract_isbns(line) or _plain_urls(line):
        return False
    words = line.split()
    if len(words) <= 8 and re.search(r"\b(give|convert|generate|style|vancouver|apa|mla|chicago|harvard)\b", line, re.I):
        return True
    return False


def _looks_like_reference_line(line: str) -> bool:
    return bool(re.search(r"\b(19|20)\d{2}\b", line)) and len(line.split()) >= 4


def _title_query(text: str) -> str:
    quoted = re.search(r"[\"“]([^\"”]{6,})[\"”]", text)
    if quoted:
        return quoted.group(1).strip()
    cleaned = text
    cleaned = _BIBTEX_RE.sub(" ", cleaned)
    cleaned = _CHECK_RE.sub(" ", cleaned)
    for _style, pattern in _STYLE_PATTERNS:
        cleaned = pattern.sub(" ", cleaned)
    cleaned = re.sub(r"\b(bibtex|citations?|references?|in style|style)\b", " ", cleaned, flags=re.I)
    previous = None
    while previous != cleaned:
        previous = cleaned
        cleaned = _LEADING_REQUEST_RE.sub("", cleaned).strip()
    cleaned = re.sub(
        r"^(?:for|of|this(?:\s+(?:title|paper|article|doi))?(?:\s+to)?)\b[\s:,-]*",
        "",
        cleaned,
        flags=re.I,
    )
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .,:;-")
    return cleaned
