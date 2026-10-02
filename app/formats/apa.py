"""APA 7th edition."""

from __future__ import annotations

from app.formats.common import (
    Markup,
    en_dash_pages,
    full_title,
    host_link,
    sentence_title,
    venue,
    year_label,
)
from app.models.metadata import Author, CanonicalRecord
from app.utils.authors import apa_editor, apa_person, join_names
from app.utils.text import sentence_case


def format_apa(record: CanonicalRecord) -> tuple[Markup, list[str]]:
    if record.type == "book":
        return _book(record), []
    if record.type == "chapter":
        return _chapter(record), []
    if record.type == "website":
        return _web(record), []
    if record.type == "thesis":
        return _thesis(record), []
    if record.type == "dataset":
        return _dataset(record), []
    return _article(record), []


def in_text_apa(record: CanonicalRecord) -> str:
    year = year_label(record)
    names = _in_text_names(record.authors)
    if not names:
        title = sentence_case(full_title(record))
        return f"({title}, {year})"
    return f"({names}, {year})"


def _article(record: CanonicalRecord) -> Markup:
    markup = Markup()
    title = sentence_title(record)
    year = year_label(record)
    if record.authors:
        markup.add(f"{_reference_authors(record.authors)} ({year}). ")
        markup.add(_period(title) + " ")
    else:
        markup.add(f"{_period(title)} ({year}). ")
    journal = record.journal or record.container_title
    if journal and record.volume and record.issue:
        markup.add(f"{journal}, {record.volume}", italic=True)
        markup.add(f"({record.issue})")
        if record.pages:
            markup.add(f", {en_dash_pages(record.pages)}")
        markup.add(". ")
    elif journal and record.volume:
        markup.add(f"{journal}, {record.volume}", italic=True)
        markup.add(f", {en_dash_pages(record.pages)}. " if record.pages else ". ")
    elif journal and record.pages:
        markup.add(journal, italic=True)
        markup.add(f", {en_dash_pages(record.pages)}. ")
    elif journal:
        markup.add(journal, italic=True)
        markup.add(". ")
        if record.type == "journal_article" and not record.volume and not record.pages:
            markup.add("Advance online publication. ")
    if record.type == "preprint":
        markup.add("Preprint. ")
    link = host_link(record)
    if link:
        markup.add(link)
    return markup


def _book(record: CanonicalRecord) -> Markup:
    markup = Markup()
    year = year_label(record)
    title = sentence_title(record)
    if record.authors:
        markup.add(f"{_reference_authors(record.authors)} ({year}). ")
    else:
        markup.add(f"({year}). ")
    markup.add(_period(title), italic=True)
    markup.add(" ")
    if record.publisher:
        markup.add(f"{record.publisher}. ")
    link = host_link(record)
    if link:
        markup.add(link)
    return markup


def _chapter(record: CanonicalRecord) -> Markup:
    markup = Markup()
    year = year_label(record)
    title = sentence_title(record)
    book = sentence_case(record.container_title or record.journal or "")
    if record.authors:
        markup.add(f"{_reference_authors(record.authors)} ({year}). ")
    markup.add(f"{_period(title)} ")
    if record.editors:
        names = join_names(
            [apa_editor(editor) for editor in record.editors],
            sep=", ",
            last=", & " if len(record.editors) > 2 else " & ",
        )
        label = "Ed." if len(record.editors) == 1 else "Eds."
        markup.add(f"In {names} ({label}), ")
    elif book:
        markup.add("In ")
    if book:
        markup.add(book, italic=True)
    if record.pages:
        markup.add(f" (pp. {en_dash_pages(record.pages)})")
    markup.add(". ")
    if record.publisher:
        markup.add(f"{record.publisher}. ")
    link = host_link(record)
    if link:
        markup.add(link)
    return markup


def _web(record: CanonicalRecord) -> Markup:
    markup = Markup()
    year = year_label(record)
    title = sentence_title(record)
    if record.authors:
        markup.add(f"{_reference_authors(record.authors)} ({year}). ")
    else:
        markup.add(f"{_period(title)} ({year}). ")
        title = ""
    if title:
        markup.add(_period(title), italic=True)
        markup.add(" ")
    if record.publisher:
        markup.add(f"{record.publisher}. ")
    link = host_link(record)
    if link:
        markup.add(link)
    return markup


def _thesis(record: CanonicalRecord) -> Markup:
    markup = Markup()
    year = year_label(record)
    title = sentence_title(record)
    if record.authors:
        markup.add(f"{_reference_authors(record.authors)} ({year}). ")
    institution = record.publisher or "Institution"
    markup.add(_period(title), italic=True)
    markup.add(f" [Doctoral dissertation, {institution}]. ")
    link = host_link(record)
    if link:
        markup.add(link)
    return markup


def _dataset(record: CanonicalRecord) -> Markup:
    markup = Markup()
    year = year_label(record)
    title = sentence_title(record)
    if record.authors:
        markup.add(f"{_reference_authors(record.authors)} ({year}). ")
    markup.add(_period(title), italic=True)
    markup.add(" [Data set]. ")
    if record.publisher:
        markup.add(f"{record.publisher}. ")
    link = host_link(record)
    if link:
        markup.add(link)
    return markup


def _reference_authors(authors: list[Author]) -> str:
    if len(authors) >= 21:
        head = ", ".join(apa_person(author) for author in authors[:19])
        text = f"{head}, . . . {apa_person(authors[-1])}"
    else:
        names = [apa_person(author) for author in authors]
        text = join_names(names, sep=", ", last=", & ")
    last = authors[-1]
    if (last.is_group or not last.given) and not text.endswith("."):
        text += "."
    return text


def _in_text_names(authors: list[Author]) -> str:
    if not authors:
        return ""
    if len(authors) == 1:
        return authors[0].family
    if len(authors) == 2:
        return f"{authors[0].family} & {authors[1].family}"
    return f"{authors[0].family} et al."


def _period(text: str) -> str:
    text = text.strip()
    if not text:
        return ""
    if text[-1] in ".?!":
        return text
    return text + "."


_ = venue
