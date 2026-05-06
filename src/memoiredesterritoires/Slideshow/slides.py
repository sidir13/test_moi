from __future__ import annotations

import os
from pathlib import Path
from typing import List


def _import_moviepy():
    """Lazy import of moviepy to avoid slow startup."""
    global AudioFileClip, ImageClip, concatenate_videoclips, vfx, _HAS_NEW_API, _resize_fx
    try:  # MoviePy 2.x public API
        from moviepy import AudioFileClip, ImageClip, concatenate_videoclips  # type: ignore
        import moviepy.video.fx as vfx  # type: ignore
        _HAS_NEW_API = hasattr(ImageClip, "with_duration")
        _resize_fx = None
    except Exception:  # pragma: no cover - fallback for dev builds
        from moviepy.audio.io.AudioFileClip import AudioFileClip  # type: ignore
        from moviepy.video.VideoClip import ImageClip  # type: ignore
        from moviepy.video.compositing.concatenate import concatenate_videoclips  # type: ignore
        from moviepy.video.fx.resize import resize as _resize_fx  # type: ignore
        vfx = None  # type: ignore
        _HAS_NEW_API = False

AudioFileClip = ImageClip = concatenate_videoclips = vfx = _resize_fx = None  # type: ignore
_HAS_NEW_API = False


def _set_duration(clip, seconds: float):
    return clip.with_duration(seconds) if _HAS_NEW_API else clip.set_duration(seconds)


def _set_audio(video_clip, audio_clip):
    return video_clip.with_audio(audio_clip) if hasattr(video_clip, "with_audio") else video_clip.set_audio(audio_clip)


def _resize_to_1080p(clip):
    if _HAS_NEW_API and vfx:
        return clip.with_effects([vfx.Resize((1920, 1080))])
    if _resize_fx is None:
        raise RuntimeError("MoviePy resize effect not available")
    return clip.fx(_resize_fx, newsize=(1920, 1080))


def clean_images(directory: Path) -> List[Path]:
    """Convert WEBP images to JPG so MoviePy can ingest the folder safely."""
    from PIL import Image
    sanitized: List[Path] = []
    for filename in sorted(os.listdir(directory)):
        source = directory / filename
        if not source.is_file():
            continue

        target = source
        if source.suffix.lower() == ".webp":
            target = source.with_suffix(".jpg")
            with Image.open(source) as img:
                img.convert("RGB").save(target, "JPEG", quality=90)
            source.unlink()

        sanitized.append(target)

    return sanitized


def slideshow(image_dir: str, audio_file: str, output_path: str) -> str:
    """Create a slideshow video matching 100% of the audio duration."""
    _import_moviepy()
    directory = Path(image_dir)
    if not directory.exists():
        raise FileNotFoundError(f"Dossier d'images introuvable: {directory}")

    audio_source = Path(audio_file)
    if not audio_source.exists():
        raise FileNotFoundError(f"Audio introuvable: {audio_source}")

    images = clean_images(directory)
    if not images:
        raise ValueError("Aucune image fournie pour créer le diaporama.")

    audio_clip = AudioFileClip(str(audio_source))
    video_clip = None
    final_clip = None
    clips: List[ImageClip] = []
    try:
        duration = float(audio_clip.duration or 0.0)
        if duration <= 0:
            raise ValueError("Durée audio invalide pour le diaporama.")

        slide_duration = duration / len(images)
        for img in images:
            clip = ImageClip(str(img))
            clip = _set_duration(clip, slide_duration)
            clip = _resize_to_1080p(clip)
            clips.append(clip)

        video_clip = concatenate_videoclips(clips, method="compose")
        final_clip = _set_audio(video_clip, audio_clip)

        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        final_clip.write_videofile(str(output), fps=24)
        return str(output)
    finally:
        for clip in clips:
            try:
                clip.close()
            except Exception:
                pass
        if video_clip:
            try:
                video_clip.close()
            except Exception:
                pass
        if final_clip:
            try:
                final_clip.close()
            except Exception:
                pass
        audio_clip.close()
