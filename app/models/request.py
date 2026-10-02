"""API request bodies."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class CitationRequest(BaseModel):
    input: str = Field(min_length=1, max_length=20_000)
    styles: list[str] | None = None
    include_bibtex: bool = True
    validate: bool = True
    verify: bool = True
    candidate_id: str | None = None


class BatchRequest(BaseModel):
    input: str = Field(min_length=1, max_length=100_000)
    styles: list[str] | None = None
    include_bibtex: bool = True
    validate: bool = True
    stream: bool = False


class FormatRequest(BaseModel):
    metadata: dict[str, Any]
    styles: list[str] = Field(default_factory=lambda: ["apa"])
    include_bibtex: bool = True
    validate: bool = True


class ExportRequest(BaseModel):
    records: list[dict[str, Any]] = Field(default_factory=list)
    ids: list[str] = Field(default_factory=list)
    format: str = "bib"
    styles: list[str] = Field(default_factory=lambda: ["apa"])


class LibrarySaveRequest(BaseModel):
    record: dict[str, Any]
    collection: str = "Inbox"
    citations: dict[str, str] = Field(default_factory=dict)
    bibtex: str | None = None


class DuplicateResolveRequest(BaseModel):
    action: str
    ids: list[str] = Field(min_length=2, max_length=2)
