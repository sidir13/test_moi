# Project automation for Mémoire des Territoires

IMAGE_NAME ?= memoire-des-territoires-app
GITHUB_PROFILE ?= julienRactM

ENV_FILE ?= .env
APP_DIR ?= app
PLATFORM ?= mac
QWEN_MODEL_DIR ?= models/qwen3-tts
QWEN_MODEL_ID ?= Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign

GITPAT ?= YourGITPAT

UV ?= uv
NPM ?= npm
PYTHON ?= python3

ifeq ($(PLATFORM),mac)
	DOCKER_PLATFORM := linux/arm64
else ifeq ($(PLATFORM),linux)
	DOCKER_PLATFORM := linux/amd64
else
$(error PLATFORM must be 'linux' or 'mac')
endif

.PHONY: ensure-env ensure-app  install-uv install-mac build docker-build build-mac docker-run run-mac docker-refresh docker-refresh-mac docker-push download-qwen-model dev

ensure-env:
	@test -f $(ENV_FILE) || (echo "Missing $(ENV_FILE). Copy from env.example" && exit 1)

ensure-app:
	@if [ ! -d $(APP_DIR) ]; then \
		mkdir -p $(APP_DIR); \
	fi

uv-install:
ifeq ($(PLATFORM), mac)
	brew install uv
else
	pip install uv
endif

install: ensure-env ensure-app
	$(UV) sync
	cd $(APP_DIR) && $(NPM) install --legacy-peer-deps
	cd $(APP_DIR) && $(NPM) run build
	$(MAKE) download-qwen-model

install-mac:
	$(MAKE) install PLATFORM=mac

download-qwen-model:
	$(PYTHON) scripts/download_qwen_tts.py --output-dir $(QWEN_MODEL_DIR) --model $(QWEN_MODEL_ID)

build: docker-build

docker-build: ensure-env
	cd $(APP_DIR) && $(NPM) install --legacy-peer-deps
	cd $(APP_DIR) && $(NPM) run build
	docker build --platform $(DOCKER_PLATFORM) -t $(IMAGE_NAME):latest -f Dockerfile .

build-mac:
	$(MAKE) docker-build PLATFORM=mac

run: docker-run

docker-run: ensure-env
	docker run --rm --platform $(DOCKER_PLATFORM) -p 8000:8000 --env-file $(ENV_FILE) -v $(CURDIR)/data:/app/data $(IMAGE_NAME):latest

run-mac:
	$(MAKE) docker-run PLATFORM=mac

refresh: docker-refresh

docker-refresh:
	$(MAKE) uv-install
	$(MAKE) install PLATFORM=$(PLATFORM)
	$(MAKE) download-qwen-model
	$(MAKE) docker-build PLATFORM=$(PLATFORM)
	$(MAKE) docker-run PLATFORM=$(PLATFORM)

docker-refresh-mac:
	$(MAKE) docker-refresh PLATFORM=mac



run-app: ensure-env ensure-app
	$(UV) sync
	cd $(APP_DIR) && $(NPM) install --legacy-peer-deps
	cd $(APP_DIR) && $(NPM) run build
	$(PYTHON) -m uv run uvicorn server.app:create_app --factory --host 0.0.0.0 --port 8000 --reload

dev: ensure-env ensure-app
	$(UV) sync
	cd $(APP_DIR) && $(NPM) install --legacy-peer-deps
	$(PYTHON) -m uv run uvicorn server.app:create_app --factory --host 0.0.0.0 --port 8000 --reload & cd $(APP_DIR) && $(NPM) run dev
