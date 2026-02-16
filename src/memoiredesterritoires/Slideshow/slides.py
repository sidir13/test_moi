import os
from pathlib import Path
from typing import List

from PIL import Image
from moviepy.editor import AudioFileClip, ImageClip, concatenate_videoclips
from moviepy.video.fx.resize import resize


def clean_images(directory: Path) -> List[Path]:
    sanitized: List[Path] = []
    for filename in sorted(os.listdir(directory)):
        source = directory / filename
        if not source.is_file():
            continue
        target = source
        if source.suffix.lower() == ".webp":
            target = source.with_suffix(".jpg")
            img = Image.open(source).convert("RGB")
            img.save(target, "JPEG", quality=90)
            img.close()
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
    duration = audio_clip.duration
    slide_duration = duration / len(images)

    clips = []
    for img in images:
        clip = (
            ImageClip(str(img))
            .with_duration(slide_duration)
            .fx(resize, newsize=(1920, 1080))
        )
        clips.append(clip)

    video = concatenate_videoclips(clips, method="compose")
    final = video.set_audio(audio_clip)

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    final.write_videofile(str(output), fps=24)
    return str(output)
