"""
Integration tests for POST /api/v1/generate-brd.

All external I/O (Azure AI Foundry, file system) is mocked.
Uses httpx.AsyncClient with FastAPI's ASGI transport — no real server needed.
"""
import base64
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

# Must be set before importing app modules that read settings at import time
os.environ.setdefault("AZURE_FOUNDRY_ENDPOINT", "https://fake.services.ai.azure.com/models")
os.environ.setdefault("AZURE_FOUNDRY_API_KEY", "fake-key")
os.environ.setdefault("AZURE_FOUNDRY_MODEL", "gpt-4o-mini")
os.environ.setdefault("API_SECRET_KEY", "test-secret")
os.environ.setdefault("BRD_TEMPLATE_PATH", "./templates/brd_template.docx")

from main import app  # noqa: E402  — must come after env setup

VALID_KEY = "test-secret"
HEADERS = {"X-API-Key": VALID_KEY}

# Minimal valid BRDContent for mock returns
_MOCK_BRD_CONTENT = MagicMock()
_MOCK_BRD_CONTENT.project_name = "Test Project"
_MOCK_BRD_CONTENT.business_objectives = ["obj1"]
_MOCK_BRD_CONTENT.in_scope = ["scope1"]
_MOCK_BRD_CONTENT.out_of_scope = []
_MOCK_BRD_CONTENT.functional_requirements = []
_MOCK_BRD_CONTENT.non_functional_requirements = []
_MOCK_BRD_CONTENT.assumptions = []
_MOCK_BRD_CONTENT.constraints = []
_MOCK_BRD_CONTENT.risks = []


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


def _fake_docx() -> bytes:
    """Return a minimal valid docx byte string (won't be parsed — just bytes)."""
    return b"PK" + b"\x00" * 100  # fake zip header sufficient for size checks


# ---------------------------------------------------------------------------
# Auth tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_missing_api_key_returns_401(client):
    files = {"file": ("t.vtt", b"WEBVTT\n\n00:00:01.000 --> 00:00:02.000\nHello", "text/plain")}
    resp = await client.post("/api/v1/generate-brd", files=files)
    assert resp.status_code == 422  # FastAPI validation: missing required header


@pytest.mark.asyncio
async def test_wrong_api_key_returns_401(client):
    files = {"file": ("t.vtt", b"WEBVTT\n\n00:00:01.000 --> 00:00:02.000\nHello", "text/plain")}
    resp = await client.post("/api/v1/generate-brd", files=files, headers={"X-API-Key": "wrong"})
    assert resp.status_code == 401
    assert "Invalid" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# File validation tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unsupported_extension_returns_400(client):
    files = {"file": ("transcript.pdf", b"%PDF fake", "application/pdf")}
    resp = await client.post("/api/v1/generate-brd", files=files, headers=HEADERS)
    assert resp.status_code == 400
    assert ".pdf" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_empty_file_returns_400(client):
    files = {"file": ("transcript.vtt", b"", "text/plain")}
    resp = await client.post("/api/v1/generate-brd", files=files, headers=HEADERS)
    assert resp.status_code == 400
    assert "empty" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_oversized_file_returns_413(client):
    # Build a file larger than MAX_FILE_SIZE_MB (default 20MB in .env.example, 1MB in test env)
    with patch("app.api.dependencies.settings") as mock_settings:
        mock_settings.api_secret_key = VALID_KEY
        mock_settings.max_file_size_bytes = 10  # 10 bytes limit for test
        mock_settings.allowed_extensions = [".vtt", ".docx"]
        big = b"x" * 100
        files = {"file": ("transcript.vtt", big, "text/plain")}
        resp = await client.post("/api/v1/generate-brd", files=files, headers=HEADERS)
    assert resp.status_code == 413


# ---------------------------------------------------------------------------
# Pipeline success test
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_successful_brd_generation(client):
    with (
        patch("app.api.routes.extract_transcript", return_value="Clean transcript text") as mock_extract,
        patch("app.api.routes.process_transcript", new_callable=AsyncMock, return_value=_MOCK_BRD_CONTENT) as mock_process,
        patch("app.api.routes.build_brd", return_value=_fake_docx()) as mock_build,
    ):
        files = {"file": ("meeting.vtt", b"WEBVTT\n\nspeaker: hello world content", "text/plain")}
        resp = await client.post("/api/v1/generate-brd", files=files, headers=HEADERS)

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert "job_id" in body
    assert body["project_name"] == "Test Project"
    assert body["filename"].endswith(".docx")
    # Verify base64 decodes to our fake docx bytes
    decoded = base64.b64decode(body["docx_base64"])
    assert decoded == _fake_docx()
    assert "sections_extracted" in body

    mock_extract.assert_called_once()
    mock_process.assert_awaited_once()
    mock_build.assert_called_once()


# ---------------------------------------------------------------------------
# Error propagation tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_extraction_error_returns_400(client):
    from app.services.extractor import ExtractionError

    with patch("app.api.routes.extract_transcript", side_effect=ExtractionError("bad vtt")):
        files = {"file": ("t.vtt", b"garbage", "text/plain")}
        resp = await client.post("/api/v1/generate-brd", files=files, headers=HEADERS)

    assert resp.status_code == 400
    assert "bad vtt" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_azure_error_returns_502(client):
    from app.services.foundry_client import AzureFoundryError

    with (
        patch("app.api.routes.extract_transcript", return_value="text"),
        patch("app.api.routes.process_transcript", new_callable=AsyncMock, side_effect=AzureFoundryError("timeout")),
    ):
        files = {"file": ("t.vtt", b"WEBVTT\ncontent here", "text/plain")}
        resp = await client.post("/api/v1/generate-brd", files=files, headers=HEADERS)

    assert resp.status_code == 502
    assert "timeout" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_ai_processor_error_returns_422(client):
    from app.services.ai_processor import AIProcessorError

    with (
        patch("app.api.routes.extract_transcript", return_value="text"),
        patch("app.api.routes.process_transcript", new_callable=AsyncMock, side_effect=AIProcessorError("bad json")),
    ):
        files = {"file": ("t.vtt", b"WEBVTT\ncontent here", "text/plain")}
        resp = await client.post("/api/v1/generate-brd", files=files, headers=HEADERS)

    assert resp.status_code == 422
    assert "bad json" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_brd_builder_error_returns_500(client):
    from app.services.brd_builder import BRDBuilderError

    with (
        patch("app.api.routes.extract_transcript", return_value="text"),
        patch("app.api.routes.process_transcript", new_callable=AsyncMock, return_value=_MOCK_BRD_CONTENT),
        patch("app.api.routes.build_brd", side_effect=BRDBuilderError("template missing")),
    ):
        files = {"file": ("t.vtt", b"WEBVTT\ncontent here", "text/plain")}
        resp = await client.post("/api/v1/generate-brd", files=files, headers=HEADERS)

    assert resp.status_code == 500
    assert "template missing" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_health_endpoint(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


# ---------------------------------------------------------------------------
# Response shape
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_response_contains_all_section_counts(client):
    content = MagicMock()
    content.project_name = "Proj"
    content.business_objectives = ["a", "b"]
    content.in_scope = ["x"]
    content.out_of_scope = ["y", "z"]
    content.functional_requirements = [MagicMock(), MagicMock(), MagicMock()]
    content.non_functional_requirements = [MagicMock()]
    content.assumptions = []
    content.constraints = ["c"]
    content.risks = [MagicMock(), MagicMock()]

    with (
        patch("app.api.routes.extract_transcript", return_value="text"),
        patch("app.api.routes.process_transcript", new_callable=AsyncMock, return_value=content),
        patch("app.api.routes.build_brd", return_value=_fake_docx()),
    ):
        files = {"file": ("t.vtt", b"WEBVTT\nsome content", "text/plain")}
        resp = await client.post("/api/v1/generate-brd", files=files, headers=HEADERS)

    assert resp.status_code == 200
    sections = resp.json()["sections_extracted"]
    assert sections["business_objectives"] == 2
    assert sections["in_scope"] == 1
    assert sections["out_of_scope"] == 2
    assert sections["functional_requirements"] == 3
    assert sections["non_functional_requirements"] == 1
    assert sections["assumptions"] == 0
    assert sections["constraints"] == 1
    assert sections["risks"] == 2
