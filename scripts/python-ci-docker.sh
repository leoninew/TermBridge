#!/usr/bin/env bash
set -euo pipefail

IMAGE_NAME="${IMAGE_NAME:-termbridge-python-ci:3.11-buster-cn}"
CONTAINER_NAME="${CONTAINER_NAME:-termbridge-python-ci-cn}"
BASE_IMAGE="${BASE_IMAGE:-python:3.11-buster}"
PYPI_INDEX_URL="${PYPI_INDEX_URL:-https://pypi.tuna.tsinghua.edu.cn/simple}"
DEBIAN_MIRROR="${DEBIAN_MIRROR:-mirrors.tuna.tsinghua.edu.cn}"
WORKDIR="/workspace"
VENV_DIR="/opt/termbridge-venv"
UV_CACHE_DIR="/opt/uv-cache"

# Git Bash/MSYS rewrites POSIX-looking Docker arguments like /workspace into
# Windows paths unless disabled, which breaks Linux container workdir values.
export MSYS_NO_PATHCONV="${MSYS_NO_PATHCONV:-1}"

usage() {
  cat <<'USAGE'
Usage: scripts/python-ci-docker.sh [all|init|ruff|mypy|pytest|shell|stop|rm]

Runs the Python CI checks in a reusable Docker container.

Commands:
  all      Build image if needed, start/reuse the container, initialize deps, then run ruff, mypy, pytest (default)
  init     Build image if needed, start/reuse the container, and initialize deps only
  ruff     Run ruff check .
  mypy     Run mypy src tests
  pytest   Run pytest
  shell    Open an interactive shell in the reusable container
  stop     Stop the reusable container
  rm       Remove the reusable container

Environment overrides:
  IMAGE_NAME       Docker image tag (default: termbridge-python-ci:3.11-buster-cn)
  CONTAINER_NAME   Docker container name (default: termbridge-python-ci-cn)
  BASE_IMAGE       Base image used when building (default: python:3.11-buster)
  PYPI_INDEX_URL   Python package index URL (default: Tsinghua PyPI mirror)
  DEBIAN_MIRROR    Debian mirror host (default: mirrors.tuna.tsinghua.edu.cn)
USAGE
}

log() {
  printf '\n==> %s\n' "$1"
}

repo_root() {
  git rev-parse --show-toplevel
}

docker_mount_path() {
  local path="$1"
  if command -v cygpath >/dev/null 2>&1; then
    cygpath -w "$path"
  else
    printf '%s\n' "$path"
  fi
}

image_exists() {
  docker image inspect "$IMAGE_NAME" >/dev/null 2>&1
}

container_exists() {
  docker container inspect "$CONTAINER_NAME" >/dev/null 2>&1
}

container_running() {
  [ "$(docker inspect -f '{{.State.Running}}' "$CONTAINER_NAME" 2>/dev/null || true)" = "true" ]
}

build_image_if_missing() {
  if image_exists; then
    log "Docker image already exists: $IMAGE_NAME"
    return
  fi

  log "Docker image is missing; building $IMAGE_NAME from $BASE_IMAGE"
  docker build -t "$IMAGE_NAME" -f - . <<DOCKERFILE
FROM ${BASE_IMAGE}
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_INDEX_URL=${PYPI_INDEX_URL} \
    UV_INDEX_URL=${PYPI_INDEX_URL} \
    UV_CACHE_DIR=${UV_CACHE_DIR} \
    UV_PROJECT_ENVIRONMENT=${VENV_DIR} \
    PATH="${VENV_DIR}/bin:/root/.local/bin:\$PATH"
RUN if [ -f /etc/apt/sources.list ]; then \
      sed -i 's|deb.debian.org|${DEBIAN_MIRROR}|g; s|security.debian.org|${DEBIAN_MIRROR}|g' /etc/apt/sources.list; \
    fi \
    && if [ -f /etc/apt/sources.list.d/debian.sources ]; then \
      sed -i 's|deb.debian.org|${DEBIAN_MIRROR}|g; s|security.debian.org|${DEBIAN_MIRROR}|g' /etc/apt/sources.list.d/debian.sources; \
    fi \
    && python -m pip install --no-cache-dir --upgrade pip uv
WORKDIR ${WORKDIR}
CMD ["sleep", "infinity"]
DOCKERFILE
}

start_container() {
  local root
  root="$(repo_root)"

  if container_running; then
    log "Docker container is already running: $CONTAINER_NAME"
    return
  fi

  if container_exists; then
    log "Starting existing Docker container: $CONTAINER_NAME"
    docker start "$CONTAINER_NAME" >/dev/null
    return
  fi

  log "Creating and starting reusable Docker container: $CONTAINER_NAME"
  docker run -d \
    --name "$CONTAINER_NAME" \
    -v "$(docker_mount_path "$root"):${WORKDIR}" \
    -w "$WORKDIR" \
    "$IMAGE_NAME" >/dev/null
}

docker_exec_flags() {
  if [ -t 0 ] && [ -t 1 ]; then
    printf '%s\n' '-it'
  else
    printf '%s\n' '-i'
  fi
}

exec_in_container() {
  docker exec $(docker_exec_flags) \
    -e PIP_INDEX_URL="$PYPI_INDEX_URL" \
    -e UV_INDEX_URL="$PYPI_INDEX_URL" \
    -e UV_PROJECT_ENVIRONMENT="$VENV_DIR" \
    -e UV_CACHE_DIR="$UV_CACHE_DIR" \
    -w "$WORKDIR" \
    "$CONTAINER_NAME" \
    bash -lc "$1"
}

ensure_environment() {
  log "Checking Python environment readiness"
  exec_in_container "
    set -euo pipefail
    mkdir -p '$VENV_DIR' '$UV_CACHE_DIR'
    current_hash=\$(sha256sum pyproject.toml uv.lock | sha256sum | cut -d' ' -f1)
    marker='$VENV_DIR/.termbridge-env.sha'
    if [ ! -x '$VENV_DIR/bin/python' ] || [ ! -f \"\$marker\" ] || [ \"\$(cat \"\$marker\" 2>/dev/null || true)\" != \"\$current_hash\" ]; then
      echo 'Python environment is not ready; running uv sync --locked --dev'
      uv sync --locked --dev
      printf '%s\n' \"\$current_hash\" > \"\$marker\"
    else
      echo 'Python environment is ready; skipping dependency sync'
    fi
  "
}

run_step() {
  local name="$1"
  local command="$2"
  log "Running ${name}"
  exec_in_container "$command"
}

prepare() {
  build_image_if_missing
  start_container
}

run_all() {
  prepare
  ensure_environment
  run_step "Ruff" "uv run ruff check ."
  run_step "mypy" "uv run mypy src tests"
  run_step "pytest" "uv run pytest"
}

command="${1:-all}"
case "$command" in
  all)
    run_all
    ;;
  init)
    prepare
    ensure_environment
    ;;
  ruff)
    prepare
    ensure_environment
    run_step "Ruff" "uv run ruff check ."
    ;;
  mypy)
    prepare
    ensure_environment
    run_step "mypy" "uv run mypy src tests"
    ;;
  pytest)
    prepare
    ensure_environment
    run_step "pytest" "uv run pytest"
    ;;
  shell)
    prepare
    ensure_environment
    exec_in_container "exec bash"
    ;;
  stop)
    if container_exists; then
      log "Stopping Docker container: $CONTAINER_NAME"
      docker stop "$CONTAINER_NAME" >/dev/null
    else
      log "Docker container does not exist: $CONTAINER_NAME"
    fi
    ;;
  rm)
    if container_exists; then
      log "Removing Docker container: $CONTAINER_NAME"
      docker rm -f "$CONTAINER_NAME" >/dev/null
    else
      log "Docker container does not exist: $CONTAINER_NAME"
    fi
    ;;
  -h|--help|help)
    usage
    ;;
  *)
    usage >&2
    exit 2
    ;;
esac
