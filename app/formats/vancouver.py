"""Vancouver / ICMJE."""

from __future__ import annotations

from app.formats.common import Markup, full_title, host_link, hyphen_pages, sentence_title, year_label
from app.models.metadata import Author, CanonicalRecord
from app.utils.authors import join_names, vancouver_person
from app.utils.doi import doi_url


def format_vancouver(record: CanonicalRecord) -> tuple[Markup, list[str]]:
    notes: list[str] = []
    markup = Markup()
    authors = _authors(record.authors)
    title = sentence_title(record)
    if authors:
        markup.add(f"{authors}. ")
    if title:
        markup.add(f"{_period(title)} ")
    if record.type == "book":
        if record.publisher:
            markup.add(f"{record.publisher}; ")
        markup.add(f"{year_label(record, 'date unknown')}.")
    elif record.type == "chapter":
        book = record.container_title or record.journal or ""
        if book:
            markup.add(f"In: {book}. ")
        if record.publisher:
            markup.add(f"{record.publisher}; ")
        markup.add(year_label(record, "date unknown"))
        if record.pages:
            markup.add(f". p. {hyphen_pages(record.pages)}.")
        else:
            markup.add(".")
    elif record.type == "website":
        if record.publisher:
            markup.add(f"{record.publisher}. ")
        markup.add(f"{year_label(record, 'date unknown')}.")
        link = host_link(record)
        if link:
            markup.add(f" Available from: {link}")
    else:
        journal = record.journal_abbrev or record.journal or record.container_title
        if record.journal and not record.journal_abbrev:
            notes.append("Journal name is shown in full because no abbreviation was supplied by the sources.")
        if journal:
            label = f"{journal} [Preprint]" if record.type == "preprint" else journal
            markup.add(f"{label}. ")
        elif record.type == "preprint":
            markup.add("Preprint. ")
        markup.add(_locator(record))
    if record.type not in {"website"} and record.doi:
        markup.add(f" doi:{record.doi}")
    elif record.type not in {"book", "website", "chapter"} and not record.doi and record.urls:
        markup.add(f" Available from: {record.urls[0]}")
    return markup, notes


def in_text_vancouver(_record: CanonicalRecord) -> str:
    return "[1]"


def _authors(authors: list[Author]) -> str:
    if not authors:
        return ""
    shown = authors[:6]
    names = join_names([vancouver_person(author) for author in shown], sep=", ", last=", ")
    if len(authors) > 6:
        return f"{names}, et al"
    return names


def _locator(record: CanonicalRecord) -> str:
    year = year_label(record, "date unknown")
    pages = hyphen_pages(record.pages)
    if record.volume and record.issue and pages:
        return f"{year};{record.volume}({record.issue}):{pages}."
    if record.volume and record.issue:
        return f"{year};{record.volume}({record.issue})."
    if record.volume and pages:
        return f"{year};{record.volume}:{pages}."
    if record.volume:
        return f"{year};{record.volume}."
    if pages:
        return f"{year}:{pages}."
    return f"{year}."


def _period(text: str) -> str:
    text = text.strip()
    if not text or text[-1] in ".?!":
        return text
    return text + "."


_ = doi_url
