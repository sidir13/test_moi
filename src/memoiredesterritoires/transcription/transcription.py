from __future__ import annotations

from typing import Dict, List

from faster_whisper import WhisperModel


def transcribe_chunks(path: str, max_time: int = 180, chunk_size: int = 30) -> Dict[str, object]:
    """
    Transcribe an audio file and bucket the transcript into time-based chunks.

    Args:
        path: Path to the audio file.
        max_time: Maximum number of seconds to process before stopping.
        chunk_size: Duration of each chunk in seconds.

    Returns:
        Dict with detected language, processed duration, and a list of chunk texts.
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than 0")

    model_size = "large-v3-turbo"
    model = WhisperModel(model_size, device="cpu", compute_type="int8")

    segments, info = model.transcribe(
        path,
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 500},
    )

    chunks: List[Dict[str, object]] = []
    current_chunk_text: List[str] = []
    next_checkpoint = float(chunk_size)
    chunk_index = 1

    for segment in segments:
        current_chunk_text.append(segment.text.strip())

        reached_chunk_boundary = segment.end >= next_checkpoint
        reached_max_time = segment.end >= max_time

        if reached_chunk_boundary or reached_max_time:
            chunk_text = " ".join(filter(None, current_chunk_text)).strip()
            if chunk_text:
                chunks.append(
                    {
                        "chunk": chunk_index,
                        "end_time": round(min(segment.end, max_time), 2),
                        "text": chunk_text,
                    }
                )
                chunk_index += 1
            current_chunk_text = []
            next_checkpoint += chunk_size

        if reached_max_time:
            break

    # Add any trailing text that didn't hit a boundary
    trailing_text = " ".join(filter(None, current_chunk_text)).strip()
    if trailing_text:
        chunks.append(
            {
                "chunk": chunk_index,
                "end_time": max_time,
                "text": trailing_text,
            }
        )

    return {
        "language": info.language,
        "duration": min(info.duration, max_time),
        "chunks": chunks,
    }
