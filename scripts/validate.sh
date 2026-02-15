#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

PYTHON_BIN="${PYTHON_BIN:-}"
if [[ -z "${PYTHON_BIN}" ]]; then
  if [[ -x ".venv/bin/python" ]]; then
    PYTHON_BIN=".venv/bin/python"
  else
    PYTHON_BIN="python"
  fi
fi

"${PYTHON_BIN}" -m pytest -q
"${PYTHON_BIN}" -m mypy src tests

if "${PYTHON_BIN}" -m ruff --version >/dev/null 2>&1; then
  "${PYTHON_BIN}" -m ruff check .
else
  echo "warning: ruff not found; install dev deps: pip install -e '.[dev]'" >&2
fi

if "${PYTHON_BIN}" -m black --version >/dev/null 2>&1; then
  "${PYTHON_BIN}" -m black --check .
else
  echo "warning: black not found; install dev deps: pip install -e '.[dev]'" >&2
fi
