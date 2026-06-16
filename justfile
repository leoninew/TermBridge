set shell := ["bash", "-cu"]

install:
    cd web && yarn install
    uv sync --group dev

dev:
    rm -rf src/termbridge/static
    uv run python scripts/dev.py

dev-backend:
    uv run python -m termbridge.main --host 127.0.0.1 --port 9008 --reload

dev-frontend:
    cd web && yarn dev

check:
    uv run ruff check --fix src tests
    uv run ruff format src tests
    uv run mypy src

test:
    uv run pytest

build:
    cd web && yarn build
    rm -rf src/termbridge/static
    cp -R web/dist src/termbridge/static
    uv build

release VERSION:
    if [ -z "{{VERSION}}" ]; then echo "VERSION is required"; exit 1; fi
    if [ ! -f "dist/termbridge-{{VERSION}}.tar.gz" ]; then echo "Missing tar.gz"; exit 1; fi
    if [ ! -f "dist/termbridge-{{VERSION}}-py3-none-any.whl" ]; then echo "Missing whl"; exit 1; fi
    uvx twine upload "dist/termbridge-{{VERSION}}.tar.gz" "dist/termbridge-{{VERSION}}-py3-none-any.whl"

clean:
    find . -type d -name "__pycache__" -not -path "./.git/*" -exec rm -rf {} +
    find . -type d -name ".mypy_cache" -not -path "./.git/*" -exec rm -rf {} +
    find . -type d -name ".ruff_cache" -not -path "./.git/*" -exec rm -rf {} +
    rm -rf dist build src/termbridge/static
    rm -f .coverage
