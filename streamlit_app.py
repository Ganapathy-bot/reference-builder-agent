"""Streamlit interface for evidence-first citation generation."""

from __future__ import annotations

import asyncio
import html
from typing import Any

import streamlit as st

from app.agents.citation_agent import generate
from app.agents.input_agent import parse_input
from app.agents.search_agent import search
from app.config import get_settings
from app.db import Database
from app.formats.engine import normalize_styles, supported_styles
from app.models.metadata import CanonicalRecord
from app.utils.http import HttpClient


st.set_page_config(
    page_title="Reference Desk",
    page_icon="R",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    :root { --desk-green: #183c31; --desk-coral: #c5533d; --desk-muted: #6b756e; }
    .stApp { background: #f8faf7; }
    [data-testid="stSidebar"] { background: var(--desk-green); }
    [data-testid="stSidebar"] * { color: #edf4ee; }
    [data-testid="stSidebar"] [data-testid="stMultiSelect"] * { color: #202923; }
    [data-testid="stSidebar"] [data-testid="stCheckbox"] label { color: #edf4ee; }
    .desk-brand { display: flex; align-items: center; gap: 12px; margin: 0 0 34px; color: #fff; }
    .desk-mark { display: grid; place-items: center; width: 38px; height: 38px; border: 1px solid #bed1c3; font: 22px Georgia, serif; }
    .desk-mark span { color: #e7d66f; }
    .desk-name { font: 600 10px/1.2 monospace; letter-spacing: .08em; }
    .desk-eyebrow { margin: 0 0 8px; color: var(--desk-coral); font: 10px monospace; letter-spacing: .12em; }
    .desk-title { margin: 0; color: #202923; font: 400 42px/1.05 Georgia, serif; }
    .desk-deck { margin: 8px 0 28px; color: var(--desk-muted); font-size: 14px; }
    .input-frame { padding: 18px; border: 1px solid #d6ded7; border-top: 3px solid var(--desk-coral); background: #fff; }
    .result-heading { margin: 0 0 5px; color: #202923; font: 400 22px Georgia, serif; }
    .citation-label { margin: 16px 0 5px; color: #315f4d; font: 10px monospace; letter-spacing: .1em; text-transform: uppercase; }
    div[data-testid="stMetric"] { padding: 12px; border: 1px solid #d6ded7; background: #fff; }
    .stButton > button[kind="primary"], .stFormSubmitButton > button[kind="primary"] { background: var(--desk-coral); border-color: var(--desk-coral); }
    .stButton > button, .stDownloadButton > button { border-radius: 3px; }
    @media (max-width: 700px) { .desk-title { font-size: 34px; } }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource
def database() -> Database:
    settings = get_settings()
    db = Database(settings.database_path)
    db.init()
    return db


async def search_references(raw_inputs: list[str], db: Database, settings: Any) -> list[tuple[str, Any, Any]]:
    matches = []
    async with HttpClient(
        db,
        settings.user_agent,
        timeout=settings.http_timeout,
        cache_ttl=settings.cache_ttl_seconds,
        miss_ttl=settings.miss_ttl_seconds,
    ) as client:
        for raw_input in raw_inputs:
            parsed = parse_input(raw_input)
            outcome = await search(parsed, client, settings)
            matches.append((raw_input, parsed, outcome))
    return matches


def build_result(
    raw_input: str,
    parsed: Any,
    outcome: Any,
    styles: list[str],
    include_bibtex: bool,
    validate: bool,
) -> dict[str, Any]:
    if outcome.decision == "needs_confirmation":
        return {
            "status": "needs_confirmation",
            "input": raw_input,
            "source": {"type": parsed.source_type, "value": parsed.source_value},
            "message": outcome.warning,
            "candidates": [record.model_dump(mode="json") for record in outcome.candidates[:5]],
        }
    if outcome.selected is None:
        return {
            "status": "not_found",
            "input": raw_input,
            "message": outcome.warning or "No matching bibliographic record was found.",
            "source_errors": outcome.errors,
        }
    return format_record(outcome.selected, styles, include_bibtex, validate, outcome.warning)


def format_record(
    record: CanonicalRecord,
    styles: list[str],
    include_bibtex: bool,
    validate: bool,
    warning: str | None = None,
) -> dict[str, Any]:
    formatted = generate(
        record,
        styles,
        include_bibtex=include_bibtex,
        validate=validate,
        max_retries=get_settings().max_retries,
    )
    warnings = list(formatted["warnings"])
    if warning:
        warnings.append(warning)
    return {
        "status": "success",
        "metadata": record.model_dump(mode="json"),
        "citations": formatted["citations"],
        "bibtex": formatted["bibtex"],
        "validation": formatted["validation"],
        "warnings": warnings,
    }


def render_result(result: dict[str, Any], index: int, styles: list[str], include_bibtex: bool, validate: bool) -> None:
    if result["status"] == "needs_confirmation":
        st.warning(result.get("message") or "Choose the record that matches your reference.")
        candidates = result["candidates"]
        labels = [
            f"{candidate.get('title') or 'Untitled'} · {candidate.get('year') or 'n.d.'} · {candidate.get('journal') or candidate.get('publisher') or 'Publication unknown'}"
            for candidate in candidates
        ]
        selected_index = st.selectbox(
            "Possible matches",
            options=range(len(candidates)),
            format_func=lambda choice: labels[choice],
            key=f"candidate-{index}",
        )
        if st.button("Use selected record", type="primary", key=f"use-candidate-{index}"):
            record = CanonicalRecord.model_validate(candidates[selected_index])
            st.session_state.reference_results[index] = format_record(record, styles, include_bibtex, validate)
            st.rerun()
        return

    if result["status"] != "success":
        st.error(result.get("message") or "No matching bibliographic record was found.")
        for source_error in result.get("source_errors", []):
            st.caption(f"{source_error.get('source')}: {source_error.get('message')}")
        return

    metadata = result["metadata"]
    authors = metadata.get("authors") or []
    author_names = ", ".join(
        " ".join(part for part in (author.get("given"), author.get("family")) if part)
        for author in authors[:4]
    )
    if len(authors) > 4:
        author_names += f", and {len(authors) - 4} more"
    with st.container(border=True):
        st.markdown(f"<h2 class='result-heading'>{html.escape(metadata.get('title') or 'Untitled reference')}</h2>", unsafe_allow_html=True)
        details = [part for part in (author_names, str(metadata.get("year") or ""), metadata.get("journal") or metadata.get("publisher")) if part]
        st.caption(" · ".join(details))
        metric, save = st.columns([1, 3])
        metric.metric("Metadata confidence", f"{round((metadata.get('confidence') or 0) * 100)}%")
        with save:
            st.write("")
            if st.button("Save to library", key=f"save-{index}"):
                database().library_add(metadata, "Inbox", result["citations"], result.get("bibtex"))
                st.success("Saved to your library.")
        for style, citation in result["citations"].items():
            st.markdown(f"<div class='citation-label'>{html.escape(style)}</div>", unsafe_allow_html=True)
            st.code(citation, language=None)
        if result.get("bibtex"):
            st.markdown("<div class='citation-label'>BibTeX</div>", unsafe_allow_html=True)
            st.code(result["bibtex"], language="bibtex")
            st.download_button(
                "Download .bib",
                result["bibtex"],
                file_name="reference.bib",
                mime="application/x-bibtex",
                key=f"download-{index}",
            )
        if result.get("warnings"):
            for warning in result["warnings"]:
                st.warning(warning)
        with st.expander("Verified metadata"):
            st.json(
                {
                    "DOI": metadata.get("doi"),
                    "Sources": metadata.get("sources_used", []),
                    "Fields": metadata.get("fields", {}),
                    "Validation": result.get("validation", {}),
                }
            )


def render_library(db: Database) -> None:
    records = db.library_list()
    st.markdown("<div class='desk-eyebrow'>YOUR COLLECTION</div><h1 class='desk-title'>Saved library</h1>", unsafe_allow_html=True)
    if not records:
        st.info("Your saved references will appear here.")
        return
    bibtex = "\n\n".join(item["bibtex"] for item in records if item.get("bibtex"))
    if bibtex:
        st.download_button("Export library as BibTeX", bibtex, "references.bib", "application/x-bibtex")
    for item in records:
        with st.container(border=True):
            st.markdown(f"<h2 class='result-heading'>{html.escape(item.get('title') or 'Untitled reference')}</h2>", unsafe_allow_html=True)
            st.caption(" · ".join(str(part) for part in (item.get("year"), item.get("doi"), item.get("collection")) if part))
            remove, citation = st.columns([1, 5])
            with remove:
                if st.button("Remove", key=f"remove-{item['id']}"):
                    db.library_delete(item["id"])
                    st.rerun()
            with citation:
                st.write(next(iter(item.get("citations", {}).values()), ""))


db = database()
with st.sidebar:
    st.markdown("<div class='desk-brand'><div class='desk-mark'>R<span>/</span></div><div class='desk-name'>REFERENCE<br>DESK</div></div>", unsafe_allow_html=True)
    section = st.radio("Workspace", ["New reference", "Saved library"], label_visibility="collapsed")
    st.divider()
    style_labels = {style["id"]: style["label"] for style in supported_styles()}
    selected_labels = st.multiselect("Citation styles", list(style_labels.values()), default=["APA 7"])
    batch_mode = st.checkbox("Batch mode", help="Enter one reference on each line.")
    include_bibtex = st.checkbox("Include BibTeX", value=True)
    validate_output = st.checkbox("Validate output", value=True)
    st.divider()
    st.caption("Evidence from Crossref · OpenAlex · DataCite · PubMed")

if section == "Saved library":
    render_library(db)
else:
    st.markdown("<div class='desk-eyebrow'>LOOK UP & FORMAT</div><h1 class='desk-title'>New reference</h1><p class='desk-deck'>Search verified scholarly records and shape a citation.</p>", unsafe_allow_html=True)
    with st.form("reference-search", clear_on_submit=False):
        raw_input = st.text_area(
            "Reference input",
            height=145,
            placeholder="Paste a DOI, publication title, URL, PMID, ISBN, or existing citation...",
        )
        submitted = st.form_submit_button("Search & generate", type="primary", use_container_width=True)

    if submitted:
        styles = normalize_styles([style_id for style_id, label in style_labels.items() if label in selected_labels])
        lines = [line.strip() for line in raw_input.splitlines() if line.strip()]
        inputs = lines if batch_mode and len(lines) > 1 else [raw_input.strip()]
        if not raw_input.strip():
            st.error("Enter a DOI, title, URL, PMID, ISBN, or citation first.")
        elif len(inputs) > get_settings().batch_limit:
            st.error(f"Batch limit is {get_settings().batch_limit} references.")
        elif not selected_labels:
            st.error("Choose at least one citation style.")
        else:
            with st.spinner(f"Searching {len(inputs)} reference{'s' if len(inputs) != 1 else ''} across scholarly sources…"):
                try:
                    found = asyncio.run(search_references(inputs, db, get_settings()))
                    st.session_state.reference_styles = styles
                    st.session_state.reference_include_bibtex = include_bibtex
                    st.session_state.reference_validate = validate_output
                    st.session_state.reference_results = [
                        build_result(raw, parsed, outcome, styles, include_bibtex, validate_output)
                        for raw, parsed, outcome in found
                    ]
                except Exception as exc:
                    st.error(f"Lookup failed: {exc}")

    for index, result in enumerate(st.session_state.get("reference_results", [])):
        render_result(
            result,
            index,
            st.session_state.get("reference_styles", ["apa"]),
            st.session_state.get("reference_include_bibtex", True),
            st.session_state.get("reference_validate", True),
        )