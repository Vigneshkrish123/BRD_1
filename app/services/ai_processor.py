from loguru import logger

from app.core.models import BRDContent
from app.services.prompts import SYSTEM_PROMPT, BRD_EXTRACTION_PROMPT, CONTINUATION_PROMPT
from app.services.foundry_client import call_foundry, parse_json_response, AzureFoundryError
from app.services.brd_merger import merge_brd_chunks
from app.utils.chunker import chunk_transcript, estimate_tokens


class AIProcessorError(Exception):
    """Raised when AI processing fails unrecoverably."""


def process_transcript(transcript: str) -> BRDContent:
    """
    Main entry point for AI processing.

    Pipeline:
    1. Chunk transcript if it exceeds safe token window
    2. Call Azure Foundry for each chunk
    3. Parse + merge all chunk results
    4. Return validated BRDContent

    Raises:
        AIProcessorError: on unrecoverable AI or parsing failure
    """
    estimated_tokens = estimate_tokens(transcript)
    logger.info(f"Processing transcript: ~{estimated_tokens} estimated tokens")

    chunks = chunk_transcript(transcript)
    logger.info(f"Processing {len(chunks)} chunk(s)")

    extracted_chunks: list[dict] = []

    for idx, chunk in enumerate(chunks):
        logger.info(f"Processing chunk {idx + 1}/{len(chunks)} (~{estimate_tokens(chunk)} tokens)")

        try:
            raw_response = _call_for_chunk(chunk, idx, extracted_chunks)
            parsed = parse_json_response(raw_response)
            extracted_chunks.append(parsed)
            logger.info(
                f"Chunk {idx + 1} extracted: "
                f"FR={len(parsed.get('functional_requirements', []))} "
                f"NFR={len(parsed.get('non_functional_requirements', []))} "
                f"Risks={len(parsed.get('risks', []))}"
            )
        except AzureFoundryError as e:
            raise AIProcessorError(
                f"Failed to process transcript chunk {idx + 1}: {e}"
            ) from e

    if not extracted_chunks:
        raise AIProcessorError("AI extraction produced no usable output from transcript.")

    return merge_brd_chunks(extracted_chunks)


def _call_for_chunk(
    chunk: str,
    chunk_index: int,
    previous_chunks: list[dict],
) -> str:
    """
    Build the appropriate prompt for this chunk and call Foundry.

    - First chunk: full extraction prompt
    - Subsequent chunks: continuation prompt with ID offsets
      so numbering continues from where previous chunk left off
    """
    if chunk_index == 0 or not previous_chunks:
        user_prompt = BRD_EXTRACTION_PROMPT.format(transcript=chunk)
    else:
        # Calculate ID offsets from all previously extracted chunks
        fr_count = sum(len(c.get("functional_requirements", [])) for c in previous_chunks)
        nfr_count = sum(len(c.get("non_functional_requirements", [])) for c in previous_chunks)
        risk_count = sum(len(c.get("risks", [])) for c in previous_chunks)

        user_prompt = CONTINUATION_PROMPT.format(
            transcript=chunk,
            fr_next=fr_count + 1,
            nfr_next=nfr_count + 1,
            risk_next=risk_count + 1,
        )

    return call_foundry(SYSTEM_PROMPT, user_prompt)
