FROM node:22-bookworm AS frontend-builder

WORKDIR /app/frontend
COPY frontend/package.json frontend/yarn.lock ./
RUN corepack enable && yarn install --frozen-lockfile
COPY frontend/ ./
RUN yarn build

FROM python:3.12-slim AS backend-builder

WORKDIR /app
RUN pip install --no-cache-dir uv
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --no-install-project --no-dev
COPY src ./src

FROM python:3.12-slim

WORKDIR /app
COPY --from=backend-builder /app/.venv /app/.venv
COPY pyproject.toml README.md ./
COPY src ./src
COPY --from=frontend-builder /app/frontend/dist ./src/termbridge/static

ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 9008
CMD ["python", "-m", "termbridge.main", "--host", "0.0.0.0", "--port", "9008"]
