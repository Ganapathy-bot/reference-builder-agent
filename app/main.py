"""FastAPI application for the bibliography intelligence agent."""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.agents.citation_agent import generate
from app.agents.input_agent import parse_input
from app.agents.search_agent import search
from app.config import get_settings
from app.db import Database
from app.formats.engine import normalize_styles, supported_styles
from app.models.metadata import CanonicalRecord
from app.models.request import BatchRequest, CitationRequest, LibrarySaveRequest
from app.utils.http import HttpClient


STATIC_DIR = Path(__file__).resolve().parent / "static"


@asynccontextmanager
async def lifespan(application: FastAPI):
    settings = get_settings()
    database = Database(settings.database_path)
    database.init()
    application.state.settings = settings
    application.state.database = database
    try:
        yield
    finally:
        database.close()


app = FastAPI(
    title="Reference Desk",
    description="Evidence-first reference lookup and citation formatting.",
    version="1.0.0",
    lifespan=lifespan,
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
async def home() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/v1/styles")
async def styles() -> list[dict[str, str]]:
    return supported_styles()


@app.post("/api/v1/citation")
async def create_citation(request: CitationRequest) -> dict[str, Any]:
    return await _create_citation(request)


@app.post("/api/v1/batch")
async def create_batch(request: BatchRequest) -> dict[str, Any]:
    items = [line.strip() for line in request.input.splitlines() if line.strip()]
    if not items:
        raise HTTPException(status_code=422, detail="Enter at least one reference.")
    limit = app.state.settings.batch_limit
    if len(items) > limit:
        raise HTTPException(status_code=413, detail=f"Batch limit is {limit} references.")
    results = []
    for item in items:
        results.append(
            await _create_citation(
                CitationRequest(
                    input=item,
                    styles=request.styles,
                    include_bibtex=request.include_bibtex,
                    validate=request.validate,
                )
            )
        )
    return {"status": "complete", "results": results}


@app.get("/api/v1/library")
async def list_library() -> list[dict[str, Any]]:
    return app.state.database.library_list()


@app.post("/api/v1/library")
async def save_to_library(request: LibrarySaveRequest) -> dict[str, Any]:
    try:
        CanonicalRecord.model_validate(request.record)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Invalid canonical metadata.") from exc
    return app.state.database.library_add(
        request.record,
        request.collection,
        request.citations,
        request.bibtex,
    )


@app.delete("/api/v1/library/{item_id}")
async def delete_from_library(item_id: str) -> dict[str, bool]:
    if not app.state.database.library_delete(item_id):
        raise HTTPException(status_code=404, detail="Library item not found.")
    return {"deleted": True}


async def _create_citation(request: CitationRequest) -> dict[str, Any]:
    settings = app.state.settings
    database: Database = app.state.database
    parsed = parse_input(request.input)
    try:
        chosen_styles = normalize_styles(request.styles or parsed.requested_styles)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    trace: list[dict[str, Any]] = [{"stage": "input", "source_type": parsed.source_type}]
    if request.candidate_id:
        candidate = database.get_candidate(request.candidate_id, settings.candidate_ttl_seconds)
        if candidate is None:
            raise HTTPException(status_code=404, detail="Candidate expired or was not found. Search again.")
        record = CanonicalRecord.model_validate(candidate)
        outcome = None
    else:
        async with HttpClient(
            database,
            settings.user_agent,
            timeout=settings.http_timeout,
            cache_ttl=settings.cache_ttl_seconds,
            miss_ttl=settings.miss_ttl_seconds,
        ) as client:
            outcome = await search(parsed, client, settings)
        trace.append(
            {
                "stage": "search",
                "decision": outcome.decision,
                "sources": outcome.source_timings,
                "errors": outcome.errors,
            }
        )
        if outcome.decision == "needs_confirmation":
            candidates = []
            for candidate_record in outcome.candidates[:5]:
                candidate_id = database.save_candidate(candidate_record.model_dump(mode="json"))
                candidates.append(
                    {
                        "candidate_id": candidate_id,
                        "metadata": candidate_record.model_dump(mode="json"),
                    }
                )
            database.save_trace("", request.input, "needs_confirmation", trace)
            return {
                "status": "needs_confirmation",
                "source": {"type": parsed.source_type, "value": parsed.source_value},
                "message": outcome.warning,
                "candidates": candidates,
                "source_errors": outcome.errors,
            }
        if outcome.selected is None:
            database.save_trace("", request.input, "not_found", trace)
            return {
                "status": "not_found",
                "source": {"type": parsed.source_type, "value": parsed.source_value},
                "message": outcome.warning or "No matching bibliographic record was found.",
                "source_errors": outcome.errors,
            }
        record = outcome.selected

    generated = generate(
        record,
        chosen_styles,
        include_bibtex=request.include_bibtex,
        validate=request.validate,
        max_retries=settings.max_retries,
    )
    trace.append({"stage": "format", "styles": chosen_styles})
    request_id = uuid.uuid4().hex
    database.save_trace(request_id, request.input, "success", trace)
    response = {
        "request_id": request_id,
        "status": "success",
        "source": {"type": parsed.source_type, "value": parsed.source_value},
        "metadata": record.model_dump(mode="json"),
        "verification": {"score": record.confidence, "flags": record.status_flags},
        "citations": generated["citations"],
        "citations_html": generated["citations_html"],
        "citation_notes": generated["citation_notes"],
        "in_text": generated["in_text"],
        "bibtex": generated["bibtex"],
        "validation": generated["validation"],
        "warnings": generated["warnings"] + ([outcome.warning] if outcome and outcome.warning else []),
        "sources": record.sources_used,
        "source_timings": outcome.source_timings if outcome else [],
    }
    return response