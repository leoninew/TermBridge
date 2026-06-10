.PHONY: help backend frontend prepare wheel

help:
	@printf "Available commands:\n"
	@printf "  make backend   Start backend API on 127.0.0.1:9008 with reload\n"
	@printf "  make frontend  Start frontend Vite dev server on 127.0.0.1:9007\n"
	@printf "  make prepare        Install frontend and backend dependencies\n"
	@printf "  make wheel          Build frontend assets and wheel\n"
	@printf "  make help           Show this help message\n"

backend:
	uv run python -m termbridge.main --host 127.0.0.1 --port 9008 --reload

frontend:
	cd frontend && yarn dev

prepare:
	cd frontend && yarn install
	uv sync

wheel:
	cd frontend && yarn build
	rm -rf src/termbridge/static
	cp -R frontend/dist src/termbridge/static
	uv build
