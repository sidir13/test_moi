import os
from pathlib import Path
from typing import List

from PIL import Image

# ----------------------------
# MoviePy imports (compat)
# ----------------------------
try:
    # Newer MoviePy 2.x may expose these at top-level
    from moviepy import AudioFileClip, ImageClip, concatenate_videoclips
    import moviepy.video.fx as vfx  # has Resize class in newer 2.x
    _HAS_NEW_API = hasattr(ImageClip, "with_duration")
except Exception:
    # MoviePy 2.0.0.dev2 (and some builds) -> import from submodules
    from moviepy.audio.io.AudioFileClip import AudioFileClip
    from moviepy.video.VideoClip import ImageClip
    from moviepy.video.compositing.concatenate import concatenate_videoclips
    from moviepy.video.fx.resize import resize as _resize_fx
    _HAS_NEW_API = False


def _set_duration(clip, seconds: float):
    return clip.with_duration(seconds) if _HAS_NEW_API else clip.set_duration(seconds)


def _set_audio(video_clip, audio_clip):
    return video_clip.with_audio(audio_clip) if hasattr(video_clip, "with_audio") else video_clip.set_audio(audio_clip)


def _resize_to_1080p(clip):
    # Newer MoviePy 2.x: effects are classes
    if _HAS_NEW_API:
        return clip.with_effects([vfx.Resize((1920, 1080))])
    # dev2: fx function + .fx(...)
    return clip.fx(_resize_fx, newsize=(1920, 1080))


def clean_images(directory: Path) -> List[Path]:
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
    try:
        duration = float(audio_clip.duration)
        slide_duration = duration / len(images)

        clips = []
        for img in images:
            clip = ImageClip(str(img))
            clip = _set_duration(clip, slide_duration)
            clip = _resize_to_1080p(clip)
            clips.append(clip)

        video = concatenate_videoclips(clips, method="compose")
        final = _set_audio(video, audio_clip)

        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        final.write_videofile(str(output), fps=24)

        # Close to release file handles / ffmpeg resources
        final.close()
        video.close()
        for c in clips:
            c.close()

        return str(output)

    finally:
        audio_clip.close()