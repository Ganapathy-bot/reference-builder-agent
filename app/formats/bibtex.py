"""Deterministic BibTeX generated only from canonical metadata."""

from __future__ import annotations

import re

from app.formats.common import bibtex_pages, full_title, host_link
from app.models.metadata import Author, CanonicalRecord
from app.utils.authors import bibtex_person
from app.utils.text import first_title_word

_ENTRY = {
    "journal_article": "article",
    "book": "book",
    "chapter": "incollection",
    "conference": "inproceedings",
    "thesis": "phdthesis",
    "report": "techreport",
    "preprint": "misc",
    "website": "misc",
    "dataset": "misc",
    "misc": "misc",
}

_ESCAPE = {
    "\\": r"\textbackslash{}",
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}


def bibtex_escape(value: str) -> str:
    return "".join(_ESCAPE.get(char, char) for char in value)


def citation_key(record: CanonicalRecord, used: set[str]) -> str:
    if record.authors:
        family = re.sub(r"[^A-Za-z0-9]", "", record.authors[0].family) or "Anon"
    else:
        family = "Anon"
    year = str(record.year) if record.year else "nd"
    word = re.sub(r"[^A-Za-z0-9]", "", first_title_word(record.title)) or "Ref"
    base = f"{family}{year}{word}"
    key = base
    index = 0
    while key.casefold() in used:
        index += 1
        suffix = chr(96 + index) if index <= 26 else str(index)
        key = f"{base}{suffix}"
    used.add(key.casefold())
    return key


def render_bibtex(record: CanonicalRecord, used: set[str] | None = None, key: str | None = None) -> str:
    registry = used if used is not None else set()
    cite_key = key or citation_key(record, registry)
    if key and key.casefold() not in registry:
        registry.add(key.casefold())
    entry = _ENTRY.get(record.type, "misc")
    fields: list[tuple[str, str]] = []

    def add(name: str, value: str | None) -> None:
        if value:
            fields.append((name, value))

    if record.authors:
        add("author", " and ".join(_person(author) for author in record.authors))
    if record.editors and record.type in {"chapter", "conference"}:
        add("editor", " and ".join(_person(author) for author in record.editors))
    add("title", full_title(record))
    if entry == "article":
        add("journal", record.journal)
    elif entry in {"incollection", "inproceedings"}:
        add("booktitle", record.container_title or record.journal)
    if entry == "techreport":
        add("institution", record.publisher)
    elif entry == "phdthesis":
        add("school", record.publisher)
    elif record.publisher and entry in {"book", "incollection", "inproceedings", "misc"}:
        add("publisher", record.publisher)
    if record.year:
        add("year", str(record.year))
    add("volume", record.volume)
    add("number", record.issue)
    add("pages", bibtex_pages(record.pages))
    add("doi", record.doi)
    add("pmid", record.pmid)
    if record.isbn:
        add("isbn", record.isbn[0])
    if record.issn:
        add("issn", record.issn[0])
    link = host_link(record)
    if link:
        add("url", link)
    if record.type == "preprint":
        add("note", "Preprint")
    elif record.type == "dataset":
        add("note", "Dataset")
    lines = [f"@{entry}{{{cite_key},"]
    for index, (name, value) in enumerate(fields):
        comma = "," if index < len(fields) - 1 else ""
        lines.append(f"  {name} = {{{bibtex_escape(value)}}}{comma}")
    lines.append("}")
    return "\n".join(lines)


def _person(author: Author) -> str:
    return bibtex_person(author)
