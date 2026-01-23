## JUST TO KEEP TRACK OF THE MODELS DOWNLOADED, don't use it ##

FROM python:3.11-slim

# System deps
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*

# Put models inside your project-style path
# (inside the container this will be /app/models)
WORKDIR /app

# Hugging Face cache location (inside /app/models)
ENV HF_HOME=/app/models/.cache
ENV HUGGINGFACE_HUB_CACHE=/app/models/.cache
ENV TRANSFORMERS_CACHE=/app/models/.cache

# Install HF CLI
RUN pip install --no-cache-dir "huggingface_hub[cli]"

# Create models dir
RUN mkdir -p /app/models
WORKDIR /app/models

# If gated, prefer Docker build secrets (don’t bake tokens into image)
# RUN --mount=type=secret,id=hf_token \
#     huggingface-cli login --token "$(cat /run/secrets/hf_token)"

# Download models
RUN huggingface-cli download Qwen/Qwen3-TTS-Tokenizer-12Hz \
    --local-dir ./Qwen3-TTS-Tokenizer-12Hz

RUN huggingface-cli download Qwen/Qwen3-TTS-12Hz-1.7B-Base \
    --local-dir ./Qwen3-TTS-12Hz-1.7B-Base

RUN huggingface-cli download Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice \
    --local-dir ./Qwen3-TTS-12Hz-1.7B-CustomVoice