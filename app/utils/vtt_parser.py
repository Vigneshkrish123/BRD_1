import re
from loguru import logger


# Matches: 00:00:00.000 --> 00:00:00.000 (with optional position metadata)
_TIMESTAMP_LINE = re.compile(r"^\d{2}:\d{2}:\d{2}[.,]\d{3}\s+-->\s+\d{2}:\d{2}:\d{2}[.,]\d{3}")

# Matches: <00:00:00.000> inline timestamps inside cue text
_INLINE_TIMESTAMP = re.compile(r"<\d{2}:\d{2}:\d{2}[.,]\d{3}>")

# Matches: <v Speaker Name> or <v.role Speaker Name> tags (WebVTT voice spans)
_VOICE_TAG = re.compile(r"<v(?:\.[^>]+)?\s+([^>]+)>")

# Matches: any remaining HTML-like tags
_HTML_TAG = re.compile(r"<[^>]+>")

# Matches: NOTE, STYLE, REGION blocks
_BLOCK_HEADER = re.compile(r"^(NOTE|STYLE|REGION)\b")


def parse_vtt(raw: str) -> str:
    """
    Parse a WebVTT transcript into clean plain text.

    Strategy:
    - Drop header, cue identifiers, timestamps, NOTE/STYLE/REGION blocks
    - Preserve speaker labels as "Speaker: text" where detectable
    - Collapse duplicate consecutive speaker lines
    - Return single clean string ready for AI processing
    """
    lines = raw.splitlines()
    output: list[str] = []
    skip_block = False
    current_speaker: str | None = None

    i = 0
    # Skip WEBVTT header line and optional header metadata
    if lines and lines[0].startswith("WEBVTT"):
        i = 1
        while i < len(lines) and lines[i].strip():
            i += 1

    while i < len(lines):
        line = lines[i].strip()

        # Skip empty lines
        if not line:
            skip_block = False
            i += 1
            continue

        # Skip NOTE / STYLE / REGION blocks
        if _BLOCK_HEADER.match(line):
            skip_block = True
            i += 1
            continue

        if skip_block:
            i += 1
            continue

        # Skip timestamp lines
        if _TIMESTAMP_LINE.match(line):
            i += 1
            continue

        # Skip pure cue identifier lines (numeric or UUID before a timestamp)
        if i + 1 < len(lines) and _TIMESTAMP_LINE.match(lines[i + 1].strip()):
            i += 1
            continue

        # Process cue text
        # Extract speaker from voice tag if present
        voice_match = _VOICE_TAG.search(line)
        if voice_match:
            current_speaker = voice_match.group(1).strip()

        # Strip all tags and inline timestamps
        clean = _VOICE_TAG.sub("", line)
        clean = _INLINE_TIMESTAMP.sub("", clean)
        clean = _HTML_TAG.sub("", clean)
        clean = clean.strip()

        if not clean:
            i += 1
            continue

        # Format with speaker label if known
        if current_speaker:
            formatted = f"{current_speaker}: {clean}"
        else:
            formatted = clean

        # Collapse duplicate consecutive lines (VTT often repeats rolling captions)
        if output and output[-1] == formatted:
            i += 1
            continue

        output.append(formatted)
        i += 1

    result = "\n".join(output)
    logger.debug(f"VTT parsed: {len(lines)} raw lines → {len(output)} clean lines")
    return result
