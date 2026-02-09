#!/usr/bin/env python3
"""
Download the Qwen3 TTS model checkpoint into a local directory.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from huggingface_hub import snapshot_download


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch Qwen3 TTS weights locally.")
    parser.add_argument(
        "--model",
        default="Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign",
        help="Hugging Face repo id to download.",
    )
    parser.add_argument(
        "--output-dir",
        default="models/qwen3-tts",
        help="Directory where the checkpoint will be stored.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    dest = Path(args.output_dir).expanduser().resolve()
    dest.mkdir(parents=True, exist_ok=True)
    snapshot_download(
        repo_id=args.model,
        local_dir=str(dest),
        local_dir_use_symlinks=False,
        resume_download=True,
    )
    print(f"Model downloaded to {dest}")


if __name__ == "__main__":
    main()
