"""Compare source records, keep conflicts visible, and build one canonical record."""

from __future__ import annotations

import hashlib
from typing import Callable

from app.models.metadata import Author, CanonicalRecord, FieldValue, SourceHit
from app.sources.mapping import clean_pages
from app.utils.authors import authors_display, family_key
from app.utils.similarity import author_jaccard
from app.utils.text import collapse, normalize_match

SOURCE_WEIGHT = {
    "crossref": 1.00,
    "pubmed": 0.98,
    "datacite": 0.90,
    "openlibrary": 0.90,
    "openalex": 0.86,
    "publisher": 0.80,
}

CORE_FIELDS = ("title", "authors", "year", "journal")
WEAK_FIELDS = {"pages", "issue", "volume", "publisher"}


def reconcile(hits: list[SourceHit]) -> CanonicalRecord:
    usable = [hit for hit in hits if hit.title or hit.doi or hit.isbn or hit.pmid]
    if not usable:
        raise ValueError("No metadata to reconcile.")
    fields: dict[str, FieldValue] = {}
    title_field = _pick_text(usable, lambda hit: hit.title, weak=False)
    fields["title"] = title_field
    year_field = _pick_year(usable)
    fields["year"] = year_field
    journal_field = _pick_text(usable, lambda hit: hit.journal, weak=False)
    fields["journal"] = journal_field
    abbrev_field = _pick_text(usable, lambda hit: hit.journal_abbrev, weak=True)
    fields["journal_abbrev"] = abbrev_field
    volume_field = _pick_text(usable, lambda hit: hit.volume, weak=True)
    fields["volume"] = volume_field
    issue_field = _pick_text(usable, lambda hit: hit.issue, weak=True)
    fields["issue"] = issue_field
    pages_field = _pick_text(usable, lambda hit: clean_pages(hit.pages), weak=True)
    fields["pages"] = pages_field
    publisher_field = _pick_text(usable, lambda hit: hit.publisher, weak=True)
    fields["publisher"] = publisher_field
    doi_field = _pick_text(usable, lambda hit: hit.doi, weak=False, prefer_source="crossref")
    fields["doi"] = doi_field
    pmid_field = _pick_text(usable, lambda hit: hit.pmid, weak=False, prefer_source="pubmed")
    fields["pmid"] = pmid_field
    container_field = _pick_text(usable, lambda hit: hit.container_title, weak=True)
    fields["container_title"] = container_field
    subtitle_field = _pick_text(usable, lambda hit: hit.subtitle, weak=True)
    fields["subtitle"] = subtitle_field

    authors, author_field = _pick_authors(usable)
    fields["authors"] = author_field
    editors = _richest(usable, lambda hit: hit.editors)

    record_type = _pick_type(usable)
    isbn = _union(usable, lambda hit: hit.isbn)
    issn = _union(usable, lambda hit: hit.issn)
    urls = []
    for hit in _by_weight(usable):
        if hit.url and hit.url not in urls:
            urls.append(hit.url)
    doi = doi_field.selected
    if doi and f"https://doi.org/{doi}" not in urls:
        urls.insert(0, f"https://doi.org/{doi}")
    abstract = next((hit.abstract for hit in _by_weight(usable) if hit.abstract), None)
    month, day = _date_parts(usable, year_field.selected)
    retracted = any(hit.retracted for hit in usable)
    preprint = any(hit.preprint for hit in usable) or record_type == "preprint"
    if preprint:
        record_type = "preprint"

    flags: list[str] = []
    if retracted:
        flags.append("retracted")
    if preprint:
        flags.append("preprint")
    elif record_type == "journal_article" and not volume_field.selected and not pages_field.selected:
        flags.append("early_access")
    elif not retracted:
        flags.append("published")
    if any(field.conflict or field.status in {"conflicting", "unresolved"} for field in fields.values()):
        flags.append("metadata_conflict")

    record = CanonicalRecord(
        record_id=_record_id(doi, pmid_field.selected, isbn, title_field.selected, year_field.selected),
        type=record_type,
        title=title_field.selected or "",
        subtitle=subtitle_field.selected,
        authors=authors,
        editors=editors,
        year=year_field.selected,
        month=month,
        day=day,
        journal=journal_field.selected,
        journal_abbrev=abbrev_field.selected,
        volume=volume_field.selected,
        issue=issue_field.selected,
        pages=pages_field.selected,
        publisher=publisher_field.selected,
        container_title=container_field.selected,
        doi=doi,
        pmid=pmid_field.selected,
        isbn=isbn,
        issn=issn,
        urls=urls,
        abstract=abstract,
        fields=fields,
        status_flags=flags,
        sources_used=sorted({hit.source for hit in usable}),
        retracted=retracted,
        preprint=preprint,
        match_score=max((hit.match_score for hit in usable), default=1.0),
    )
    return record


def _by_weight(hits: list[SourceHit]) -> list[SourceHit]:
    return sorted(hits, key=lambda hit: SOURCE_WEIGHT.get(hit.source, 0.5), reverse=True)


def _status(support_count: int, conflict: bool, close: bool, exact: bool, weak: bool) -> tuple[str, float]:
    if close:
        return "unresolved", 0.42
    if conflict:
        return "conflicting", 0.62
    if support_count >= 2:
        return "verified", 0.97
    if weak:
        return "partially_verified", 0.72
    if exact:
        return "verified", 0.93
    return "partially_verified", 0.75


def _pick_text(
    hits: list[SourceHit],
    getter: Callable[[SourceHit], str | None],
    weak: bool,
    prefer_source: str | None = None,
) -> FieldValue:
    buckets: dict[str, list[tuple[SourceHit, str]]] = {}
    for hit in hits:
        value = getter(hit)
        if not value:
            continue
        key = normalize_match(value) or value.casefold()
        buckets.setdefault(key, []).append((hit, value))
    if not buckets:
        return FieldValue(status="missing", confidence=0.0)
    ranked = sorted(
        buckets.items(),
        key=lambda item: _bucket_score(item[1], prefer_source),
        reverse=True,
    )
    winner_pairs = ranked[0][1]
    selected = _preferred_original(winner_pairs, prefer_source)
    alternatives = []
    for _key, pairs in ranked[1:]:
        alternative = _preferred_original(pairs, prefer_source)
        if alternative and normalize_match(alternative) != normalize_match(selected):
            alternatives.append(alternative)
    support = _bucket_score(winner_pairs, prefer_source)
    second = _bucket_score(ranked[1][1], prefer_source) if len(ranked) > 1 else 0.0
    conflict = bool(alternatives) and second >= 0.75
    close = conflict and second >= support * 0.85
    exact = any(hit.match_score >= 0.999 for hit, _value in winner_pairs)
    status, confidence = _status(len({hit.source for hit, _value in winner_pairs}), conflict, close, exact, weak)
    return FieldValue(
        selected=selected,
        confidence=confidence,
        sources=sorted({hit.source for hit, _value in winner_pairs}),
        conflict=conflict,
        alternatives=alternatives,
        status=status,
    )


def _bucket_score(pairs: list[tuple[SourceHit, str]], prefer_source: str | None) -> float:
    score = 0.0
    seen = set()
    for hit, _value in pairs:
        if hit.source in seen:
            continue
        seen.add(hit.source)
        score += SOURCE_WEIGHT.get(hit.source, 0.5)
        if prefer_source and hit.source == prefer_source:
            score += 0.15
    return score


def _preferred_original(pairs: list[tuple[SourceHit, str]], prefer_source: str | None) -> str:
    def sort_key(pair: tuple[SourceHit, str]) -> tuple:
        hit, value = pair
        return (
            0 if prefer_source and hit.source == prefer_source else 1,
            -SOURCE_WEIGHT.get(hit.source, 0.5),
            -len(value),
        )

    return sorted(pairs, key=sort_key)[0][1]


def _pick_year(hits: list[SourceHit]) -> FieldValue:
    buckets: dict[int, list[SourceHit]] = {}
    for hit in hits:
        if hit.year:
            buckets.setdefault(hit.year, []).append(hit)
        for alt in hit.alt_years:
            if alt != hit.year:
                buckets.setdefault(alt, []).append(hit)
    if not buckets:
        return FieldValue(status="missing", confidence=0.0)
    # Alt years from the same hit should not count as a second independent source
    # for the primary year, but they do create an alternative.
    primary: dict[int, list[SourceHit]] = {}
    for hit in hits:
        if hit.year:
            primary.setdefault(hit.year, []).append(hit)
    if not primary:
        primary = buckets
    ranked = sorted(
        primary.items(),
        key=lambda item: sum(SOURCE_WEIGHT.get(hit.source, 0.5) for hit in item[1]),
        reverse=True,
    )
    year, supporters = ranked[0]
    alternatives = [other for other in buckets if other != year]
    support = sum(SOURCE_WEIGHT.get(hit.source, 0.5) for hit in supporters)
    second_support = 0.0
    if len(ranked) > 1:
        second_support = sum(SOURCE_WEIGHT.get(hit.source, 0.5) for hit in ranked[1][1])
    elif alternatives:
        second_support = 0.8
    conflict = bool(alternatives)
    close = conflict and (second_support >= support * 0.85 if len(ranked) > 1 else False)
    exact = any(hit.match_score >= 0.999 for hit in supporters)
    status, confidence = _status(len({hit.source for hit in supporters}), conflict, close, exact, weak=False)
    if conflict and not close and len(supporters) >= 1 and second_support < support:
        status, confidence = "conflicting", max(confidence, 0.7)
    return FieldValue(
        selected=year,
        confidence=confidence,
        sources=sorted({hit.source for hit in supporters}),
        conflict=conflict,
        alternatives=alternatives,
        status=status,
    )


def _pick_authors(hits: list[SourceHit]) -> tuple[list[Author], FieldValue]:
    lists = [(hit, hit.authors) for hit in hits if hit.authors]
    if not lists:
        return [], FieldValue(status="missing", confidence=0.0, selected="")
    buckets: list[list[tuple[SourceHit, list[Author]]]] = []
    for hit, authors in lists:
        placed = False
        for bucket in buckets:
            if author_jaccard(bucket[0][1], authors) >= 0.67:
                bucket.append((hit, authors))
                placed = True
                break
        if not placed:
            buckets.append([(hit, authors)])

    def bucket_score(bucket: list[tuple[SourceHit, list[Author]]]) -> float:
        sources = {hit.source for hit, _authors in bucket}
        richness = max(_richness(authors) for _hit, authors in bucket)
        return sum(SOURCE_WEIGHT.get(source, 0.5) for source in sources) + min(richness, 40) / 400

    buckets.sort(key=bucket_score, reverse=True)
    winner = buckets[0]
    selected = max((authors for _hit, authors in winner), key=_richness)
    alternatives = []
    for bucket in buckets[1:]:
        alt = max((authors for _hit, authors in bucket), key=_richness)
        label = authors_display(alt)
        if label and label not in alternatives:
            alternatives.append(label)
    conflict = bool(alternatives)
    close = False
    if len(buckets) > 1:
        close = bucket_score(buckets[1]) >= bucket_score(winner) * 0.9
    exact = any(hit.match_score >= 0.999 for hit, _authors in winner)
    status, confidence = _status(len({hit.source for hit, _authors in winner}), conflict, close, exact, weak=False)
    return selected, FieldValue(
        selected=authors_display(selected),
        confidence=confidence,
        sources=sorted({hit.source for hit, _authors in winner}),
        conflict=conflict,
        alternatives=alternatives,
        status=status,
    )


def _richness(authors: list[Author]) -> int:
    score = 0
    for author in authors:
        score += 2
        if author.given and len(author.given) > 2:
            score += 2
        if author.orcid:
            score += 1
    return score


def _richest(hits: list[SourceHit], getter: Callable[[SourceHit], list[Author]]) -> list[Author]:
    choices = [getter(hit) for hit in hits if getter(hit)]
    if not choices:
        return []
    return max(choices, key=_richness)


def _pick_type(hits: list[SourceHit]) -> str:
    ranked = _by_weight(hits)
    for preferred in ("crossref", "pubmed", "datacite", "openlibrary"):
        for hit in ranked:
            if hit.source == preferred and hit.type:
                return hit.type
    return ranked[0].type or "misc"


def _union(hits: list[SourceHit], getter: Callable[[SourceHit], list[str]]) -> list[str]:
    values: list[str] = []
    for hit in _by_weight(hits):
        for item in getter(hit):
            if item and item not in values:
                values.append(item)
    return values


def _date_parts(hits: list[SourceHit], year: int | None) -> tuple[int | None, int | None]:
    for hit in _by_weight(hits):
        if hit.year == year and (hit.month or hit.day):
            return hit.month, hit.day
    return None, None


def _record_id(doi: str | None, pmid: str | None, isbn: list[str], title: str | None, year: int | None) -> str:
    if doi:
        return doi.lower()
    if pmid:
        return f"pmid:{pmid}"
    if isbn:
        return f"isbn:{isbn[0]}"
    digest = hashlib.sha1(f"{normalize_match(title)}|{year or ''}".encode("utf-8")).hexdigest()[:12]
    return f"title:{digest}"


def group_hits(hits: list[SourceHit]) -> list[list[SourceHit]]:
    from app.utils.similarity import same_work_hit

    groups: list[list[SourceHit]] = []
    for hit in hits:
        placed = False
        for group in groups:
            anchor = group[0]
            shared_isbn = bool(set(hit.isbn) & set(anchor.isbn))
            if shared_isbn or same_work_hit(hit.doi, anchor.doi, hit.title, anchor.title, hit.year, anchor.year, hit.pmid, anchor.pmid):
                group.append(hit)
                placed = True
                break
        if not placed:
            groups.append([hit])
    return groups


def describe_conflicts(record: CanonicalRecord) -> list[dict]:
    conflicts = []
    for name, field in record.fields.items():
        if field.conflict or field.status in {"conflicting", "unresolved"}:
            conflicts.append(
                {
                    "field": name,
                    "selected": field.selected,
                    "alternatives": field.alternatives,
                    "sources": field.sources,
                    "status": field.status,
                }
            )
    return conflicts


def public_metadata(record: CanonicalRecord) -> dict:
    return {
        "record_id": record.record_id,
        "type": record.type,
        "title": record.title,
        "subtitle": record.subtitle,
        "authors": [author.model_dump() for author in record.authors],
        "editors": [author.model_dump() for author in record.editors],
        "publication": {
            "journal": record.journal,
            "journal_abbrev": record.journal_abbrev,
            "year": record.year,
            "month": record.month,
            "day": record.day,
            "volume": record.volume,
            "issue": record.issue,
            "pages": record.pages,
            "container_title": record.container_title,
        },
        "publisher": record.publisher,
        "identifiers": {
            "doi": record.doi,
            "pmid": record.pmid,
            "issn": record.issn,
            "isbn": record.isbn,
        },
        "urls": record.urls,
        "abstract": record.abstract,
        "sources": record.sources_used,
        "status_flags": record.status_flags,
        "verification": {
            "score": record.confidence,
            "fields": {name: field.model_dump() for name, field in record.fields.items()},
        },
    }


def candidate_summary(record: CanonicalRecord, candidate_id: str | None = None) -> dict:
    authors = authors_display(record.authors)
    return {
        "id": candidate_id,
        "record_id": record.record_id,
        "title": record.title,
        "authors": authors,
        "year": record.year,
        "journal": record.journal or record.publisher,
        "doi": record.doi,
        "type": record.type,
        "match_score": record.match_score,
        "confidence": record.confidence,
        "sources": record.sources_used,
        "status_flags": record.status_flags,
    }


_ = collapse
