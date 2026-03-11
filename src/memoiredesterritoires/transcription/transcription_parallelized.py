import base64
import logging
from pydub import AudioSegment
from openai import OpenAI
import os
from dotenv import load_dotenv
import tempfile
import time
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)


def _transcribe_chunk(
    i,
    chunk,
    tmpdir,
    client,
    system_prompt,
    model,
    max_retries,
):
    """Worker function for parallel chunk transcription"""

    chunk_path = os.path.join(tmpdir, f"chunk_{i}.wav")
    chunk.export(chunk_path, format="wav")

    with open(chunk_path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("utf-8")

    last_error: Optional[Exception] = None

    for attempt in range(1, max_retries + 1):

        try:
            completion = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": f"Transcris exactement ce segment audio n°{i}."
                            },
                            {
                                "type": "input_audio",
                                "input_audio": {
                                    "data": encoded,
                                    "format": "wav"
                                }
                            }
                        ]
                    }
                ],
                timeout=60.0,
            )

            if not completion or not completion.choices:
                raise ValueError("No choices returned")

            message = completion.choices[0].message

            if not message or not message.content:
                raise ValueError("Empty response content")

            text = message.content.strip()

            if text:
                return i, text

        except Exception as e:
            last_error = e
            logger.warning(
                "Chunk error | chunk=%d attempt=%d error=%s",
                i,
                attempt,
                f"{type(e).__name__}: {e}",
            )

            if attempt < max_retries:
                wait = 2 ** attempt
                time.sleep(wait)

    logger.error("Chunk failed | chunk=%d", i)
    return i, None


def transcribe_audio(
    audio_path: str,
    chunk_duration_s: int = 30,
    model: str = "google/gemini-3-flash-preview",
    max_workers: int = 6,
    max_retries: int = 3,
) -> str:
    """
    Transcribe audio using parallel chunk processing.

    Args:
        audio_path: path to audio file
        chunk_duration_s: chunk duration
        model: OpenRouter model
        max_workers: number of parallel API calls
        max_retries: retries per chunk
    """

    load_dotenv()

    client = OpenAI(
        api_key=os.getenv("ANTHROPIC_AUTH_TOKEN"),
        base_url="https://openrouter.ai/api/v1",
    )

    system_prompt = """Tu es un système de transcription automatique.
Transcris fidèlement la parole humaine.
- Ne résume pas
- Ne reformule pas
- Ne corrige pas
- Garde les hésitations et répétitions
Répond uniquement par le texte transcrit en français."""

    if chunk_duration_s <= 0:
        raise ValueError("chunk_duration_s must be positive")

    audio = AudioSegment.from_file(audio_path)
    chunk_duration_ms = chunk_duration_s * 1000

    chunks = [
        audio[i:i + chunk_duration_ms]
        for i in range(0, len(audio), chunk_duration_ms)
    ]

    logger.info(
        "Transcription start | file=%s chunks=%d parallel_workers=%d",
        audio_path,
        len(chunks),
        max_workers,
    )

    results = {}

    with tempfile.TemporaryDirectory() as tmpdir:

        with ThreadPoolExecutor(max_workers=max_workers) as executor:

            futures = [
                executor.submit(
                    _transcribe_chunk,
                    i,
                    chunk,
                    tmpdir,
                    client,
                    system_prompt,
                    model,
                    max_retries,
                )
                for i, chunk in enumerate(chunks, 1)
            ]

            for future in as_completed(futures):
                i, text = future.result()
                results[i] = text

    # rebuild transcript in order
    full_transcript = []
    cumulative_ms = 0

    for i, chunk in enumerate(chunks, 1):

        text = results.get(i)

        if not text:
            logger.warning("Chunk skipped | chunk=%d", i)
            cumulative_ms += len(chunk)
            continue

        lines = text.split("\n")

        for line in lines:

            if not line.strip():
                continue

            total_seconds = cumulative_ms // 1000
            mm = total_seconds // 60
            ss = total_seconds % 60

            full_transcript.append(f"[{mm:02d}:{ss:02d}] {line}")

            cumulative_ms += len(chunk) // max(len(lines), 1)

    if not full_transcript:
        raise ValueError("Transcription failed: no valid chunks")

    logger.info(
        "Transcription finished | chunks=%d lines=%d",
        len(chunks),
        len(full_transcript),
    )

    return "\n".join(full_transcript)