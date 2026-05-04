import re
from pathlib import Path
from loguru import logger

from app.utils.vtt_parser import parse_vtt
from app.utils.docx_extractor import extract_docx_text


# Minimum viable transcript length — below this something went wrong
_MIN_CHARS = 100

# Collapse 3+ blank lines into 2
_EXCESS_BLANK = re.compile(r"\n{3,}")

# Strip filler noise common in auto-generated transcripts
_FILLER_PATTERNS = re.compile(
    r"\b(um+|uh+|hmm+|mhm+|erm+|ah+)\b",
    flags=re.IGNORECASE,
)


class ExtractionError(Exception):
    """Raised when transcript extraction fails or produces unusable output."""


def extract_transcript(file_bytes: bytes, filename: str) -> str:
    """
    Primary entry point. Accepts raw file bytes + original filename.
    Returns a clean, normalised plain-text transcript.

    Raises:
        ExtractionError: unsupported extension, empty result, or file too short
    """
    suffix = Path(filename).suffix.lower()
    logger.info(f"Extracting transcript from '{filename}' (ext={suffix}, size={len(file_bytes)} bytes)")

    if suffix == ".vtt":
        raw_text = _extract_vtt(file_bytes)
    elif suffix == ".docx":
        raw_text = _extract_docx(file_bytes)
    else:
        raise ExtractionError(
            f"Unsupported file type '{suffix}'. Accepted formats: .vtt, .docx"
        )

    cleaned = _clean(raw_text)

    if len(cleaned) < _MIN_CHARS:
        raise ExtractionError(
            f"Extracted transcript is too short ({len(cleaned)} chars). "
            "File may be empty, corrupted, or contain only metadata."
        )

    logger.info(f"Extraction complete: {len(cleaned)} chars of clean transcript")
    return cleaned


# ── Private helpers ────────────────────────────────────────────────────────────

def _extract_vtt(file_bytes: bytes) -> str:
    try:
        # VTT files are UTF-8; fall back to latin-1 for legacy exports
        try:
            raw = file_bytes.decode("utf-8")
        except UnicodeDecodeError:
            raw = file_bytes.decode("latin-1")
            logger.warning("VTT decoded with latin-1 fallback — consider re-exporting as UTF-8")
        return parse_vtt(raw)
    except Exception as e:
        raise ExtractionError(f"VTT parsing failed: {e}") from e


def _extract_docx(file_bytes: bytes) -> str:
    try:
        return extract_docx_text(file_bytes)
    except Exception as e:
        raise ExtractionError(f"DOCX extraction failed: {e}") from e


def _clean(text: str) -> str:
    """
    Normalise whitespace, remove filler words, strip artefacts.
    Keeps speaker labels and sentence structure intact.
    """
    # Normalise line endings
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Remove filler words (um, uh, hmm…)
    text = _FILLER_PATTERNS.sub("", text)

    # Collapse excess whitespace within lines
    lines = [" ".join(line.split()) for line in text.splitlines()]

    # Drop lines that are pure noise after cleaning
    lines = [l for l in lines if len(l) > 2]

    # Rejoin and collapse excess blank lines
    text = "\n".join(lines)
    text = _EXCESS_BLANK.sub("\n\n", text)

    return text.strip()
