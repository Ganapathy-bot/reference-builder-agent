"""Title, author, and duplicate similarity."""

from __future__ import annotations

import re
from difflib import SequenceMatcher

from app.models.metadata import Author, CanonicalRecord
from app.utils.authors import family_key
from app.utils.text import normalize_match


def title_similarity(left: str | None, right: str | None) -> float:
    a = normalize_match(left)
    b = normalize_match(right)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    return SequenceMatcher(None, a, b).ratio()


def title_recall(query: str | None, title: str | None) -> float:
    """How much of the candidate title is present in a longer pasted citation."""
    title_tokens = set(normalize_match(title).split())
    query_tokens = set(normalize_match(query).split())
    if not title_tokens:
        return 0.0
    return len(title_tokens & query_tokens) / len(title_tokens)


def score_title_match(query: str, record: CanonicalRecord) -> float:
    contained = normalize_match(record.title)
    query_norm = normalize_match(query)
    if contained and contained in query_norm:
        base = 0.97
    else:
        base = max(title_similarity(record.title, query), title_recall(query, record.title) * 0.98)
    if record.year and str(record.year) in query:
        base += 0.02
    if record.authors:
        family = normalize_match(record.authors[0].family)
        if family and family in query_norm:
            base += 0.02
    return round(min(base, 1.0), 4)


def author_jaccard(left: list[Author], right: list[Author]) -> float:
    a = {family_key(author) for author in left if family_key(author)}
    b = {family_key(author) for author in right if family_key(author)}
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def duplicate_report(left: CanonicalRecord, right: CanonicalRecord) -> dict | None:
    """Strong identifier matches and fuzzy title/author/year matches."""
    if left.record_id == right.record_id:
        return {"strength": "strong", "reason": "Same record", "similarity": 1.0}
    if left.doi and right.doi and left.doi.lower() == right.doi.lower():
        return {"strength": "strong", "reason": "Same DOI", "similarity": 1.0}
    if left.pmid and right.pmid and left.pmid == right.pmid:
        return {"strength": "medium", "reason": "Same PMID", "similarity": 0.98}
    left_isbn = set(left.isbn)
    right_isbn = set(right.isbn)
    if left_isbn and right_isbn and left_isbn & right_isbn:
        return {"strength": "medium", "reason": "Same ISBN", "similarity": 0.96}
    title_score = title_similarity(left.title, right.title)
    authors_score = author_jaccard(left.authors, right.authors)
    year_score = 1.0 if left.year and left.year == right.year else 0.0 if left.year and right.year else 0.5
    journal_score = title_similarity(left.journal, right.journal) if left.journal and right.journal else 0.5
    combined = (title_score * 0.55) + (authors_score * 0.25) + (year_score * 0.12) + (journal_score * 0.08)
    if title_score >= 0.92 and (year_score == 1.0 or authors_score >= 0.5):
        return {
            "strength": "fuzzy",
            "reason": "Title, author, and year are very close",
            "similarity": round(combined, 4),
        }
    if combined >= 0.86 and title_score >= 0.8:
        return {
            "strength": "fuzzy",
            "reason": "Bibliographic details overlap",
            "similarity": round(combined, 4),
        }
    return None


def same_work_hit(doi_a: str | None, doi_b: str | None, title_a: str | None, title_b: str | None, year_a: int | None, year_b: int | None, pmid_a: str | None = None, pmid_b: str | None = None) -> bool:
    if doi_a and doi_b and doi_a.lower() == doi_b.lower():
        return True
    if pmid_a and pmid_b and pmid_a == pmid_b:
        return True
    if title_a and title_b and title_similarity(title_a, title_b) >= 0.93:
        if year_a and year_b and abs(year_a - year_b) > 1:
            return False
        return True
    return False


_TOKEN = re.compile(r"[a-z0-9]+")


def significant_tokens(value: str | None) -> list[str]:
    stop = {"the", "a", "an", "of", "and", "or", "for", "in", "on", "with"}
    return [token for token in _TOKEN.findall((value or "").casefold()) if token not in stop]
