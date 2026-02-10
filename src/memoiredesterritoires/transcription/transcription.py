import base64
from pydub import AudioSegment
from openai import OpenAI
import os
from dotenv import load_dotenv
import tempfile
import math
import time
from typing import Optional

def transcribe_audio(
    audio_path: str,
    chunk_duration_s: int = 30,
    model: str = "google/gemini-3-flash-preview",
    delay_between_chunks: float = 2.0,
    max_retries: int = 3,
) -> str:
    """
    Transcribe a WAV file in chunks, adding continuous timestamps [mm:ss] to each line.
    
    Args:
        audio_path: Path to the audio file
        chunk_duration_s: Duration of each chunk in seconds
        model: Model to use for transcription
        delay_between_chunks: Delay in seconds between API calls to avoid rate limiting
        max_retries: Maximum number of retries per chunk on API errors
    """
    load_dotenv()
    client = OpenAI(
        api_key=os.getenv("ANTHROPIC_AUTH_TOKEN"),
        base_url="https://openrouter.ai/api/v1"
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

    chunk_duration_ms = int(chunk_duration_s) * 1000
    audio = AudioSegment.from_file(audio_path)

    # Split audio into chunks
    chunks = [
        audio[i:i + chunk_duration_ms]
        for i in range(0, len(audio), chunk_duration_ms)
    ]
    
    full_transcript = []
    cumulative_ms = 0  # cumulative time in milliseconds
    last_error: Optional[Exception] = None  # Track last error for debugging

    with tempfile.TemporaryDirectory() as tmpdir:
        for i, chunk in enumerate(chunks, 1):
            print(f"Chunk {i}/{len(chunks)} | durée = {len(chunk)/1000:.1f}s")
            chunk_path = os.path.join(tmpdir, f"chunk_{i}.wav")
            chunk.export(chunk_path, format="wav")

            with open(chunk_path, "rb") as f:
                encoded = base64.b64encode(f.read()).decode("utf-8")

            # Retry logic for API calls
            text: Optional[str] = None
            
            for attempt in range(1, max_retries + 1):
                try:
                    completion = client.chat.completions.create(
                        model=model,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {
                                "role": "user",
                                "content": [
                                    {"type": "text", "text": f"Transcris exactement ce segment audio n°{i}."},
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
                        timeout=60.0,  # 60s timeout per request
                    )

                    # Get plain text from LLM with validation
                    if not completion or not completion.choices or len(completion.choices) == 0:
                        print(f"⚠️  Chunk {i} (attempt {attempt}): API returned no choices")
                        if attempt < max_retries:
                            wait_time = 2 ** attempt  # Exponential backoff: 2s, 4s, 8s
                            print(f"   Retrying in {wait_time}s...")
                            time.sleep(wait_time)
                            continue
                        else:
                            print(f"   Skipping after {max_retries} attempts")
                            break
                    
                    message = completion.choices[0].message
                    if not message or not message.content:
                        print(f"⚠️  Chunk {i} (attempt {attempt}): API returned empty content")
                        if attempt < max_retries:
                            wait_time = 2 ** attempt
                            print(f"   Retrying in {wait_time}s...")
                            time.sleep(wait_time)
                            continue
                        else:
                            print(f"   Skipping after {max_retries} attempts")
                            break
                    
                    text = message.content.strip()
                    if not text:
                        print(f"⚠️  Chunk {i} (attempt {attempt}): Empty transcription")
                        if attempt < max_retries:
                            wait_time = 2 ** attempt
                            print(f"   Retrying in {wait_time}s...")
                            time.sleep(wait_time)
                            continue
                        else:
                            print(f"   Skipping after {max_retries} attempts")
                            break
                    
                    # Success!
                    if attempt > 1:
                        print(f"✓  Chunk {i} succeeded on attempt {attempt}")
                    break
                    
                except Exception as e:
                    last_error = e
                    print(f"⚠️  Chunk {i} (attempt {attempt}) error: {type(e).__name__}: {str(e)}")
                    if attempt < max_retries:
                        wait_time = 2 ** attempt
                        print(f"   Retrying in {wait_time}s...")
                        time.sleep(wait_time)
                    else:
                        print(f"   Failed after {max_retries} attempts, skipping chunk")
                        break
            
            # If we got text, process it
            if not text:
                print(f"⚠️  Chunk {i}: Skipped (no valid transcription after retries)")
                cumulative_ms += len(chunk)  # Still advance time
                continue
                
            lines = text.split("\n")  # split into lines for timestamping

            # Add continuous timestamps
            for line in lines:
                if not line.strip():
                    continue
                # compute mm:ss from cumulative_ms
                total_seconds = cumulative_ms // 1000
                mm = total_seconds // 60
                ss = total_seconds % 60
                full_transcript.append(f"[{mm:02d}:{ss:02d}] {line}")
                # Increment cumulative_ms assuming approx. even spacing
                # Here we divide chunk length evenly across lines
                cumulative_ms += len(chunk) // max(len(lines), 1)
            
            # Delay between chunks to avoid rate limiting (except for last chunk)
            if i < len(chunks) and delay_between_chunks > 0:
                time.sleep(delay_between_chunks)

    if not full_transcript:
        error_msg = f"Transcription failed: no valid chunks were transcribed out of {len(chunks)} chunks."
        error_msg += "\n  Possible causes:"
        error_msg += "\n  - API rate limiting (too many requests)"
        error_msg += "\n  - Model doesn't support audio input"
        error_msg += "\n  - Invalid API key or quota exceeded"
        error_msg += "\n  - Audio format not supported"
        if last_error:
            error_msg += f"\n  Last error: {type(last_error).__name__}: {str(last_error)}"
        raise ValueError(error_msg)
    
    print(f"✓ Transcription complete: {len(full_transcript)} lines from {len(chunks)} chunks")
    return "\n".join(full_transcript)
