# === Frontend build ===
FROM node:20-slim AS frontend-builder
WORKDIR /frontend
COPY app/package*.json ./
RUN npm install --legacy-peer-deps
COPY app .
RUN npm run build

# === Backend deps ===
FROM python:3.12-slim AS python-deps
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends build-essential ffmpeg && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml uv.lock ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir "setuptools>=70" "wheel>=0.43"
COPY . /app
COPY models/ /app/models/
RUN pip install --no-cache-dir -e .

# === Runtime image ===
FROM python-deps AS runtime
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app:/app/src
WORKDIR /app
COPY --from=frontend-builder /frontend/dist ./app/dist
RUN ln -sfn /app/src/server /app/server
COPY docker-entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
EXPOSE 8000
ENTRYPOINT ["/entrypoint.sh"]
CMD ["uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "8000"]
