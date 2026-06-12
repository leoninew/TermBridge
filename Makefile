.PHONY: help install fastapi web

help:
	@printf "Available commands:\n"
	@printf "  make install   Install web and fastapi dependencies\n"
	@printf "  make fastapi   Start fastapi API on 127.0.0.1:9008 with reload\n"
	@printf "  make web       Start frontend Vite dev server on 127.0.0.1:9007\n"
	@printf "  make build     Build web assets and Python distributions\n"
	@printf "  make help      Show this help message\n"

install:
	cd web && yarn install
	uv sync

fastapi:
	uv run python -m termbridge.main --host 127.0.0.1 --port 9008 --reload

web:
	cd web && yarn dev

build:
	cd web && yarn build
	rm -rf src/termbridge/static
	cp -R web/dist src/termbridge/static
	uv build

