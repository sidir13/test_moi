# Project automation for Mémoire des Territoires

IMAGE_NAME ?= memoire-des-territoires-app
GITHUB_PROFILE ?= julienRactM
GITHUB_HOST ?= laplateformeio
ENV_FILE ?= .env
APP_DIR ?= app
PLATFORM ?= linux
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

.PHONY: ensure-env ensure-app  install-uv install-mac build docker-build build-mac docker-run run-mac docker-refresh docker-refresh-mac docker-push download-qwen-model

ensure-env:
	@test -f $(ENV_FILE) || (echo "Missing $(ENV_FILE). Copy from env.example" && exit 1)

ensure-app:
	@if [ ! -d $(APP_DIR) ]; then \
		mkdir -p $(APP_DIR); \
	fi

uv-install:
	pip install uv

install: ensure-env ensure-app
	$(UV) sync
	cd $(APP_DIR) && $(NPM) install --legacy-peer-deps
	cd $(APP_DIR) && $(NPM) run build

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

docker-push:
	@if [ -z "$(GITPAT)" ]; then \
		echo "Set GITPAT=your_token"; \
		exit 1; \
	fi
	echo $(GITPAT) | docker login ghcr.io -u $(GITHUB_PROFILE) --password-stdin
	docker tag $(IMAGE_NAME):latest ghcr.io/$(GITHUB_HOST)/$(IMAGE_NAME):latest
	docker push ghcr.io/$(GITHUB_HOST)/$(IMAGE_NAME):latest

run-app: ensure-env ensure-app
	$(UV) sync
	cd $(APP_DIR) && $(NPM) install --legacy-peer-deps
	cd $(APP_DIR) && $(NPM) run build
	$(UV) run uvicorn server.app:create_app --factory --reload
