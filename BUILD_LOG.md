# BRD Agent — Build Log
# Session: May 04, 2026
# All decisions, builds, outputs, and current state recorded here.

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

Clarification questions asked and answered:
  Q: BRD output format?              A: Word (.docx)
  Q: Where does output go?           A: Email attachment via Power Automate
  Q: BRD structure?                  A: Fixed company template
  Q: How Power Automate calls backend? A: HTTP POST to REST API (FastAPI)
  Q: Azure Foundry model?            A: GPT-4o mini

BRD Sections confirmed by user:
  1. Business Objectives
  2. In Scope
  3. Out of Scope
  4. Functional Requirements     (FR-001, FR-002 ... table format)
  5. Non-Functional Requirements (NFR-001, NFR-002 ... table format)
  6. Assumptions
  7. Constraints
  8. Risks                       (with Likelihood + Impact + Mitigation columns)

--------------------------------------------------------------------------------
STEP 2 — High-Level Architecture Presented
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

User confirmed schema and said "next" to proceed.

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
    - FR table: ID | Description | Priority (placeholder row: {{ fr_rows }})
    - NFR table: ID | Category | Description (placeholder row: {{ nfr_rows }})
    - Risk table: ID | Description | Likelihood | Impact | Mitigation
                  (placeholder row: {{ risk_rows }})
    - Brand colors: Navy #1F497D, Blue #2E75B6, Orange accent #ED7D31
    - Run once at deploy: python scripts/create_template.py

  app/services/brd_builder.py
    - build_brd(content: BRDContent) → bytes (main public API)
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
  Output: BRD built: 37,886 bytes
  All 8 sections populated:
    business_objectives: 1 bullet
    in_scope: 2 bullets
    out_of_scope: 1 bullet
    assumptions: 1 bullet
    constraints: 1 bullet
    attendees: 2 bullets
    FR table: 2 rows
    NFR table: 2 rows
    Risk table: 1 row
  Status: ✅ PASSED

KEY DECISIONS:
  - Template is version-controlled separately from code (gitignored)
  - Placeholder strategy: {{ tag }} in paragraph text → found by regex, replaced
  - OxmlElement used for bullets (not unicode) — matches SKILL.md requirement
  - Priority/Likelihood/Impact colour-coded directly in cell text runs
  - Never mutates original template file — loads fresh copy per request

================================================================================
DIRECTORY STRUCTURE — QUESTION ANSWERED
================================================================================

User asked: "Where should Module 2 files go in the project structure?"

Answer provided with full annotated tree showing:
  app/utils/        ← low-level file parsers (vtt_parser, docx_extractor, chunker)
  app/services/     ← business logic (extractor, ai_processor, brd_merger, brd_builder)
  app/core/         ← shared foundation (config, models, logging)
  app/api/          ← HTTP layer (routes, dependencies) — Module 5
  tests/            ← all test files
  scripts/          ← one-time scripts (create_template)
  templates/        ← company .docx template

Import rule stated: api → services → utils → core (never reverse)

================================================================================
CURRENT STATE
================================================================================

COMPLETED:
  ✅ Module 1 — Project Skeleton
  ✅ Module 2 — Transcript Extractor
  ✅ Module 3 — Azure AI Processor
  ✅ Module 4 — BRD Builder

IN PROGRESS / NEXT:
  ⏳ Module 5 — FastAPI Layer
      Files to build:
        main.py                  — Uvicorn entrypoint + lifespan
        app/api/routes.py        — POST /api/v1/generate-brd
        app/api/dependencies.py  — X-API-Key auth + file validation middleware
        tests/test_api.py        — httpx.AsyncClient integration tests

  ⏳ Power Automate Integration Guide (after Module 5)
      - HTTP action configuration
      - Base64 decode + email attachment setup
      - Sample flow JSON

================================================================================
PENDING USER ACTIONS (Deploy Checklist)
================================================================================

  [ ] Copy .env.example → .env and fill in real Azure credentials
  [ ] Run: poetry install
  [ ] Run: python scripts/create_template.py  (or place your real company template)
  [ ] Set BRD_TEMPLATE_PATH in .env to point to your real template
  [ ] Confirm Azure AI Foundry endpoint URL format:
        https://<project-name>.services.ai.azure.com/models
  [ ] Generate API_SECRET_KEY (openssl rand -hex 32) and set in Power Automate

================================================================================
SESSION END — RESUME WITH: "next" to build Module 5
================================================================================
