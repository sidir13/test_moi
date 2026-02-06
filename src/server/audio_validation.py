"""Helpers for validating uploaded audio files."""

from __future__ import annotations

import io
import os
import tempfile
from pathlib import Path
from typing import Dict

import soundfile as sf
from pydub.utils import mediainfo

SUPPORTED_FORMATS = {
    "wav": {"wav", "wave"},
    "flac": {"flac"},
    "ogg": {"ogg"},
    "aiff": {"aiff", "aif"},
    "mp3": {"mp3"},
}


def validate_audio_file(filename: str, contents: bytes, max_bytes: int) -> Dict[str, object]:
    if len(contents) > max_bytes:
        raise ValueError("file too large")

    buffer = io.BytesIO(contents)
    detected_format = ""
    duration = 0.0
    samplerate = 0
    frames = 0
    try:
        with sf.SoundFile(buffer) as audio:
            frames = len(audio)
            samplerate = audio.samplerate or 1
            duration = frames / samplerate
            detected_format = (audio.format or "").lower()
    except RuntimeError:
        probe = _probe_with_ffprobe(filename, contents)
        detected_format = (probe.get("format_name") or "").split(",")[0].lower()
        duration = float(probe.get("duration") or 0.0)
        samplerate = int(float(probe.get("sample_rate") or 0) or 1)
        frames = int(duration * samplerate)
        if not detected_format:
            raise ValueError("invalid audio data")

    ext = Path(filename).suffix.lower().lstrip(".")
    if ext:
        allowed = SUPPORTED_FORMATS.get(ext, {ext})
        if detected_format and detected_format not in allowed:
            raise ValueError(f"extension {ext} does not match detected format {detected_format}")

    return {
        "frames": frames,
        "samplerate": samplerate,
        "duration": duration,
        "format": detected_format or ext,
    }


def _probe_with_ffprobe(filename: str, contents: bytes) -> Dict[str, str]:
    suffix = Path(filename).suffix or ".audio"
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(contents)
            tmp_path = tmp.name
        return mediainfo(tmp_path)
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)
