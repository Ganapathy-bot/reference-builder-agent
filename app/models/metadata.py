"""Canonical bibliographic records and source hits."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class Author(BaseModel):
    given: str | None = None
    family: str
    suffix: str | None = None
    orcid: str | None = None
    is_group: bool = False


class FieldValue(BaseModel):
    """One reconciled field, including disagreement that must stay visible."""

    selected: Any = None
    confidence: float = 0.0
    sources: list[str] = Field(default_factory=list)
    conflict: bool = False
    alternatives: list[Any] = Field(default_factory=list)
    status: str = "missing"


class SourceHit(BaseModel):
    """A single metadata record as returned by one external source."""

    source: str
    source_id: str | None = None
    match_score: float = 1.0
    type: str = "journal_article"
    title: str | None = None
    subtitle: str | None = None
    authors: list[Author] = Field(default_factory=list)
    editors: list[Author] = Field(default_factory=list)
    year: int | None = None
    alt_years: list[int] = Field(default_factory=list)
    month: int | None = None
    day: int | None = None
    journal: str | None = None
    journal_abbrev: str | None = None
    volume: str | None = None
    issue: str | None = None
    pages: str | None = None
    publisher: str | None = None
    container_title: str | None = None
    doi: str | None = None
    pmid: str | None = None
    isbn: list[str] = Field(default_factory=list)
    issn: list[str] = Field(default_factory=list)
    url: str | None = None
    abstract: str | None = None
    retracted: bool = False
    preprint: bool = False


class CanonicalRecord(BaseModel):
    """Single internal record used by every formatter."""

    record_id: str
    type: str = "journal_article"
    title: str = ""
    subtitle: str | None = None
    authors: list[Author] = Field(default_factory=list)
    editors: list[Author] = Field(default_factory=list)
    year: int | None = None
    month: int | None = None
    day: int | None = None
    journal: str | None = None
    journal_abbrev: str | None = None
    volume: str | None = None
    issue: str | None = None
    pages: str | None = None
    publisher: str | None = None
    container_title: str | None = None
    doi: str | None = None
    pmid: str | None = None
    isbn: list[str] = Field(default_factory=list)
    issn: list[str] = Field(default_factory=list)
    urls: list[str] = Field(default_factory=list)
    abstract: str | None = None
    confidence: float = 0.0
    match_score: float = 1.0
    fields: dict[str, FieldValue] = Field(default_factory=dict)
    status_flags: list[str] = Field(default_factory=list)
    sources_used: list[str] = Field(default_factory=list)
    retracted: bool = False
    preprint: bool = False


class ParsedInput(BaseModel):
    raw_input: str
    source_type: str
    source_value: str
    requested_styles: list[str] = Field(default_factory=list)
    outputs: list[str] = Field(default_factory=lambda: ["citation", "bibtex"])
    intent: str = "cite"
    items: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
