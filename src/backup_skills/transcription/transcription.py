from __future__ import annotations

import wave
from typing import Dict, List, Optional

from faster_whisper import WhisperModel


def _get_audio_duration(path: str) -> float:
    """Return the duration (seconds) of a WAV file using stdlib only."""
    with wave.open(path, "rb") as wf:
        return wf.getnframes() / float(wf.getframerate())


def transcribe_chunks(
    path: str,
    start_time: float = 0.0,
    max_time: int = 1200,
    chunk_size: int = 60,
) -> Dict[str, object]:
    """
    Transcribe an audio file and bucket the transcript into time-based chunks.

    Args:
        path: Path to the audio file.
        start_time: Offset (in seconds) from which to start transcribing.
        max_time: Maximum number of seconds to process before stopping.
        chunk_size: Duration of each logical chunk in seconds.

    Returns:
        Dict with detected language, processed duration, and a list of chunk texts.
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than 0")

    total_duration = _get_audio_duration(path)
    start_time = max(0.0, float(start_time))
    if start_time >= total_duration:
        return {
            "language": None,
            "audio_duration": total_duration,
            "start_time": start_time,
            "end_time": start_time,
            "has_more": False,
            "next_start_time": None,
            "chunks": [],
        }

    end_limit = min(total_duration, start_time + max_time)

    model_size = "large-v3-turbo"
    model = WhisperModel(model_size, device="cpu", compute_type="int8")

    segments, info = model.transcribe(
        path,
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 500},
    )

    chunks: List[Dict[str, object]] = []
    current_chunk_text: List[str] = []
    chunk_index = 1
    chunk_start: Optional[float] = None
    chunk_end: float = start_time

    for segment in segments:
        if segment.end <= start_time:
            continue
        if segment.start >= end_limit:
            break

        seg_start = max(segment.start, start_time)
        seg_end = min(segment.end, end_limit)

        if chunk_start is None:
            chunk_start = seg_start
        chunk_end = seg_end
        current_chunk_text.append(segment.text.strip())

        if (chunk_end - chunk_start) >= chunk_size:
            chunk_text = " ".join(filter(None, current_chunk_text)).strip()
            if chunk_text:
                chunks.append(
                    {
                        "chunk": chunk_index,
                        "chunk_start": round(chunk_start, 2),
                        "chunk_end": round(chunk_end, 2),
                        "text": chunk_text,
                    }
                )
                chunk_index += 1
            current_chunk_text = []
            chunk_start = None

    if current_chunk_text:
        chunk_text = " ".join(filter(None, current_chunk_text)).strip()
        if chunk_text:
            chunks.append(
                {
                    "chunk": chunk_index,
                    "chunk_start": round(chunk_start or start_time, 2),
                    "chunk_end": round(chunk_end, 2),
                    "text": chunk_text,
                }
            )

    processed_until = chunk_end
    has_more = processed_until < total_duration - 1e-3

    return {
        "language": info.language,
        "audio_duration": total_duration,
        "start_time": start_time,
        "end_time": processed_until,
        "has_more": has_more,
        "next_start_time": processed_until if has_more else None,
        "chunks": chunks,
    }
