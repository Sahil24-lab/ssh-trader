#!/usr/bin/env bash
set -euo pipefail

if ! command -v trivy >/dev/null 2>&1; then
  echo "trivy is not installed. Install it with: brew install trivy" >&2
  exit 1
fi

exec trivy fs \
  --severity HIGH,CRITICAL \
  --scanners vuln,misconfig \
  --exit-code 1 \
  --skip-dirs .git \
  --skip-dirs .venv \
  --skip-dirs data \
  --skip-dirs out \
  --skip-dirs trading-dashboard/node_modules \
  .
