#!/bin/sh
set -eu

repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
uv_cache_dir=${UV_CACHE_DIR:-${TMPDIR:-/tmp}/teachcrm-uv-cache}

echo "[1/3] Backend quality and regression suite"
cd "$repo_root/backend"
UV_CACHE_DIR="$uv_cache_dir" uv run ruff check app tests
UV_CACHE_DIR="$uv_cache_dir" uv run mypy app
UV_CACHE_DIR="$uv_cache_dir" uv run pytest
UV_CACHE_DIR="$uv_cache_dir" uv run alembic current --check-heads

echo "[2/3] Frontend quality and production bundle"
cd "$repo_root/frontend"
npm run lint
npm test
npm run build

echo "[3/3] Repository integrity"
cd "$repo_root"
git diff --check
test -z "$(git status --porcelain)" || {
  echo "Рабочее дерево содержит незакоммиченные изменения" >&2
  git status --short >&2
  exit 1
}

echo "Release gate passed"
