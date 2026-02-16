#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

bash scripts/run_e2e_hyperliquid.sh "$@"

DASHBOARD_HTML="${DASHBOARD_HTML:-out/dashboard.html}"
CSV_PATH="${DATA_CSV:-data/hyperliquid_btc_1h.csv}"

echo "[dashboard] Serving ${DASHBOARD_HTML} with CSV ${CSV_PATH}"
./.venv/bin/python scripts/serve_dashboard.py --dashboard "${DASHBOARD_HTML}" --csv "${CSV_PATH}"
