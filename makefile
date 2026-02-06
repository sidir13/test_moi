.PHONY: uv-install
uv-install:
	cd $(PROJECT_ROOT) && pip install uv

.PHONY: uv-install-mac
uv-install-mac:
	cd $(PROJECT_ROOT) && brew install uv

.PHONY: install
install: uv-install
	pass

.PHONY: docker-build
docker-build:
	pass

.PHONY: docker-run
docker-run:
	pass

.PHONY: docker-refresh
docker-refresh: uv-install install docker-build docker-run