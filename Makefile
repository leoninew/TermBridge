SHELL := bash
.SHELLFLAGS := -eu -o pipefail -c
.DEFAULT_GOAL := help

UV ?= uv
UV_RUN ?= $(UV) run --locked --no-sync
CHECK_FIX := $(filter 1 true yes,$(fix))
RUFF_FORMAT_ARGS := --check
RUFF_CHECK_ARGS :=

ifneq ($(CHECK_FIX),)
RUFF_FORMAT_ARGS :=
RUFF_CHECK_ARGS := --fix
endif

ARGS := $(wordlist 2,$(words $(MAKECMDGOALS)),$(MAKECMDGOALS))
RELEASE_VERSION := $(if $(VERSION),$(VERSION),$(firstword $(ARGS)))

.PHONY: help deps install run dev-backend dev-frontend check test build release clean

help:
	@printf "Available targets:\n"
	@printf "  deps          Sync locked Python dependencies\n"
	@printf "  install       Install web and Python dependencies\n"
	@printf "  run           Start both development servers\n"
	@printf "  dev-backend   Start the FastAPI backend with reload\n"
	@printf "  dev-frontend  Start the web dev server\n"
	@printf "  check         Check format, lint, and types; use fix=1 to apply fixes\n"
	@printf "  test          Run pytest\n"
	@printf "  build         Build web assets and Python distributions\n"
	@printf "  release       Upload dist artifacts, with VERSION=<version> or positional version\n"
	@printf "  clean         Remove local build and cache artifacts\n"

deps:
	$(UV) sync --all-groups --locked

install:
	cd web && yarn install
	$(UV) sync --group dev

run:
	rm -rf src/termbridge/static
	$(UV) run python scripts/run.py

dev-backend:
	$(UV) run python -m termbridge.main --host 127.0.0.1 --port 9008 --reload

dev-frontend:
	cd web && yarn dev

check:
	$(UV_RUN) ruff format $(RUFF_FORMAT_ARGS) src tests
	$(UV_RUN) ruff check $(RUFF_CHECK_ARGS) src tests
	$(UV_RUN) mypy src

test:
	$(UV_RUN) pytest

build:
	cd web && yarn build
	rm -rf src/termbridge/static
	cp -R web/dist src/termbridge/static
	$(UV) build

release:
	if [ -z "$(RELEASE_VERSION)" ]; then echo "VERSION is required"; exit 1; fi
	if [ ! -f "dist/termbridge-$(RELEASE_VERSION).tar.gz" ]; then echo "Missing tar.gz"; exit 1; fi
	if [ ! -f "dist/termbridge-$(RELEASE_VERSION)-py3-none-any.whl" ]; then echo "Missing whl"; exit 1; fi
	uvx --env-file .env twine upload --non-interactive "dist/termbridge-$(RELEASE_VERSION).tar.gz" "dist/termbridge-$(RELEASE_VERSION)-py3-none-any.whl"

clean:
	find . -type d -name "__pycache__" -not -path "./.git/*" -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -not -path "./.git/*" -exec rm -rf {} +
	find . -type d -name ".ruff_cache" -not -path "./.git/*" -exec rm -rf {} +
	rm -rf dist build src/termbridge/static
	rm -f .coverage

%:
	@:
