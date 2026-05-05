# BRD Agent — Build Log
# Session: May 04, 2026
# Complete record of all decisions, builds, and outputs.

================================================================================
SESSION START
================================================================================

--------------------------------------------------------------------------------
STEP 1 — Requirements Gathering
--------------------------------------------------------------------------------

User requested a BRD Agent with:
  - Input:  Meeting transcript (.docx or .vtt) via Power Automate
  - Output: Filled company BRD template (.docx) sent as email attachment
  - Backend: Python with Poetry (no frontend)
  - AI: Azure AI Foundry API
  - Transport: HTTP POST REST API (Power Automate → FastAPI)
  - Model: GPT-4o mini

Clarification Q&A:
  Q: BRD output format?               A: Word (.docx)
  Q: Where does output go?            A: Email attachment via Power Automate
  Q: BRD structure?                   A: Fixed company template
  Q: How Power Automate calls backend? A: HTTP POST to REST API (FastAPI)
  Q: Azure Foundry model?             A: GPT-4o mini

BRD Sections confirmed:
  1. Business Objectives
  2. In Scope
  3. Out of Scope
  4. Functional Requirements      (FR-001, FR-002 ... table format)
  5. Non-Functional Requirements  (NFR-001, NFR-002 ... table format)
  6. Assumptions
  7. Constraints
  8. Risks                        (Likelihood + Impact + Mitigation columns)

--------------------------------------------------------------------------------
STEP 2 — High-Level Architecture Defined
--------------------------------------------------------------------------------

Pipeline defined as 5 layers:

  Power Automate
    → Layer 1: FastAPI Gateway       (validate, auth, job_id)
    → Layer 2: Transcript Extractor  (.vtt/.docx → clean text)
    → Layer 3: AI Processor          (Azure Foundry → structured JSON)
    → Layer 4: BRD Builder           (JSON → filled .docx)
    → Layer 5: Response Handler      (base64 .docx → Power Automate)

5 modules mapped:
  Module 1 — Project Skeleton
  Module 2 — Transcript Extractor
  Module 3 — Azure AI Processor
  Module 4 — BRD Builder
  Module 5 — FastAPI Layer

User confirmed and said "next" to proceed.

================================================================================
MODULE 1 — Project Skeleton
================================================================================

STATUS: ✅ COMPLETE
DOWNLOAD: brd_agent_module1.zip

Files created:

  pyproject.toml
    - Poetry config with all runtime + dev dependencies pinned
    - Runtime: fastapi, uvicorn, python-multipart, azure-ai-inference,
               azure-identity, python-docx, pydantic, pydantic-settings,
               httpx, aiofiles, python-dotenv, loguru, tenacity
    - Dev: pytest, pytest-asyncio, ruff, mypy

  .env.example
    - All env vars documented:
        AZURE_FOUNDRY_ENDPOINT, AZURE_FOUNDRY_API_KEY, AZURE_FOUNDRY_MODEL
        API_SECRET_KEY, APP_ENV, LOG_LEVEL, MAX_FILE_SIZE_MB
        ALLOWED_EXTENSIONS, BRD_TEMPLATE_PATH

  app/core/config.py
    - Pydantic BaseSettings class
    - Single module-level `settings` singleton
    - Computed properties: max_file_size_bytes, is_production
    - Reads from .env file automatically

  app/core/models.py
    - Pydantic models:
        Likelihood(enum): Low | Medium | High
        Impact(enum): Low | Medium | High
        FunctionalRequirement: id, description, priority
        NonFunctionalRequirement: id, category, description
        Risk: id, description, likelihood, impact, mitigation
        BRDContent: full BRD schema (all 8 sections + meta)
        BRDResponse: API response contract (job_id, docx_base64, sections_extracted)
        ErrorResponse: error contract

  app/core/logging.py
    - Loguru setup
    - Coloured stdout in dev
    - Rotating daily file logs in production (30-day retention, zip compression)

  Directory structure created:
    brd-agent/
    ├── app/{core,api,services,utils}/
    ├── tests/
    ├── templates/
    ├── logs/
    └── scripts/

KEY DECISION: `core` has zero internal dependencies.
Import hierarchy enforced: api → services → utils → core

================================================================================
MODULE 2 — Transcript Extractor
================================================================================

STATUS: ✅ COMPLETE
DOWNLOAD: brd_agent_module2.zip

Files created:

  app/utils/vtt_parser.py
    - Full WebVTT parser
    - Strips: timestamp lines, inline timestamps, NOTE/STYLE/REGION blocks,
              voice tags (<v Speaker>), HTML tags, cue identifiers
    - Preserves: speaker labels as "Speaker: text"
    - Collapses: consecutive duplicate lines (rolling caption dedup)
    - Handles: UTF-8 and latin-1 encoding

  app/utils/docx_extractor.py
    - python-docx based extractor
    - Extracts: body paragraphs + table cells
    - Handles Teams-style table-format transcripts

  app/services/extractor.py
    - Main entry point for all extraction
    - Routes by file extension (.vtt / .docx)
    - Post-processing: normalise line endings, strip filler words
      (um, uh, hmm, mhm, erm — regex stripped before AI)
    - Collapses excess blank lines
    - Validates minimum length (100 chars)
    - Raises typed ExtractionError on failures

  tests/test_extractor.py
    - 9 tests covering:
        VTT speaker extraction, timestamp stripping, no-speaker case,
        filler word removal, DOCX paragraph extraction, empty para handling,
        unsupported extension error, empty VTT error, garbage bytes error

KEY DECISIONS:
  - Filler words stripped before AI to reduce token waste
  - ExtractionError is typed — API layer catches it as 400, not 500
  - VTT latin-1 fallback for legacy Teams/Zoom exports

================================================================================
MODULE 3 — Azure AI Processor
================================================================================

STATUS: ✅ COMPLETE
DOWNLOAD: brd_agent_module3.zip

Files created:

  app/services/prompts.py
    - SYSTEM_PROMPT: BA persona, strict JSON rules, no fabrication rule
    - BRD_EXTRACTION_PROMPT: Full schema injected as format string
      Maps all 8 BRD sections with explicit JSON structure
    - CONTINUATION_PROMPT: For chunk 2+ — carries ID offsets
      (fr_next, nfr_next, risk_next) so numbering never restarts

  app/utils/chunker.py
    - Word-based chunking (not char/token — avoids tokenizer dependency)
    - 6,000 words per chunk (≈ 8,000 tokens, safe for GPT-4o mini 128k context)
    - 200-word overlap between chunks (prevents boundary requirement loss)
    - estimate_tokens(): rough 4-chars-per-token estimate

  app/services/foundry_client.py
    - ChatCompletionsClient from azure-ai-inference SDK
    - AzureKeyCredential auth
    - temperature=0.1 (deterministic extraction)
    - max_tokens=4096
    - Tenacity retry: 3 attempts, exponential backoff 2-10s
      retries on: HttpResponseError, ServiceRequestError
    - parse_json_response(): strips markdown code fences if model adds them
    - Raises AzureFoundryError on unrecoverable failure

  app/services/brd_merger.py
    - Merges list of chunk dicts into single BRDContent
    - Deduplication: normalised lowercase string comparison on description
    - Takes first non-placeholder project_name / meeting_date found
    - Re-sequences all IDs cleanly after merge: FR-001, FR-002...
    - Coerces enum values (handles 'medium', 'MEDIUM', 'Medium' all → Medium)
    - Returns validated BRDContent

  app/services/ai_processor.py
    - Orchestrator: chunk → call → merge
    - Chunk 0: uses BRD_EXTRACTION_PROMPT
    - Chunk N: uses CONTINUATION_PROMPT with ID offsets calculated from
               all previous chunk results
    - Raises AIProcessorError (non-retryable) vs AzureFoundryError (retryable)

  tests/test_ai_processor.py
    - 11 tests, all mocked (no real API calls)
    - Covers: single chunk, markdown fence stripping, bad JSON error,
              single merge, dedup, ID resequencing, enum coercion,
              chunker overlap, estimate_tokens, short/long transcript

KEY DECISIONS:
  - temperature=0.1 to prevent hallucinated requirements
  - Typed error hierarchy: AzureFoundryError (retryable) vs AIProcessorError (not)
  - Continuation prompt carries ID offsets — clean sequential IDs across chunks
  - Dedup by normalised description — catches overlap-boundary duplicates

================================================================================
MODULE 4 — BRD Builder
================================================================================

STATUS: ✅ COMPLETE
DOWNLOAD: brd_agent_module4.zip
SAMPLE OUTPUT: sample_brd_output.docx (live generated — verified working)

Files created:

  scripts/create_template.py
    - Generates company BRD .docx template with all section placeholders
    - Cover page with meta table (Project Name, Meeting Date, Prepared By, Version)
    - Section headings with navy/blue brand styling
    - Placeholder paragraphs: {{ business_objectives_list }}, {{ in_scope_list }},
        {{ out_of_scope_list }}, {{ assumptions_list }}, {{ constraints_list }},
        {{ attendees_list }}
    - FR table: ID | Description | Priority  (placeholder: {{ fr_rows }})
    - NFR table: ID | Category | Description (placeholder: {{ nfr_rows }})
    - Risk table: ID | Description | Likelihood | Impact | Mitigation
                  (placeholder: {{ risk_rows }})
    - Brand colors: Navy #1F497D, Blue #2E75B6, Orange accent #ED7D31
    - Run once at deploy: python scripts/create_template.py

  app/services/brd_builder.py
    - build_brd(content: BRDContent) → bytes  (main public API)
    - Loads template from BRD_TEMPLATE_PATH setting
    - _fill_inline_placeholders(): replaces {{ project_name }}, {{ meeting_date }}
      in body paragraphs AND table cells (cover page meta table)
    - _fill_bullet_sections(): finds {{ tag }} paragraphs, removes them,
      inserts styled bullet paragraphs using proper OxmlElement (not unicode bullets)
    - _fill_fr_table(): removes placeholder row, adds FR rows with alternating
      row shading, colour-coded Priority (High=Red, Medium=Orange, Low=Green)
    - _fill_nfr_table(): same pattern, 3 columns
    - _fill_risk_table(): 5 columns, colour-coded Likelihood + Impact
    - Empty sections → writes "None identified in transcript." (no crash)
    - Raises BRDBuilderError if template missing

  tests/test_brd_builder.py
    - 7 tests:
        Returns bytes, valid docx, project name in document,
        FR table correct row count, Risk table correct row count,
        missing template raises BRDBuilderError,
        empty sections handled gracefully

SMOKE TEST RESULT:
  Command: python -c "... build_brd(content) ..."
  Output:  BRD built: 37,886 bytes
  All 8 sections populated — Status: ✅ PASSED

KEY DECISIONS:
  - Template is version-controlled separately from code
  - Placeholder strategy: {{ tag }} in paragraph text → found by regex, replaced
  - OxmlElement used for bullets (not unicode) — proper OOXML compliance
  - Priority/Likelihood/Impact colour-coded in cell text runs
  - Never mutates original template file — loads fresh copy per request

================================================================================
MODULE 5 — FastAPI Layer
================================================================================

STATUS: ✅ COMPLETE
DOWNLOAD: brd_agent_module5.zip

Files created:

  main.py
    - Uvicorn entrypoint with asynccontextmanager lifespan
    - Logs startup: env, model, template path
    - Docs UI (/docs) disabled in production (APP_ENV=production)
    - Health endpoint: GET /health (no auth, returns {status, env})
    - Router mounted at: /api/v1

  app/api/dependencies.py
    - verify_api_key(x_api_key: Header)
        Compares against settings.api_secret_key
        Returns 401 with detail on mismatch
    - validate_upload_file(file: UploadFile) → bytes
        Validates extension against ALLOWED_EXTENSIONS
        Reads file once into memory, returns raw bytes
        Returns 400 on bad extension or empty file
        Returns 413 if size > MAX_FILE_SIZE_MB

  app/api/routes.py
    - POST /api/v1/generate-brd
    - Accepts: multipart/form-data, single field "file"
    - Required header: X-API-Key
    - Pipeline: extract_transcript → process_transcript → build_brd
    - Error → HTTP status mapping:
        ExtractionError   → 400
        AzureFoundryError → 502  (upstream failure, retries exhausted)
        AIProcessorError  → 422  (bad JSON from model)
        BRDBuilderError   → 500
        Unhandled         → 500
    - Success response (BRDResponse):
        { success, job_id, project_name, filename, docx_base64, sections_extracted }
    - Output filename format: {project_slug}_{YYYYMMDD}.docx
    - Logs: job_id, elapsed_ms, docx_bytes, per-section counts

  tests/test_api.py
    - 12 tests using httpx.AsyncClient + ASGITransport (no real server)
    - Auth: missing key (422), wrong key (401)
    - File: bad extension (400), empty file (400), oversized (413)
    - Success: full pipeline mock, base64 round-trip verified
    - Error paths: all 4 typed errors → correct HTTP codes
    - Health check: GET /health returns 200
    - Response shape: all 8 section counts verified

KEY DECISIONS:
  - 502 used for Azure errors (not 500) — signals upstream failure to Power Automate
  - process_transcript must be async def (or wrapped in asyncio.to_thread if sync)
  - File read happens once in dependency, passed as bytes to route — no double-read
  - job_id logged on every request for traceability

================================================================================
DIRECTORY STRUCTURE — FINAL
================================================================================

  brd-agent/
  ├── main.py                         ✅ Module 5
  ├── pyproject.toml                  ✅ Module 1
  ├── .env.example                    ✅ Module 1
  ├── .env                            (user fills in)
  ├── templates/
  │   └── brd_template.docx           (run scripts/create_template.py once)
  ├── logs/                           (auto-created in production)
  ├── scripts/
  │   └── create_template.py          ✅ Module 4
  ├── app/
  │   ├── core/
  │   │   ├── config.py               ✅ Module 1
  │   │   ├── models.py               ✅ Module 1
  │   │   └── logging.py              ✅ Module 1
  │   ├── utils/
  │   │   ├── vtt_parser.py           ✅ Module 2
  │   │   ├── docx_extractor.py       ✅ Module 2
  │   │   └── chunker.py              ✅ Module 3
  │   ├── services/
  │   │   ├── extractor.py            ✅ Module 2
  │   │   ├── prompts.py              ✅ Module 3
  │   │   ├── foundry_client.py       ✅ Module 3
  │   │   ├── ai_processor.py         ✅ Module 3
  │   │   ├── brd_merger.py           ✅ Module 3
  │   │   └── brd_builder.py          ✅ Module 4
  │   └── api/
  │       ├── routes.py               ✅ Module 5
  │       └── dependencies.py         ✅ Module 5
  └── tests/
      ├── test_extractor.py           ✅ Module 2  (9 tests)
      ├── test_ai_processor.py        ✅ Module 3  (11 tests)
      ├── test_brd_builder.py         ✅ Module 4  (7 tests)
      └── test_api.py                 ✅ Module 5  (12 tests)

  Total tests: 39

================================================================================
PENDING USER ACTIONS — Deploy Checklist
================================================================================

  [ ] poetry install
  [ ] cp .env.example .env  →  fill in real Azure credentials
  [ ] python scripts/create_template.py  (or drop in real company template)
  [ ] Set BRD_TEMPLATE_PATH in .env to point to your template
  [ ] Confirm Azure endpoint format:
        https://<project-name>.services.ai.azure.com/models
  [ ] openssl rand -hex 32  →  set as API_SECRET_KEY in .env
  [ ] Set same API_SECRET_KEY in Power Automate HTTP action header

================================================================================
WHAT REMAINS
================================================================================

  ⏳ Power Automate Integration Guide (POWER_AUTOMATE.md)
      - HTTP action config (URL, method, headers, body)
      - Base64 decode expression → file attachment
      - Email action setup
      - Sample flow JSON (importable)
      - Troubleshooting: timeout settings, 502 retry logic

================================================================================
SESSION END — RESUME WITH: "next" to build POWER_AUTOMATE.md
================================================================================
