"""MLA 9th edition."""

from __future__ import annotations

from app.formats.common import Markup, full_title, host_link, mla_pages, year_label
from app.models.metadata import Author, CanonicalRecord
from app.utils.authors import join_names, mla_inverted, mla_straight
from app.utils.text import title_case


def format_mla(record: CanonicalRecord) -> tuple[Markup, list[str]]:
    if record.type == "book":
        return _book(record), []
    if record.type in {"website", "dataset"}:
        return _web(record), []
    return _article(record), []


def in_text_mla(record: CanonicalRecord) -> str:
    names = _in_text_names(record.authors)
    page = ""
    if record.pages:
        page = record.pages.replace("–", "-").split("-")[0].strip()
    locator = f" {page}" if page else ""
    if not names:
        title = title_case(full_title(record))
        short = title if len(title) <= 40 else title[:40].rstrip() + "..."
        return f"({short}{locator})"
    return f"({names}{locator})"


def _article(record: CanonicalRecord) -> Markup:
    markup = Markup()
    authors = _reference_authors(record.authors)
    title = title_case(full_title(record))
    if authors:
        markup.add(f"{authors}. ")
    markup.add(f'"{_period(title)}" ')
    journal = record.journal or record.container_title
    if journal:
        markup.add(journal, italic=True)
        markup.add(", ")
    bits = []
    if record.volume:
        bits.append(f"vol. {record.volume}")
    if record.issue:
        bits.append(f"no. {record.issue}")
    bits.append(year_label(record))
    if record.pages:
        bits.append(f"pp. {mla_pages(record.pages)}")
    markup.add(", ".join(bits) + ".")
    if record.type == "preprint":
        markup.add(" Preprint.")
    link = host_link(record)
    if link:
        markup.add(f" {link}")
    return markup


def _book(record: CanonicalRecord) -> Markup:
    markup = Markup()
    authors = _reference_authors(record.authors)
    title = title_case(full_title(record))
    if authors:
        markup.add(f"{authors}. ")
    markup.add(_bare(title), italic=True)
    markup.add(". ")
    tail = []
    if record.publisher:
        tail.append(record.publisher)
    tail.append(year_label(record))
    markup.add(", ".join(tail) + ".")
    link = host_link(record)
    if link:
        markup.add(f" {link}")
    return markup


def _web(record: CanonicalRecord) -> Markup:
    markup = Markup()
    authors = _reference_authors(record.authors)
    title = title_case(full_title(record))
    if authors:
        markup.add(f"{authors}. ")
    markup.add(f'"{_bare(title)}." ')
    if record.publisher:
        markup.add(record.publisher, italic=True)
        markup.add(", ")
    markup.add(f"{year_label(record)}.")
    link = host_link(record)
    if link:
        markup.add(f" {link}")
    return markup


def _reference_authors(authors: list[Author]) -> str:
    if not authors:
        return ""
    names = [mla_inverted(authors[0]), *(mla_straight(author) for author in authors[1:])]
    return join_names(names, sep=", ", last=", and ")


def _in_text_names(authors: list[Author]) -> str:
    if not authors:
        return ""
    if len(authors) == 1:
        return authors[0].family
    if len(authors) == 2:
        return f"{authors[0].family} and {authors[1].family}"
    return f"{authors[0].family} et al."


def _bare(text: str) -> str:
    return text.strip().rstrip(".")


def _period(text: str) -> str:
    text = _bare(text)
    return text if text.endswith(("?", "!")) else f"{text}."
