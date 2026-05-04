import json
import pytest
from unittest.mock import patch, MagicMock

from app.services.ai_processor import process_transcript, AIProcessorError
from app.services.brd_merger import merge_brd_chunks
from app.utils.chunker import chunk_transcript, estimate_tokens


# ── Sample data ────────────────────────────────────────────────────────────────

SAMPLE_TRANSCRIPT = """
John: We need to build a customer self-service portal by end of Q3.
Jane: The portal must integrate with our existing Salesforce CRM.
John: Users need to log in via Azure AD SSO — no separate credentials.
Jane: We're targeting 10,000 concurrent users at peak load.
John: Budget is hard-capped at 200,000 USD. No exceptions.
Jane: Mobile browser support is out of scope for this phase.
John: We're assuming the Azure AD tenant is already configured.
Jane: Risk — if Salesforce API changes, integration breaks. Medium likelihood, high impact.
John: IE11 support is not required — that's a constraint from IT policy.
"""

SAMPLE_AI_RESPONSE = {
    "project_name": "Customer Self-Service Portal",
    "meeting_date": "Not specified",
    "attendees": ["John", "Jane"],
    "business_objectives": [
        "Build a customer self-service portal by end of Q3."
    ],
    "in_scope": [
        "Customer self-service portal",
        "Salesforce CRM integration",
        "Azure AD SSO authentication",
    ],
    "out_of_scope": [
        "Mobile browser support in this phase"
    ],
    "functional_requirements": [
        {"id": "FR-001", "description": "Users must log in via Azure AD SSO.", "priority": "High"},
        {"id": "FR-002", "description": "Portal must integrate with Salesforce CRM.", "priority": "High"},
    ],
    "non_functional_requirements": [
        {"id": "NFR-001", "category": "Scalability", "description": "System must support 10,000 concurrent users at peak load."},
    ],
    "assumptions": [
        "Azure AD tenant is already configured and operational."
    ],
    "constraints": [
        "Budget is hard-capped at 200,000 USD.",
        "IE11 support is not required per IT policy.",
    ],
    "risks": [
        {
            "id": "RISK-001",
            "description": "Salesforce API changes may break integration.",
            "likelihood": "Medium",
            "impact": "High",
            "mitigation": "Not discussed",
        }
    ],
}


# ── Chunker tests ──────────────────────────────────────────────────────────────

def test_short_transcript_single_chunk():
    chunks = chunk_transcript("This is a short transcript.", words_per_chunk=100)
    assert len(chunks) == 1


def test_long_transcript_multiple_chunks():
    long_transcript = " ".join(["word"] * 15_000)
    chunks = chunk_transcript(long_transcript, words_per_chunk=6_000)
    assert len(chunks) >= 2


def test_chunk_overlap_preserves_boundary_content():
    words = [f"word{i}" for i in range(1000)]
    transcript = " ".join(words)
    chunks = chunk_transcript(transcript, words_per_chunk=400)
    # word at position 399 should appear in both chunk 0 and chunk 1
    assert "word399" in chunks[0]
    assert "word399" in chunks[1]  # overlap


def test_estimate_tokens_reasonable():
    text = "a" * 4000  # 4000 chars ≈ 1000 tokens
    assert estimate_tokens(text) == 1000


# ── AI Processor tests (mocked) ───────────────────────────────────────────────

@patch("app.services.ai_processor.call_foundry")
def test_process_transcript_single_chunk(mock_foundry):
    mock_foundry.return_value = json.dumps(SAMPLE_AI_RESPONSE)

    result = process_transcript(SAMPLE_TRANSCRIPT)

    assert result.project_name == "Customer Self-Service Portal"
    assert len(result.functional_requirements) == 2
    assert result.functional_requirements[0].id == "FR-001"
    assert len(result.non_functional_requirements) == 1
    assert len(result.risks) == 1
    assert result.risks[0].likelihood.value == "Medium"
    assert result.risks[0].impact.value == "High"


@patch("app.services.ai_processor.call_foundry")
def test_process_transcript_markdown_fences_stripped(mock_foundry):
    """Model sometimes returns ```json ... ``` despite instructions."""
    mock_foundry.return_value = f"```json\n{json.dumps(SAMPLE_AI_RESPONSE)}\n```"

    result = process_transcript(SAMPLE_TRANSCRIPT)
    assert result.project_name == "Customer Self-Service Portal"


@patch("app.services.ai_processor.call_foundry")
def test_process_transcript_raises_on_bad_json(mock_foundry):
    mock_foundry.return_value = "This is not JSON at all."

    with pytest.raises(AIProcessorError, match="Failed to process"):
        process_transcript(SAMPLE_TRANSCRIPT)


# ── Merger tests ───────────────────────────────────────────────────────────────

def test_merge_single_chunk():
    result = merge_brd_chunks([SAMPLE_AI_RESPONSE])
    assert result.project_name == "Customer Self-Service Portal"
    assert len(result.functional_requirements) == 2


def test_merge_deduplicates_requirements():
    duplicate = {**SAMPLE_AI_RESPONSE}  # Identical chunk
    result = merge_brd_chunks([SAMPLE_AI_RESPONSE, duplicate])
    # Duplicates must be removed
    assert len(result.functional_requirements) == 2  # Not 4


def test_merge_resequences_ids():
    chunk2 = {
        **SAMPLE_AI_RESPONSE,
        "functional_requirements": [
            {"id": "FR-099", "description": "Unique FR from chunk 2.", "priority": "Low"},
        ],
        "non_functional_requirements": [],
        "risks": [],
    }
    result = merge_brd_chunks([SAMPLE_AI_RESPONSE, chunk2])
    ids = [fr.id for fr in result.functional_requirements]
    assert ids == ["FR-001", "FR-002", "FR-003"]  # Re-sequenced cleanly


def test_merge_coerces_enum_case():
    """Model may return 'medium' instead of 'Medium' — should still parse."""
    chunk = {**SAMPLE_AI_RESPONSE, "risks": [
        {
            "id": "RISK-001",
            "description": "Test risk.",
            "likelihood": "medium",   # lowercase
            "impact": "HIGH",          # uppercase
            "mitigation": "None",
        }
    ]}
    result = merge_brd_chunks([chunk])
    assert result.risks[0].likelihood.value == "Medium"
    assert result.risks[0].impact.value == "High"
