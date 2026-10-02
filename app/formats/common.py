"""Markup and page helpers shared by style formatters."""

from __future__ import annotations

import html
import re
from dataclasses import dataclass, field
from datetime import date

from app.models.metadata import CanonicalRecord
from app.utils.doi import doi_url
from app.utils.text import sentence_case


@dataclass
class FormatOptions:
    accessed: date | None = None
    repaired: dict[str, str] = field(default_factory=dict)


class Markup:
    def __init__(self) -> None:
        self.parts: list[tuple[str, bool]] = []

    def add(self, text: str | None, italic: bool = False) -> Markup:
        if text:
            self.parts.append((str(text), italic))
        return self

    def plain(self) -> str:
        return tidy("".join(text for text, _italic in self.parts))

    def html(self) -> str:
        chunks = []
        for text, italic in self.parts:
            escaped = html.escape(text, quote=False)
            chunks.append(f"<em>{escaped}</em>" if italic else escaped)
        return tidy("".join(chunks))


def tidy(text: str) -> str:
    text = text.replace("\u00a0", " ")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\s+([,.;:])", r"\1", text)
    text = re.sub(r"\(\s+", "(", text)
    text = re.sub(r"\s+\)", ")", text)
    text = text.replace("..", ".")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def split_pages(pages: str | None) -> tuple[str | None, str | None]:
    if not pages:
        return None, None
    text = pages.replace("–", "-").replace("—", "-").replace("−", "-")
    text = re.sub(r"\s+", "", text)
    text = re.sub(r"^(?:pp?\.?)", "", text, flags=re.IGNORECASE)
    if not text:
        return None, None
    if "-" in text:
        start, end = text.split("-", 1)
        return (start or None), (end or None)
    return text, None


def en_dash_pages(pages: str | None) -> str:
    start, end = split_pages(pages)
    if not start:
        return ""
    return f"{start}\u2013{end}" if end else start


def hyphen_pages(pages: str | None) -> str:
    start, end = split_pages(pages)
    if not start:
        return ""
    return f"{start}-{end}" if end else start


def mla_pages(pages: str | None) -> str:
    start, end = split_pages(pages)
    if not start:
        return ""
    if not end or not (start.isdigit() and end.isdigit()) or len(start) != len(end) or len(start) < 2:
        return hyphen_pages(pages)
    index = 0
    while index < len(start) - 2 and start[index] == end[index]:
        index += 1
    return f"{start}-{end[index:]}"


def bibtex_pages(pages: str | None) -> str:
    start, end = split_pages(pages)
    if not start:
        return ""
    return f"{start}--{end}" if end else start


def full_title(record: CanonicalRecord) -> str:
    title = (record.title or "").strip()
    subtitle = (record.subtitle or "").strip()
    if subtitle and subtitle.casefold() not in title.casefold():
        return f"{title}: {subtitle}"
    return title


def year_label(record: CanonicalRecord, missing: str = "n.d.") -> str:
    return str(record.year) if record.year else missing


def venue(record: CanonicalRecord) -> str | None:
    return record.journal or record.container_title or record.publisher


def accessed_label(when: date | None) -> str:
    moment = when or date.today()
    return moment.strftime("%d %B %Y").lstrip("0")


def host_link(record: CanonicalRecord) -> str:
    if record.doi:
        return doi_url(record.doi)
    return record.urls[0] if record.urls else ""


def article_like(record: CanonicalRecord) -> bool:
    return record.type in {"journal_article", "preprint", "conference", "misc"}


def sentence_title(record: CanonicalRecord) -> str:
    return sentence_case(full_title(record))
