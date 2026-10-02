"""Chicago author-date, 17th edition."""

from __future__ import annotations

from app.formats.common import Markup, en_dash_pages, full_title, host_link, year_label
from app.models.metadata import Author, CanonicalRecord
from app.utils.authors import mla_inverted, mla_straight
from app.utils.text import title_case


def format_chicago(record: CanonicalRecord) -> tuple[Markup, list[str]]:
    if record.type == "book":
        return _book(record), []
    if record.type == "website":
        return _web(record), []
    return _article(record), []


def in_text_chicago(record: CanonicalRecord) -> str:
    year = year_label(record)
    names = _in_text_names(record.authors)
    if not names:
        return f"({year})"
    return f"({names} {year})"


def _article(record: CanonicalRecord) -> Markup:
    markup = Markup()
    authors = _reference_authors(record.authors)
    year = year_label(record)
    title = title_case(full_title(record))
    if authors:
        markup.add(f"{authors}. {year}. ")
    else:
        markup.add(f"{year}. ")
    markup.add(f'"{title}." ')
    journal = record.journal or record.container_title
    if journal:
        markup.add(journal, italic=True)
        markup.add(" ")
    locator = []
    if record.volume:
        issue = f" ({record.issue})" if record.issue else ""
        locator.append(f"{record.volume}{issue}")
    if record.pages:
        locator.append(en_dash_pages(record.pages))
    if locator:
        markup.add(": ".join(locator) if record.volume and record.pages else " ".join(locator))
        markup.add(".")
    if record.type == "preprint":
        markup.add(" Preprint.")
    link = host_link(record)
    if link:
        markup.add(f" {link}")
    return markup


def _book(record: CanonicalRecord) -> Markup:
    markup = Markup()
    authors = _reference_authors(record.authors)
    year = year_label(record)
    title = title_case(full_title(record))
    if authors:
        markup.add(f"{authors}. {year}. ")
    else:
        markup.add(f"{year}. ")
    markup.add(_period(title), italic=True)
    markup.add(" ")
    if record.publisher:
        markup.add(f"{record.publisher}.")
    link = host_link(record)
    if link:
        markup.add(f" {link}")
    return markup


def _web(record: CanonicalRecord) -> Markup:
    markup = Markup()
    authors = _reference_authors(record.authors)
    year = year_label(record)
    title = title_case(full_title(record))
    if authors:
        markup.add(f"{authors}. {year}. ")
    markup.add(f'"{title}." ')
    if record.publisher:
        markup.add(f"{record.publisher}. ")
    link = host_link(record)
    if link:
        markup.add(link)
    return markup


def _reference_authors(authors: list[Author]) -> str:
    if not authors:
        return ""
    shown = authors[:7] if len(authors) >= 11 else authors
    if len(shown) == 1:
        text = mla_inverted(shown[0])
    else:
        parts = [mla_inverted(shown[0])]
        parts.extend(mla_straight(author) for author in shown[1:])
        if len(parts) == 2:
            text = f"{parts[0]}, and {parts[1]}"
        else:
            text = ", ".join(parts[:-1]) + ", and " + parts[-1]
    if len(authors) >= 11:
        return f"{text}, et al."
    return text


def _in_text_names(authors: list[Author]) -> str:
    if not authors:
        return ""
    if len(authors) == 1:
        return authors[0].family
    if len(authors) == 2:
        return f"{authors[0].family} and {authors[1].family}"
    if len(authors) == 3:
        return f"{authors[0].family}, {authors[1].family}, and {authors[2].family}"
    return f"{authors[0].family} et al."


def _period(text: str) -> str:
    text = text.strip()
    if not text or text[-1] in ".?!":
        return text
    return text + "."
