"""DOI, PMID, and ISBN detection and checks."""

from __future__ import annotations

import re

DOI_RE = re.compile(r"\b(10\.\d{4,9}/[^\s\"'<>]+)", re.IGNORECASE)
DOI_SYNTAX = re.compile(r"^10\.\d{4,9}/\S+$", re.IGNORECASE)
PMID_URL_RE = re.compile(
    r"pubmed\.ncbi\.nlm\.nih\.gov/(?:pubmed/)?(\d{4,9})\b", re.IGNORECASE
)
PMID_LABEL_RE = re.compile(r"\bPMID\s*[:#]?\s*(\d{4,9})\b", re.IGNORECASE)
_ISBN_RE = re.compile(
    r"\b(?:ISBN(?:-1[03])?[:\s#-]*)?([0-9][0-9Xx][0-9Xx\-\s]{8,20}[0-9Xx])\b",
    re.IGNORECASE,
)


def clean_doi(value: str) -> str:
    doi = value.strip()
    doi = re.sub(r"^(https?://(?:dx\.)?doi\.org/)", "", doi, flags=re.IGNORECASE)
    doi = re.sub(r"^doi:\s*", "", doi, flags=re.IGNORECASE)
    doi = doi.split("?")[0].split("#")[0].strip()
    while doi and doi[-1] in ".,;:)>]}\"'":
        doi = doi[:-1]
    return doi


def extract_dois(text: str) -> list[str]:
    found: list[str] = []
    for match in DOI_RE.finditer(text or ""):
        doi = clean_doi(match.group(1))
        if doi and doi not in found and valid_doi_syntax(doi):
            found.append(doi)
    return found


def extract_doi(text: str) -> str | None:
    found = extract_dois(text)
    return found[0] if found else None


def valid_doi_syntax(doi: str) -> bool:
    return bool(doi) and bool(DOI_SYNTAX.match(doi.strip()))


def doi_url(doi: str) -> str:
    return f"https://doi.org/{doi}"


def extract_pmids(text: str) -> list[str]:
    found: list[str] = []
    for pattern in (PMID_URL_RE, PMID_LABEL_RE):
        for match in pattern.finditer(text or ""):
            pmid = match.group(1)
            if pmid not in found:
                found.append(pmid)
    return found


def extract_isbns(text: str) -> list[str]:
    found: list[str] = []
    for match in _ISBN_RE.finditer(text or ""):
        raw = re.sub(r"[^0-9Xx]", "", match.group(1))
        if len(raw) == 13 and raw.isdigit() and isbn13_valid(raw):
            if raw not in found:
                found.append(raw)
        elif len(raw) == 10 and isbn10_valid(raw):
            normalized = raw.upper()
            if normalized not in found:
                found.append(normalized)
    return found


def isbn13_valid(isbn: str) -> bool:
    digits = [int(ch) for ch in isbn if ch.isdigit()]
    if len(digits) != 13:
        return False
    total = sum(number * (1 if index % 2 == 0 else 3) for index, number in enumerate(digits[:-1]))
    check = (10 - (total % 10)) % 10
    return check == digits[-1]


def isbn10_valid(isbn: str) -> bool:
    chars = [ch for ch in isbn if ch.isdigit() or ch in "Xx"]
    if len(chars) != 10:
        return False
    numbers = [10 if ch in "Xx" else int(ch) for ch in chars]
    return sum((10 - index) * number for index, number in enumerate(numbers)) % 11 == 0
