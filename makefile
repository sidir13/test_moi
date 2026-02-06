PROJECT_ROOT := $(realpath ..)
IMAGE_NAME := memoiredesterritoires

.PHONY: uv-install
uv-install:
	cd $(PROJECT_ROOT) && pip install uv

.PHONY: uv-install-mac
uv-install-mac:
	cd $(PROJECT_ROOT) && brew install uv

.PHONY: install
install: uv-install
	uv sync

.PHONY: docker-build
docker-build:
	docker build -t $(IMAGE_NAME):latest .

.PHONY: docker-run
docker-run:
	docker run -p 8000:8000 --env-file .env $(IMAGE_NAME):latest

.PHONY: docker-refresh
docker-refresh: uv-install install docker-build docker-run