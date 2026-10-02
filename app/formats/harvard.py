"""Harvard (Cite Them Right)."""

from __future__ import annotations

from app.formats.common import Markup, accessed_label, en_dash_pages, full_title, host_link, sentence_title, year_label
from app.formats.common import FormatOptions
from app.models.metadata import Author, CanonicalRecord
from app.utils.authors import harvard_person, join_names
from app.utils.text import sentence_case


def format_harvard(record: CanonicalRecord, options: FormatOptions | None = None) -> tuple[Markup, list[str]]:
    if record.type == "book":
        return _book(record), []
    if record.type == "website":
        return _web(record, options or FormatOptions()), []
    return _article(record), []


def in_text_harvard(record: CanonicalRecord) -> str:
    year = year_label(record)
    names = _in_text_names(record.authors)
    if not names:
        title = sentence_case(full_title(record))
        short = title if len(title) <= 48 else title[:48].rstrip()
        return f"({short}, {year})"
    return f"({names}, {year})"


def _article(record: CanonicalRecord) -> Markup:
    markup = Markup()
    year = year_label(record)
    authors = _reference_authors(record.authors)
    title = sentence_title(record)
    if authors:
        markup.add(f"{authors} ({year}) ")
    else:
        markup.add(f"({year}) ")
    markup.add(f"'{title}', ")
    journal = record.journal or record.container_title
    if journal:
        markup.add(journal, italic=True)
        markup.add(", ")
    bits = []
    if record.volume and record.issue:
        bits.append(f"{record.volume}({record.issue})")
    elif record.volume:
        bits.append(str(record.volume))
    if record.pages:
        bits.append(f"pp. {en_dash_pages(record.pages)}")
    if bits:
        markup.add(", ".join(bits) + ".")
    else:
        markup.add("")
    if record.type == "preprint":
        markup.add(" Preprint.")
    if record.doi:
        markup.add(f" doi: {record.doi}.")
    elif record.urls:
        markup.add(f" Available at: {record.urls[0]}")
    return markup


def _book(record: CanonicalRecord) -> Markup:
    markup = Markup()
    year = year_label(record)
    authors = _reference_authors(record.authors)
    title = sentence_title(record)
    if authors:
        markup.add(f"{authors} ({year}) ")
    else:
        markup.add(f"({year}) ")
    markup.add(title, italic=True)
    markup.add(". ")
    if record.publisher:
        markup.add(f"{record.publisher}.")
    if record.doi:
        markup.add(f" doi: {record.doi}.")
    return markup


def _web(record: CanonicalRecord, options: FormatOptions) -> Markup:
    markup = Markup()
    year = year_label(record)
    authors = _reference_authors(record.authors)
    title = sentence_title(record)
    if authors:
        markup.add(f"{authors} ({year}) ")
    markup.add(title, italic=True)
    markup.add(". ")
    if record.publisher:
        markup.add(f"{record.publisher}. ")
    link = host_link(record)
    if link:
        markup.add(f"Available at: {link} (Accessed: {accessed_label(options.accessed)}).")
    return markup


def _reference_authors(authors: list[Author]) -> str:
    if not authors:
        return ""
    names = [harvard_person(author) for author in authors]
    return join_names(names, sep=", ", last=" and ")


def _in_text_names(authors: list[Author]) -> str:
    if not authors:
        return ""
    if len(authors) == 1:
        return authors[0].family
    if len(authors) == 2:
        return f"{authors[0].family} and {authors[1].family}"
    if len(authors) == 3:
        return f"{authors[0].family}, {authors[1].family} and {authors[2].family}"
    return f"{authors[0].family} et al."
