# Bibliography Intelligence Agent — Development Plan

## 1. Project Vision

Build an evidence-first AI Bibliography Intelligence Agent that accepts a title, DOI, URL, PMID, ISBN, or existing citation and:

1. Detects and normalizes the input.
2. Searches authoritative bibliographic sources.
3. Retrieves and reconciles metadata.
4. Verifies bibliographic evidence.
5. Converts the canonical metadata into BibTeX.
6. Formats references into requested citation styles.
7. Validates the generated output against verified metadata.
8. Self-corrects when validation detects errors.
9. Supports single-reference and batch workflows.
10. Exports results in useful research formats.

Core principle:

> Find → Verify → Normalize → Generate → Format → Validate → Self-correct.

The LLM should not be the source of truth for bibliographic metadata. External bibliographic evidence should be the source of truth; the LLM should primarily support intent understanding, reconciliation, and style-aware formatting where needed.

---

## 2. Supported Inputs

The agent should accept:

- DOI
- DOI URL
- Article title
- Web URL
- PMID
- ISBN
- Existing citation/reference
- Natural-language request
- Multiple references / batch input

Examples:

```text
10.1038/s41586-020-2649-2
```

```text
https://doi.org/10.xxxx/xxxxx
```

```text
CRISPR-Cas9 genome editing
```

```text
"Give me this paper in Vancouver style"
```

---

## 3. Supported Citation Styles

Initial release:

- APA 7
- Chicago
- MLA 9
- Harvard
- Vancouver / NLM

Future:

- IEEE
- ACS
- AMA
- Turabian
- Nature
- Cell
- Elsevier
- Springer
- Institutional/custom styles

The style system should be modular:

```text
StyleEngine
├── APAFormatter
├── ChicagoFormatter
├── MLAFormatter
├── HarvardFormatter
├── VancouverFormatter
├── IEEEFormatter
├── ACSFormatter
└── AMAFormatter
```

---

# 4. High-Level Architecture

```text
                         USER
                           |
                           v
                +---------------------+
                | Input Intelligence  |
                +----------+----------+
                           |
                           v
                +---------------------+
                | Search Orchestrator |
                +----------+----------+
                           |
             +-------------+-------------+
             |             |             |
             v             v             v
         Crossref       PubMed        DataCite
             |             |             |
             +-------------+-------------+
                           |
                           v
                +---------------------+
                | Metadata Reconciler |
                +----------+----------+
                           |
                           v
                +---------------------+
                | Evidence Validator  |
                +----------+----------+
                           |
                           v
                +---------------------+
                | Canonical Metadata  |
                +----------+----------+
                           |
             +-------------+-------------+
             |                           |
             v                           v
       BibTeX Engine              Style Engine
             |                           |
             +-------------+-------------+
                           |
                           v
                +---------------------+
                | Quality Validator   |
                +----------+----------+
                           |
                     PASS / FAIL
                           |
                    +------+------+
                    |             |
                   PASS          FAIL
                    |             |
                    v             v
                 OUTPUT      Self-correction
                                  |
                                  +----> Validate
```

---

# 5. Core Modules

## Module 1 — Input Intelligence

Responsibilities:

- Detect input type.
- Normalize DOI.
- Extract DOI from URLs.
- Detect requested citation styles.
- Detect batch requests.
- Interpret natural-language instructions.
- Identify requested output formats.
- Preserve user constraints.

Example normalized request:

```json
{
  "source_type": "doi",
  "source_value": "10.xxxx/xxxxx",
  "requested_styles": ["apa", "vancouver"],
  "outputs": ["citation", "bibtex"],
  "verify": true
}
```

---

# 6. Module 2 — Search Orchestrator

Do not rely on a single metadata source.

Recommended source hierarchy:

### General scholarly literature

1. Crossref
2. OpenAlex
3. DataCite
4. Publisher metadata

### Biomedical literature

1. PubMed
2. Europe PMC
3. Crossref
4. Publisher metadata

### Books

1. ISBN metadata
2. Open Library
3. Publisher
4. Library catalogs

The orchestrator should return multiple candidates when searching by title.

Example:

```json
{
  "candidates": [
    {
      "id": "candidate_1",
      "match_score": 0.98
    },
    {
      "id": "candidate_2",
      "match_score": 0.71
    }
  ]
}
```

Never blindly accept the first title-search result.

---

# 7. Module 3 — Metadata Reconciliation

This is a critical component.

Different sources can disagree.

Example:

```text
Crossref  → Year: 2024
PubMed    → Year: 2024
Publisher → Year: 2023
```

The reconciler should:

1. Compare fields.
2. Identify conflicts.
3. Determine the strongest evidence.
4. Record the selected value.
5. Preserve the conflicting values.
6. Assign confidence.
7. Flag unresolved conflicts.

Example:

```json
{
  "year": {
    "selected": 2024,
    "confidence": 0.91,
    "sources": ["PubMed", "Crossref"],
    "conflict": true,
    "alternatives": [2023]
  }
}
```

Never silently hide important metadata conflicts.

---

# 8. Module 4 — Canonical Metadata Schema

All sources should eventually be converted into one internal schema.

Recommended structure:

```json
{
  "record_id": "...",
  "type": "journal_article",

  "title": "...",
  "subtitle": "...",

  "authors": [
    {
      "given": "John",
      "family": "Smith",
      "suffix": null,
      "orcid": "..."
    }
  ],

  "publication": {
    "journal": "...",
    "year": 2024,
    "volume": "25",
    "issue": "4",
    "pages": "123-135"
  },

  "publisher": "...",

  "identifiers": {
    "doi": "10.xxxx/xxxxx",
    "pmid": "...",
    "issn": "...",
    "isbn": "..."
  },

  "urls": [
    "..."
  ],

  "verification": {
    "score": 0.96
  }
}
```

This canonical record becomes the single source of truth for all downstream outputs.

---

# 9. Module 5 — Evidence & Verification

Every important field should have a verification state.

Example:

```json
{
  "verification": {
    "doi": {
      "status": "verified"
    },
    "title": {
      "status": "verified"
    },
    "authors": {
      "status": "verified"
    },
    "journal": {
      "status": "verified"
    },
    "year": {
      "status": "verified"
    },
    "pages": {
      "status": "partially_verified"
    }
  }
}
```

Recommended status values:

- verified
- partially_verified
- conflicting
- missing
- unresolved

Calculate an overall confidence score.

Example:

```text
Metadata confidence: 96%
```

---

# 10. Module 6 — Deterministic BibTeX Engine

BibTeX should preferably be generated from structured canonical metadata rather than generated freely by the LLM.

Example:

```bibtex
@article{smith2024crispr,
  author = {Smith, John and Jones, Mary},
  title = {CRISPR Genome Editing},
  journal = {Nature},
  year = {2024},
  volume = {25},
  number = {4},
  pages = {123-135},
  doi = {10.xxxx/xxxxx}
}
```

Supported entry types:

- article
- book
- inbook
- incollection
- inproceedings
- proceedings
- thesis
- report
- misc

---

# 11. Citation Key Generator

Allow configurable citation keys.

Default:

```text
{first_author}{year}{first_title_word}
```

Example:

```text
Smith2024CRISPR
```

Alternative formats:

```text
Smith_Jones_2024
Smith2024GenomeEditing
Smith2024CRISPRa
```

Ensure duplicate keys are detected and resolved.

---

# 12. Module 7 — Citation Style Engine

Each style should have its own formatter.

Example API:

```python
APAFormatter.format(metadata)

VancouverFormatter.format(metadata)

MLAFormatter.format(metadata)

ChicagoFormatter.format(metadata)

HarvardFormatter.format(metadata)
```

Do not mix formatting rules across styles.

Each formatter should have tests for:

- 1 author
- 2 authors
- 3+ authors
- group author
- missing author
- article
- book
- chapter
- conference paper
- website
- DOI
- URL
- missing pages
- online-first publication
- multiple publication dates

---

# 13. Module 8 — Quality Validation

Use two levels of validation.

## A. Metadata validation

Check:

- DOI syntax
- DOI resolution where possible
- title presence
- author presence
- year
- journal
- volume
- issue
- pages
- identifier consistency

## B. Citation validation

Check:

- author order
- author formatting
- year placement
- title capitalization
- journal formatting
- volume/issue
- page range
- DOI/URL
- style-specific punctuation

---

# 14. Hallucination Detection

Compare every generated citation against canonical metadata.

Example:

```text
Canonical metadata:

Pages = 125-131

Generated citation:

Pages = 125-139
```

Validator:

```text
ERROR:
Generated page range does not match verified metadata.
```

Other checks:

```text
Generated author not in canonical record
Generated year differs from canonical record
Generated journal differs
Generated DOI differs
Generated title contains unsupported information
```

The LLM must never be allowed to silently invent missing bibliographic information.

---

# 15. Self-Correction Loop

Implement:

```text
Generate
   |
   v
Validate
   |
   +---- PASS ----> Final Output
   |
   +---- FAIL
          |
          v
       Diagnose
          |
          v
       Regenerate
          |
          v
       Validate
```

Recommended maximum:

```python
MAX_RETRIES = 2
```

After maximum retries, return the best available result with a warning.

---

# 16. Natural-Language Interface

Users should not need special commands.

Examples:

```text
Find this DOI and give me APA.
```

```text
Convert this title to Vancouver.
```

```text
Give me APA, MLA and Vancouver.
```

```text
Generate BibTeX and Chicago citation.
```

```text
Check whether this citation is correct.
```

```text
Find the DOI for this paper.
```

```text
Convert these 50 references into Vancouver.
```

---

# 17. Multi-Style Output

Example request:

```text
DOI: 10.xxxx/xxxxx

Styles:
APA
MLA
Vancouver
```

Output:

```text
APA
────────────────────
...

MLA
────────────────────
...

Vancouver
────────────────────
...

BibTeX
────────────────────
@article{...}
```

---

# 18. Batch Processing

Support:

```text
DOI 1
DOI 2
DOI 3
...
DOI 100
```

Processing screen:

```text
Processing 100 references

██████████████████░░ 90%

90 verified
7 partially verified
3 unresolved
```

Outputs:

```text
references.bib
references.ris
references.csv
references.json
references.txt
references.docx
```

---

# 19. Duplicate Detection

Detect duplicates using:

### Strong match

- DOI

### Medium match

- PMID
- ISBN

### Fuzzy match

- title similarity
- author similarity
- year
- journal

Example:

```text
Possible duplicate

Smith et al. 2024
Smith et al. 2024

Similarity: 96.4%
```

Allow:

```text
[Merge]
[Keep Both]
[Ignore]
```

---

# 20. Human-in-the-Loop

If confidence is low, do not guess.

Example:

```text
LOW CONFIDENCE

Two publications match your title.

A
Smith et al. 2024
Nature Biotechnology
Confidence: 94%

B
Smith et al. 2023
Nature Communications
Confidence: 61%

[Use A]
[Use B]
[Search Again]
```

Recommended threshold:

```text
>= 0.90  → automatic
0.70–0.89 → warning
< 0.70 → user confirmation
```

These thresholds should be configurable rather than treated as universal truth.

---

# 21. Research Library Mode

Future feature:

```text
My Research Library
│
├── Nanobiotechnology
├── Drug Delivery
├── Cancer Theranostics
├── Biosensors
├── Tissue Engineering
└── Spectroscopy
```

Users can ask:

```text
Show references related to magnetic nanoparticles.
```

```text
Export my nanomedicine references in Vancouver.
```

```text
Find duplicate references.
```

```text
Find references missing DOI.
```

---

# 22. Recommended Technology Stack

## Prototype

```text
Python
OpenAI API
Crossref API
PubMed API
DataCite API
OpenAlex API
SQLite
FastAPI
```

## Production

```text
Frontend
React / Next.js

Backend
FastAPI

Agent Layer
Python

LLM
OpenAI API

Database
PostgreSQL

Cache
Redis

Background Jobs
Celery / RQ

Search
OpenAlex / Elasticsearch / PostgreSQL FTS

Storage
S3-compatible object storage
```

---

# 23. Suggested Project Structure

```text
bibliography-agent/
│
├── app/
│   ├── main.py
│   │
│   ├── agents/
│   │   ├── input_agent.py
│   │   ├── search_agent.py
│   │   ├── reconciliation_agent.py
│   │   ├── verification_agent.py
│   │   ├── citation_agent.py
│   │   └── validation_agent.py
│   │
│   ├── sources/
│   │   ├── crossref.py
│   │   ├── pubmed.py
│   │   ├── datacite.py
│   │   ├── openalex.py
│   │   └── publisher.py
│   │
│   ├── formats/
│   │   ├── bibtex.py
│   │   ├── apa.py
│   │   ├── chicago.py
│   │   ├── mla.py
│   │   ├── harvard.py
│   │   └── vancouver.py
│   │
│   ├── validators/
│   │   ├── metadata.py
│   │   ├── citation.py
│   │   ├── bibtex.py
│   │   └── hallucination.py
│   │
│   ├── models/
│   │   ├── metadata.py
│   │   ├── request.py
│   │   └── response.py
│   │
│   └── utils/
│       ├── doi.py
│       ├── authors.py
│       └── similarity.py
│
├── tests/
│   ├── test_crossref.py
│   ├── test_bibtex.py
│   ├── test_apa.py
│   ├── test_vancouver.py
│   └── test_validation.py
│
├── data/
│
├── .env
├── requirements.txt
├── README.md
└── plan.md
```

---

# 24. API Design

Primary endpoint:

```http
POST /api/v1/citation
```

Request:

```json
{
  "input": "10.xxxx/xxxxx",
  "styles": [
    "apa",
    "vancouver"
  ],
  "include_bibtex": true,
  "validate": true
}
```

Response:

```json
{
  "status": "success",

  "source": {
    "type": "doi",
    "value": "10.xxxx/xxxxx"
  },

  "metadata": {},

  "verification": {
    "score": 0.97
  },

  "citations": {
    "apa": "...",
    "vancouver": "..."
  },

  "bibtex": "...",

  "validation": {
    "status": "passed",
    "warnings": []
  }
}
```

Additional endpoints:

```text
POST /api/v1/search
POST /api/v1/verify
POST /api/v1/bibtex
POST /api/v1/format
POST /api/v1/batch
POST /api/v1/duplicates
GET  /api/v1/styles
```

---

# 25. UI Design

Main interface:

```text
╔══════════════════════════════════════════════════════╗
║          BIBLIOGRAPHY INTELLIGENCE AGENT             ║
╠══════════════════════════════════════════════════════╣
║                                                      ║
║ Paste title / DOI / URL / PMID / ISBN                ║
║                                                      ║
║ ┌──────────────────────────────────────────────────┐ ║
║ │ 10.xxxx/xxxxx                                   │ ║
║ └──────────────────────────────────────────────────┘ ║
║                                                      ║
║ Citation style                                      ║
║                                                      ║
║ [APA] [Chicago] [MLA] [Harvard] [Vancouver]         ║
║                                                      ║
║ ☑ Verify metadata                                   ║
║ ☑ Generate BibTeX                                   ║
║ ☑ Validate output                                   ║
║                                                      ║
║              [ GENERATE CITATION ]                  ║
╚══════════════════════════════════════════════════════╝
```

Result:

```text
✓ VERIFIED

Metadata confidence: 97%

DOI          ✓
Title        ✓
Authors      ✓
Journal      ✓
Year         ✓
Pages        ✓

APA 7
────────────────────────────────────────
...

BibTeX
────────────────────────────────────────
@article{...}

[Copy] [Download .bib]
```

---

# 26. Advanced Features — Phase 2

Add:

- DOI resolver
- PMID ↔ DOI mapping
- ISBN lookup
- ORCID enrichment
- Journal ISSN validation
- Journal abbreviation service
- Citation deduplication
- Reference sorting
- Alphabetical ordering
- Vancouver numbering
- In-text citation generation
- Citation completeness checking
- Reference-list consistency checking
- Missing DOI detection
- Broken DOI detection
- Retracted-paper detection
- Preprint vs published-version detection
- Online-first vs issue-date handling
- Author ORCID enrichment

---

# 27. Advanced Features — Phase 3

Research assistant functionality:

```text
"Find all papers about magnetic nanoparticles
published between 2020 and 2025."
```

Then:

```text
Search
↓
Deduplicate
↓
Verify
↓
Classify
↓
Generate references
↓
Export
```

Potential outputs:

```text
literature.csv
literature.bib
literature.ris
literature.json
literature.docx
```

---

# 28. Retraction and Publication Status

For research reliability, add a publication-status check.

Potential flags:

```text
✓ Published
⚠ Preprint
⚠ Early access
⚠ Metadata incomplete
⚠ Possible duplicate
⚠ Retracted / corrected
```

Do not alter the bibliographic record merely because a paper has a status flag; expose the status separately.

---

# 29. Observability

Every processing request should produce an internal trace:

```text
Request ID
    ↓
Input detection
    ↓
Search sources used
    ↓
Candidate scores
    ↓
Selected metadata
    ↓
Conflicts
    ↓
BibTeX generation
    ↓
Style generation
    ↓
Validation
    ↓
Corrections
    ↓
Final result
```

This is important for debugging and research transparency.

---

# 30. Security and Reliability

Implement:

- API-key protection
- rate limiting
- request validation
- URL safety checks
- timeout handling
- retry logic
- source caching
- audit logging
- prompt-injection protection for webpage content
- strict separation between retrieved text and agent instructions

Never treat text retrieved from a webpage as trusted instructions.

---

# 31. Testing Strategy

Create a benchmark dataset containing:

### Simple

- DOI with complete metadata
- title with exact match

### Difficult

- title with multiple matches
- missing DOI
- missing authors
- missing pages
- online-first articles
- conference papers
- books
- chapters
- websites

### Conflict cases

- Crossref vs PubMed year mismatch
- journal title mismatch
- author spelling mismatch
- pagination mismatch

### Adversarial cases

- malformed DOI
- fake DOI
- unrelated title
- duplicate records
- incomplete citation
- malicious webpage metadata

Measure:

```text
Metadata accuracy
DOI accuracy
Author accuracy
Title accuracy
Year accuracy
BibTeX validity
Style compliance
Hallucination rate
Duplicate detection accuracy
```

---

# 32. MVP Roadmap

## Phase 1 — Core Prototype

Implement:

- DOI detection
- title search
- URL detection
- Crossref
- canonical metadata
- BibTeX
- APA
- Vancouver
- validation

Target:

```text
Input → Search → BibTeX → APA/Vancouver → Validate
```

---

## Phase 2 — Multi-source Intelligence

Add:

- PubMed
- DataCite
- OpenAlex
- metadata reconciliation
- confidence score
- conflict detection

Target:

```text
Multi-source → Reconcile → Verify → Format
```

---

## Phase 3 — Full Citation Platform

Add:

- Chicago
- MLA
- Harvard
- IEEE
- ACS
- AMA
- batch processing
- duplicate detection
- exports
- research library

---

## Phase 4 — Research Intelligence

Add:

- literature search
- thematic classification
- citation-network analysis
- retraction detection
- systematic-review workflows
- reference completeness analysis
- thesis bibliography assistant

---

# 33. Ideal Final Workflow

The finished agent should behave like this:

```text
USER:

"Find the paper:
CRISPR-Cas9...
Give me APA and Vancouver,
generate BibTeX and verify it."


                    ↓

              INPUT AGENT

                    ↓

        Identify title + styles

                    ↓

          SEARCH ORCHESTRATOR

       ┌────────┬────────┬────────┐
       ↓        ↓        ↓        ↓
    Crossref PubMed DataCite OpenAlex

       └────────┬────────┴────────┘
                ↓

        METADATA RECONCILER

                ↓

          EVIDENCE CHECK

                ↓

       CANONICAL RECORD

                ↓
        ┌───────┴────────┐
        ↓                ↓
     BibTeX          Style Engine
                         ↓
                    APA + Vancouver

        └───────┬────────┘
                ↓

        OUTPUT VALIDATOR

                ↓

          PASS / CORRECT

                ↓

┌───────────────────────────────────────┐
│ VERIFIED                              │
│                                       │
│ Metadata confidence: 97%              │
│                                       │
│ APA                                   │
│ ...                                   │
│                                       │
│ Vancouver                             │
│ ...                                   │
│                                       │
│ BibTeX                                │
│ @article{...}                         │
└───────────────────────────────────────┘
```

---

# 34. Definition of Done

The MVP is considered complete when it can:

- [ ] Accept DOI
- [ ] Accept DOI URL
- [ ] Accept title
- [ ] Accept article URL
- [ ] Detect requested style
- [ ] Search Crossref
- [ ] Retrieve structured metadata
- [ ] Normalize metadata
- [ ] Generate deterministic BibTeX
- [ ] Generate APA
- [ ] Generate Vancouver
- [ ] Validate DOI
- [ ] Validate required fields
- [ ] Compare generated citation with metadata
- [ ] Detect hallucinated fields
- [ ] Report confidence
- [ ] Handle missing metadata
- [ ] Handle API failures
- [ ] Provide structured JSON
- [ ] Provide human-readable output
- [ ] Pass automated tests

---

# 35. Long-Term Vision

Transform the project from:

> "AI citation generator"

into:

> **"Evidence-verified bibliographic intelligence platform for researchers."**

The long-term architecture should support:

```text
          SEARCH
             ↓
        IDENTIFY
             ↓
         VERIFY
             ↓
        RECONCILE
             ↓
        STRUCTURE
             ↓
        CITE
             ↓
       VALIDATE
             ↓
       ORGANIZE
             ↓
        ANALYZE
```

The most important architectural rule remains:

> **The LLM should reason over bibliographic evidence, not invent bibliographic evidence.**
