# CLAUDE.md — BRD Agent Project

> Hand this file to a new Claude session to continue development from where we left off.

---

## What This Project Is

A **stateless Python backend service** that receives a meeting transcript (`.docx` or `.vtt`) from **Power Automate**, extracts structured BRD content using **Azure AI Foundry (GPT-4o mini)**, and returns a filled **company `.docx` BRD template** as a base64-encoded response — which Power Automate decodes and sends as an email attachment.

No frontend. No database. No job queue. Single synchronous HTTP request end-to-end.

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Language | Python 3.11 |
| Package Manager | Poetry |
| API Framework | FastAPI |
| AI Model | Azure AI Foundry — GPT-4o mini |
| Azure SDK | `azure-ai-inference` |
| Document Generation | `python-docx` |
| Validation | Pydantic v2 |
| Logging | Loguru |
| Retry Logic | Tenacity |
| Testing | Pytest + pytest-asyncio |
| Runtime | Uvicorn |

---

## BRD Output Structure (Fixed Company Template)

All 8 sections always present in output:

| # | Section | Format |
|---|---------|--------|
| 1 | Business Objectives | Bullet list |
| 2 | In Scope | Bullet list |
| 3 | Out of Scope | Bullet list |
| 4 | Functional Requirements | Table: ID (FR-001), Description, Priority |
| 5 | Non-Functional Requirements | Table: ID (NFR-001), Category, Description |
| 6 | Assumptions | Bullet list |
| 7 | Constraints | Bullet list |
| 8 | Risks | Table: ID (RISK-001), Description, Likelihood, Impact, Mitigation |

Cover page: Project Name, Meeting Date, Prepared By (BRD Agent), Version (1.0), Attendees.

---

## End-to-End Request Flow

```
Power Automate
    │
    │  POST /api/v1/generate-brd
    │  Header: X-API-Key: <secret>
    │  Body: multipart/form-data  →  file: transcript.docx or .vtt
    ▼
FastAPI (main.py → app/api/routes.py)              ✅ DONE
    │  • Validates X-API-Key header (401 on fail)
    │  • Validates extension + size (400/413 on fail)
    │  • Generates job_id, starts timer
    ▼
Transcript Extractor (app/services/extractor.py)   ✅ DONE
    │  • .vtt → strips timestamps, voice tags, filler words (um/uh/hmm)
    │  • .docx → extracts paragraphs + table cell text
    │  • Returns clean plain-text string
    │  • Raises ExtractionError → 400
    ▼
AI Processor (app/services/ai_processor.py)        ✅ DONE
    │  • Chunks transcript at 6,000 words / 200-word overlap
    │  • Calls Azure AI Foundry with structured extraction prompt
    │  • Continuation prompt carries ID offsets for chunk 2+
    │  • Merges chunks, deduplicates requirements, re-sequences IDs
    │  • Returns validated BRDContent (Pydantic)
    │  • AzureFoundryError → 502  |  AIProcessorError → 422
    ▼
BRD Builder (app/services/brd_builder.py)          ✅ DONE
    │  • Loads company .docx template
    │  • Fills {{ placeholders }} with BRDContent
    │  • Colour-coded priority/risk cells in tables
    │  • Returns filled .docx as bytes
    │  • BRDBuilderError → 500
    ▼
FastAPI Response                                    ✅ DONE
    │  • base64-encodes .docx bytes
    │  • Returns BRDResponse JSON:
    │    { success, job_id, project_name, filename,
    │      docx_base64, sections_extracted }
    ▼
Power Automate                                      ⏳ GUIDE NOT YET WRITTEN
    • Decodes base64 → .docx file
    • Attaches to email and sends
```

---

## Directory Structure

```
brd-agent/
├── main.py                         ← Uvicorn entrypoint, lifespan, /health
├── pyproject.toml                  ← All deps (Poetry)
├── .env.example                    ← Env var template
├── .env                            ← Secrets (never commit)
├── templates/
│   └── brd_template.docx           ← Run scripts/create_template.py once
├── logs/                           ← Auto-created in production
├── scripts/
│   └── create_template.py          ← One-time template generator
├── app/
│   ├── core/
│   │   ├── config.py               ← Pydantic Settings singleton
│   │   ├── models.py               ← BRDContent, BRDResponse, all Pydantic models
│   │   └── logging.py              ← Loguru setup
│   ├── utils/
│   │   ├── vtt_parser.py           ← WebVTT → plain text
│   │   ├── docx_extractor.py       ← .docx → plain text
│   │   └── chunker.py              ← 6k-word chunks, 200-word overlap
│   ├── services/
│   │   ├── extractor.py            ← Routes to vtt/docx parser, cleans output
│   │   ├── prompts.py              ← System + extraction + continuation prompts
│   │   ├── foundry_client.py       ← Azure AI Foundry client, retry logic
│   │   ├── ai_processor.py         ← Chunk → call → merge orchestrator
│   │   ├── brd_merger.py           ← Multi-chunk merge, dedup, ID resequencing
│   │   └── brd_builder.py          ← Template filler, bullets + tables
│   └── api/
│       ├── routes.py               ← POST /api/v1/generate-brd
│       └── dependencies.py         ← verify_api_key, validate_upload_file
└── tests/
    ├── test_extractor.py           ← 9 tests
    ├── test_ai_processor.py        ← 11 tests
    ├── test_brd_builder.py         ← 7 tests
    └── test_api.py                 ← 12 tests (httpx AsyncClient, all mocked)
```

**Import rule (strict):** `api → services → utils → core`. Never reverse. `core` has zero internal deps.

---

## Environment Variables

```bash
AZURE_FOUNDRY_ENDPOINT=https://<project>.services.ai.azure.com/models
AZURE_FOUNDRY_API_KEY=<key>
AZURE_FOUNDRY_MODEL=gpt-4o-mini
API_SECRET_KEY=<strong-secret>        # Power Automate sends in X-API-Key header
APP_ENV=development                   # development | production
LOG_LEVEL=INFO
MAX_FILE_SIZE_MB=20
ALLOWED_EXTENSIONS=.docx,.vtt
BRD_TEMPLATE_PATH=./templates/brd_template.docx
```

---

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| `temperature=0.1` | Deterministic extraction — not creative generation |
| 6,000 word chunks / 200-word overlap | Safe under GPT-4o mini 128k context; overlap prevents boundary losses |
| Continuation prompt carries ID offsets | FR/NFR/RISK numbering never restarts across chunks |
| Dedup by normalised description | Catches identical requirements in overlapping chunk boundaries |
| Typed error hierarchy | ExtractionError/AzureFoundryError/AIProcessorError/BRDBuilderError each map to distinct HTTP codes |
| 502 for Azure errors (not 500) | Signals upstream failure — Power Automate can retry differently |
| File read once in dependency | `validate_upload_file` returns bytes; route never reads twice |
| `process_transcript` must be async | Route uses `await` — verify this in ai_processor.py or wrap with `asyncio.to_thread` |
| Template never mutated | Loads fresh copy per request — concurrent safety |
| Docs UI off in production | `docs_url=None` when `APP_ENV=production` |

---

## HTTP Status Code Map

| Code | Trigger |
|------|---------|
| 200 | Success |
| 400 | Bad extension, empty file, ExtractionError |
| 401 | Wrong or missing X-API-Key |
| 413 | File > MAX_FILE_SIZE_MB |
| 422 | AIProcessorError (model returned bad/unparseable JSON) |
| 500 | BRDBuilderError or unhandled exception |
| 502 | AzureFoundryError (retries exhausted) |

---

## Module Completion Status

| Module | Status | Key Files |
|--------|--------|-----------|
| 1 — Project Skeleton | ✅ Done | `pyproject.toml`, `.env.example`, `core/config.py`, `core/models.py`, `core/logging.py` |
| 2 — Transcript Extractor | ✅ Done | `services/extractor.py`, `utils/vtt_parser.py`, `utils/docx_extractor.py` |
| 3 — Azure AI Processor | ✅ Done | `services/prompts.py`, `services/foundry_client.py`, `services/ai_processor.py`, `services/brd_merger.py`, `utils/chunker.py` |
| 4 — BRD Builder | ✅ Done | `services/brd_builder.py`, `scripts/create_template.py` |
| 5 — FastAPI Layer | ✅ Done | `main.py`, `api/routes.py`, `api/dependencies.py` |
| 6 — Power Automate Guide | ⏳ Next | `POWER_AUTOMATE.md` |

---

## What To Build Next

### POWER_AUTOMATE.md — Integration Guide

Must cover:
1. HTTP action configuration (URL, method, headers, body/form-data)
2. How to decode base64 response → file attachment (Power Automate expression)
3. Email action: attach decoded .docx, set subject/body dynamically using `project_name`
4. Handling error responses (check `success` field before decoding)
5. Timeout setting — set HTTP action timeout to 110s (service max is 120s)
6. 502 retry logic recommendation
7. Sample importable flow JSON

---

## Running the Project

```bash
# Install
poetry install

# Generate template (run once)
poetry run python scripts/create_template.py

# Configure
cp .env.example .env
# → fill in Azure credentials, API_SECRET_KEY, etc.

# Dev server
poetry run uvicorn main:app --reload --port 8000

# Tests
poetry run pytest -v

# Generate API secret
openssl rand -hex 32
```

---

## Pre-Deploy Checklist

```
[ ] poetry install
[ ] cp .env.example .env  →  fill all values
[ ] python scripts/create_template.py  (or place real company template)
[ ] BRD_TEMPLATE_PATH set correctly in .env
[ ] Azure endpoint confirmed: https://<project>.services.ai.azure.com/models
[ ] API_SECRET_KEY generated and set in both .env and Power Automate
[ ] poetry run pytest -v  →  all 39 tests pass
[ ] APP_ENV=production set on server (disables /docs, enables file logging)
```
