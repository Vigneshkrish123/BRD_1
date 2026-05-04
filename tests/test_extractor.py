import pytest
from app.services.extractor import extract_transcript, ExtractionError


# ── VTT Tests ──────────────────────────────────────────────────────────────────

SAMPLE_VTT = """\
WEBVTT

00:00:01.000 --> 00:00:04.000
<v John Smith>We need to build a customer portal by Q3.

00:00:05.000 --> 00:00:09.000
<v Jane Doe>The portal must support SSO and integrate with Salesforce.

00:00:10.000 --> 00:00:13.000
<v John Smith>Budget is capped at 200k, no exceptions.

00:00:14.000 --> 00:00:17.000
<v Jane Doe>Mobile support is out of scope for this phase.
"""

SAMPLE_VTT_NO_SPEAKERS = """\
WEBVTT

00:00:01.000 --> 00:00:04.000
We need to build a customer portal.

00:00:05.000 --> 00:00:08.000
The budget is fixed at 200k.
"""


def test_vtt_extracts_speaker_lines():
    result = extract_transcript(SAMPLE_VTT.encode(), "meeting.vtt")
    assert "John Smith" in result
    assert "Jane Doe" in result
    assert "customer portal" in result


def test_vtt_strips_timestamps():
    result = extract_transcript(SAMPLE_VTT.encode(), "meeting.vtt")
    assert "-->" not in result
    assert "00:00" not in result


def test_vtt_no_speakers_still_extracts():
    result = extract_transcript(SAMPLE_VTT_NO_SPEAKERS.encode(), "meeting.vtt")
    assert "customer portal" in result
    assert "200k" in result


def test_vtt_removes_filler_words():
    vtt_with_filler = """\
WEBVTT

00:00:01.000 --> 00:00:05.000
<v Speaker>Um so we uh need to build something hmm interesting.
"""
    result = extract_transcript(vtt_with_filler.encode(), "meeting.vtt")
    assert "um" not in result.lower()
    assert "uh" not in result.lower()
    assert "build something" in result.lower()


# ── DOCX Tests ─────────────────────────────────────────────────────────────────

def _make_docx_bytes(lines: list[str]) -> bytes:
    """Helper: create a minimal .docx in memory."""
    from docx import Document
    import io
    doc = Document()
    for line in lines:
        doc.add_paragraph(line)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def test_docx_extracts_paragraphs():
    content = [
        "John: We need SSO integration with Azure AD.",
        "Jane: Performance must handle 10,000 concurrent users.",
        "John: No support for IE11 — that is out of scope.",
    ]
    result = extract_transcript(_make_docx_bytes(content), "transcript.docx")
    assert "SSO integration" in result
    assert "10,000 concurrent users" in result
    assert "out of scope" in result


def test_docx_ignores_empty_paragraphs():
    content = ["First line.", "", "   ", "Second line."]
    result = extract_transcript(_make_docx_bytes(content), "transcript.docx")
    assert "First line." in result
    assert "Second line." in result


# ── Error handling ─────────────────────────────────────────────────────────────

def test_unsupported_extension_raises():
    with pytest.raises(ExtractionError, match="Unsupported file type"):
        extract_transcript(b"some content", "meeting.pdf")


def test_empty_vtt_raises():
    with pytest.raises(ExtractionError, match="too short"):
        extract_transcript(b"WEBVTT\n\n", "empty.vtt")


def test_garbage_bytes_raises():
    with pytest.raises(ExtractionError):
        extract_transcript(b"\x00\x01\x02\x03" * 10, "meeting.docx")
