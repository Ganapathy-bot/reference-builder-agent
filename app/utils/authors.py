"""Author parsing and style-specific name shapes."""

from __future__ import annotations

import re

from app.models.metadata import Author

_SUFFIXES = {"jr", "jr.", "sr", "sr.", "ii", "iii", "iv", "v"}


def clean_orcid(value: str | None) -> str | None:
    if not value:
        return None
    text = value.strip().rstrip("/")
    text = re.sub(r"^https?://orcid\.org/", "", text, flags=re.IGNORECASE)
    return text or None


def _initial_letters(given: str) -> list[str]:
    compact = given.replace(".", " ").strip()
    parts = [part for part in compact.split() if part]
    if len(parts) == 1 and parts[0].isalpha() and parts[0].isupper() and 1 < len(parts[0]) <= 4:
        return list(parts[0])
    letters: list[str] = []
    for part in parts:
        if part:
            letters.append(part[0].upper())
    return letters


def initials_spaced(given: str | None) -> str:
    if not given or not given.strip():
        return ""
    return " ".join(f"{letter}." for letter in _initial_letters(given))


def initials_compact(given: str | None) -> str:
    return initials_spaced(given).replace(" ", "")


def initials_plain(given: str | None) -> str:
    return initials_spaced(given).replace(".", "").replace(" ", "")


def full_given(given: str | None) -> str:
    if not given or not given.strip():
        return ""
    text = given.strip()
    letters = re.sub(r"[^A-Za-z]", "", text)
    if letters.isupper() and len(letters) <= 4 and " " not in text.strip("."):
        return initials_spaced(text)
    if re.fullmatch(r"(?:[A-Z]\.?\s*){1,4}", text):
        return initials_spaced(text)
    return text


def parse_display_name(name: str, orcid: str | None = None, group: bool = False) -> Author | None:
    text = re.sub(r"\s+", " ", (name or "")).strip(" ,")
    if not text:
        return None
    if group:
        return Author(family=text, orcid=clean_orcid(orcid), is_group=True)
    parts = text.split(" ")
    suffix = None
    if parts and parts[-1].lower().rstrip(".") in {item.rstrip(".") for item in _SUFFIXES}:
        suffix = parts[-1].rstrip(".")
        if suffix.lower() in {"jr", "sr"}:
            suffix = suffix[0].upper() + suffix[1:].lower() + "."
        else:
            suffix = suffix.upper()
        parts = parts[:-1]
    if not parts:
        return None
    if len(parts) == 1:
        return Author(family=parts[0], suffix=suffix, orcid=clean_orcid(orcid), is_group=True)
    family = parts[-1]
    given = " ".join(parts[:-1])
    return Author(family=family, given=given, suffix=suffix, orcid=clean_orcid(orcid))


def parse_inverted_name(name: str, orcid: str | None = None) -> Author | None:
    """Parse 'Family, Given' or a bare organizational name."""
    text = re.sub(r"\s+", " ", (name or "")).strip(" ,")
    if not text:
        return None
    if "," not in text:
        return parse_display_name(text, orcid=orcid, group=len(text.split()) >= 3 and text[:1].isupper())
    family, given = text.split(",", 1)
    return Author(family=family.strip(), given=given.strip() or None, orcid=clean_orcid(orcid))


def parse_pubmed_name(name: str) -> Author | None:
    text = re.sub(r"\s+", " ", (name or "")).strip(" ,")
    if not text:
        return None
    if re.search(r"\s[A-Z]{1,5}$", text):
        family, initials = text.rsplit(" ", 1)
        return Author(family=family, given=initials)
    return Author(family=text, is_group=True)


def family_key(author: Author) -> str:
    return re.sub(r"[^a-z0-9]", "", (author.family or "").casefold())


def authors_display(authors: list[Author]) -> str:
    parts: list[str] = []
    for author in authors:
        if author.is_group or not author.given:
            parts.append(author.family)
        else:
            parts.append(f"{author.family}, {author.given}")
    return "; ".join(parts)


def apa_person(author: Author) -> str:
    if author.is_group or not author.given:
        name = author.family
    else:
        initials = initials_spaced(author.given)
        name = f"{author.family}, {initials}" if initials else author.family
    if author.suffix:
        name = f"{name}, {author.suffix}"
    return name


def apa_editor(author: Author) -> str:
    if author.is_group or not author.given:
        return author.family
    initials = initials_spaced(author.given)
    return f"{initials} {author.family}".strip()


def vancouver_person(author: Author) -> str:
    if author.is_group or not author.given:
        return author.family
    initials = initials_plain(author.given)
    name = f"{author.family} {initials}".strip()
    if author.suffix:
        name = f"{name} {author.suffix.replace('.', '')}"
    return name


def harvard_person(author: Author) -> str:
    if author.is_group or not author.given:
        return author.family
    initials = initials_compact(author.given)
    name = f"{author.family}, {initials}" if initials else author.family
    if author.suffix:
        name = f"{name}, {author.suffix}"
    return name


def mla_inverted(author: Author) -> str:
    if author.is_group or not author.given:
        return author.family
    return f"{author.family}, {full_given(author.given)}"


def mla_straight(author: Author) -> str:
    if author.is_group or not author.given:
        return author.family
    return f"{full_given(author.given)} {author.family}".strip()


def join_names(names: list[str], sep: str = ", ", last: str = " and ") -> str:
    if not names:
        return ""
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return names[0] + last + names[1]
    return sep.join(names[:-1]) + last + names[-1]


def bibtex_person(author: Author) -> str:
    family = author.family
    if author.is_group or not author.given:
        return family
    given = full_given(author.given)
    name = f"{family}, {given}" if given else family
    if author.suffix:
        name = f"{name}, {author.suffix}"
    return name
