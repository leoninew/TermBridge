.PHONY: help install fastapi web dev build release

help:
	@printf "Available commands:\n"
	@printf "  make install   Install web and fastapi dependencies\n"
	@printf "  make fastapi   Start fastapi API on 127.0.0.1:9008 with reload\n"
	@printf "  make web       Start frontend Vite dev server on 127.0.0.1:9007\n"
	@printf "  make dev       Start fastapi and frontend dev servers\n"
	@printf "  make build     Build web assets and Python distributions\n"
	@printf "  make release VERSION=<version>\n"
	@printf "                 Upload matching dist artifacts to PyPI\n"
	@printf "  make help      Show this help message\n"

install:
	cd web && yarn install
	uv sync

fastapi:
	uv run python -m termbridge.main --host 127.0.0.1 --port 9008 --reload

web:
	cd web && yarn dev

dev:
	uv run python scripts/dev.py

build:
	cd web && yarn build
	rm -rf src/termbridge/static
	cp -R web/dist src/termbridge/static
	uv build

release:
ifndef VERSION
	$(error VERSION is required. Usage: make release VERSION=0.1.6)
endif
	@test -f "dist/termbridge-$(VERSION).tar.gz" || (printf "Missing dist/termbridge-$(VERSION).tar.gz\n"; exit 1)
	@test -f "dist/termbridge-$(VERSION)-py3-none-any.whl" || (printf "Missing dist/termbridge-$(VERSION)-py3-none-any.whl\n"; exit 1)
	uvx twine upload "dist/termbridge-$(VERSION).tar.gz" "dist/termbridge-$(VERSION)-py3-none-any.whl"

