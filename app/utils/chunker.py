from loguru import logger


# GPT-4o mini context: 128k tokens
# Conservative chunk size: ~6000 words ≈ ~8000 tokens, leaving room for prompt + response
_WORDS_PER_CHUNK = 6_000
_OVERLAP_WORDS = 200  # Overlap so requirements spanning chunk boundaries aren't lost


def chunk_transcript(transcript: str, words_per_chunk: int = _WORDS_PER_CHUNK) -> list[str]:
    """
    Split a transcript into overlapping word-based chunks.

    Why word-based and not character/token-based:
    - Consistent across languages
    - Avoids splitting mid-sentence more often than char split
    - Simple to reason about without a tokenizer dependency

    Overlap strategy: last N words of chunk N are prepended to chunk N+1
    so a requirement that straddles a boundary is captured in full by at least one chunk.
    """
    words = transcript.split()
    total_words = len(words)

    if total_words <= words_per_chunk:
        logger.debug(f"Transcript fits in single chunk ({total_words} words)")
        return [transcript]

    chunks: list[str] = []
    start = 0

    while start < total_words:
        end = min(start + words_per_chunk, total_words)
        chunk_words = words[start:end]
        chunks.append(" ".join(chunk_words))

        if end == total_words:
            break

        # Next chunk starts with overlap from end of current chunk
        start = end - _OVERLAP_WORDS

    logger.info(f"Transcript split into {len(chunks)} chunks ({total_words} total words)")
    return chunks


def estimate_tokens(text: str) -> int:
    """
    Rough token estimate without a tokenizer.
    GPT tokenization ≈ 0.75 words per token (or ~4 chars per token).
    Use the more conservative char-based estimate.
    """
    return len(text) // 4
