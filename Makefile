.PHONY: help install backend frontend build

help:
	@printf "Available commands:\n"
	@printf "  make install   Install frontend and backend dependencies\n"
	@printf "  make backend   Start backend API on 127.0.0.1:9008 with reload\n"
	@printf "  make frontend  Start frontend Vite dev server on 127.0.0.1:9007\n"
	@printf "  make build     Build frontend assets and Python distributions\n"
	@printf "  make help      Show this help message\n"

install:
	cd frontend && yarn install
	uv sync

backend:
	uv run python -m termbridge.main --host 127.0.0.1 --port 9008 --reload

frontend:
	cd frontend && yarn dev

build:
	cd frontend && yarn build
	rm -rf src/termbridge/static
	cp -R frontend/dist src/termbridge/static
	uv build

