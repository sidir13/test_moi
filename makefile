# Project automation for Mémoire des Territoires

IMAGE_NAME ?= memoire-des-territoires-app
GITHUB_PROFILE ?= julienRactM
GITHUB_HOST ?= laplateformeio
ENV_FILE ?= .env
APP_DIR ?= app
PLATFORM ?= linux

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

.PHONY: ensure-env ensure-app  install-uv install-mac build docker-build build-mac docker-run run-mac docker-refresh refresh-mac docker-push

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

install-mac:
	$(MAKE) install PLATFORM=mac

build: docker-build

docker-build: ensure-env
	docker build --platform $(DOCKER_PLATFORM) -t $(IMAGE_NAME):latest -f Dockerfile .

build-mac:
	$(MAKE) docker-build PLATFORM=mac

run: docker-run

docker-run: ensure-env
	docker run --rm --platform $(DOCKER_PLATFORM) -p 8000:8000 --env-file $(ENV_FILE) $(IMAGE_NAME):latest

run-mac:
	$(MAKE) docker-run PLATFORM=mac

refresh: docker-refresh

docker-refresh:
	$(MAKE) uv-install
	$(MAKE) install PLATFORM=$(PLATFORM)
	$(MAKE) docker-build PLATFORM=$(PLATFORM)
	$(MAKE) docker-run PLATFORM=$(PLATFORM)

refresh-mac:
	$(MAKE) docker-refresh PLATFORM=mac

docker-push:
	@if [ -z "$(GITPAT)" ]; then \
		echo "Set GITPAT=your_token"; \
		exit 1; \
	fi
	echo $(GITPAT) | docker login ghcr.io -u $(GITHUB_PROFILE) --password-stdin
	docker tag $(IMAGE_NAME):latest ghcr.io/$(GITHUB_HOST)/$(IMAGE_NAME):latest
	docker push ghcr.io/$(GITHUB_HOST)/$(IMAGE_NAME):latest
