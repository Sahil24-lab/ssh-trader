#!/usr/bin/env bash
set -euo pipefail

if ! command -v gitleaks >/dev/null 2>&1; then
  echo "gitleaks is not installed. Install it with: brew install gitleaks" >&2
  exit 1
fi

exec gitleaks git --pre-commit --staged --redact --no-banner
