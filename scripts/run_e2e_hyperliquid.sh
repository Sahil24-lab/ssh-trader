#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "${ROOT_DIR}"

PYTHON_BIN="${PYTHON_BIN:-}"
if [[ -z "${PYTHON_BIN}" ]]; then
  if [[ -x ".venv/bin/python" ]]; then
    PYTHON_BIN=".venv/bin/python"
  else
    PYTHON_BIN="python"
  fi
fi

COIN="${COIN:-BTC}"
INTERVAL="${INTERVAL:-1h}"
START="${START:-}"
END="${END:-}"
LOOKBACK_DAYS="${LOOKBACK_DAYS:-180}"
BASE_URL="${BASE_URL:-https://api.hyperliquid.xyz}"
OUT_DIR="${OUT_DIR:-out}"
DATA_DIR="${DATA_DIR:-}"
DATA_CSV="${DATA_CSV:-}"
DATA_CSV_4H="${DATA_CSV_4H:-}"
TITLE="${TITLE:-${COIN} Hyperliquid End-to-End Report}"
SKIP_FETCH="${SKIP_FETCH:-0}"
INITIAL_NAV="${INITIAL_NAV:-10000}"

usage() {
  cat <<EOF
Usage: $(basename "$0") [options]

Options:
  --coin <symbol>         Coin symbol (default: ${COIN})
  --interval <tf>         Candle interval (default: ${INTERVAL})
  --start <time>          Start time ISO8601 or ms (default: env START)
  --end <time>            End time ISO8601 or ms (default: env END)
  --lookback-days <n>     If START/END not set, use last N days (default: ${LOOKBACK_DAYS})
  --base-url <url>        Hyperliquid API URL (default: ${BASE_URL})
  --data-dir <path>       Data output dir (default: data/)
  --data-csv <path>       Data CSV path (default: ${DATA_CSV})
  --data-csv-4h <path>    Optional 4H CSV path (default: ${DATA_CSV_4H})
  --out-dir <path>        Output directory (default: ${OUT_DIR})
  --initial-nav <n>       Backtest starting NAV (default: ${INITIAL_NAV})
  --title <text>          Dashboard title
  --skip-fetch            Skip data fetch, use existing CSV
  -h, --help              Show this help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --coin) COIN="$2"; shift 2 ;;
    --interval) INTERVAL="$2"; shift 2 ;;
    --start) START="$2"; shift 2 ;;
    --end) END="$2"; shift 2 ;;
    --lookback-days) LOOKBACK_DAYS="$2"; shift 2 ;;
    --base-url) BASE_URL="$2"; shift 2 ;;
    --data-dir) DATA_DIR="$2"; shift 2 ;;
    --data-csv) DATA_CSV="$2"; shift 2 ;;
    --data-csv-4h) DATA_CSV_4H="$2"; shift 2 ;;
    --out-dir) OUT_DIR="$2"; shift 2 ;;
    --initial-nav) INITIAL_NAV="$2"; shift 2 ;;
    --title) TITLE="$2"; shift 2 ;;
    --skip-fetch) SKIP_FETCH="1"; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1"; usage; exit 1 ;;
  esac
done

if [[ "${INTERVAL}" != "1h" ]]; then
  echo "error: TA-01 pipeline currently supports --interval 1h only (got: ${INTERVAL})" >&2
  exit 1
fi

COIN_LOWER="$(printf '%s' "${COIN}" | tr '[:upper:]' '[:lower:]')"

if [[ -z "${DATA_DIR}" ]]; then
  if [[ -n "${DATA_CSV}" ]]; then
    DATA_DIR="$(dirname "${DATA_CSV}")"
  else
    DATA_DIR="data"
  fi
fi

if [[ -z "${DATA_CSV}" ]]; then
  DATA_CSV="${DATA_DIR}/hyperliquid_${COIN_LOWER}_1h.csv"
fi

if [[ -z "${DATA_CSV_4H}" ]]; then
  DATA_CSV_4H="${DATA_DIR}/hyperliquid_${COIN_LOWER}_4h.csv"
fi

if [[ -z "${START}" ]] || [[ -z "${END}" ]]; then
  if [[ -z "${LOOKBACK_DAYS}" ]] || [[ "${LOOKBACK_DAYS}" -le 0 ]]; then
    echo "error: LOOKBACK_DAYS must be positive" >&2
    exit 1
  fi
  END="$("${PYTHON_BIN}" - <<'PY'
from datetime import datetime, timezone
print(datetime.now(tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"))
PY
)"
  START="$("${PYTHON_BIN}" - <<PY
from datetime import datetime, timedelta, timezone
end = datetime.now(tz=timezone.utc).replace(microsecond=0)
start = end - timedelta(days=int("${LOOKBACK_DAYS}"))
print(start.isoformat().replace("+00:00", "Z"))
PY
)"
fi

mkdir -p "${DATA_DIR}" "${OUT_DIR}"

if [[ "${SKIP_FETCH}" != "1" ]]; then
  echo "[1/6] Fetching Hyperliquid 1H + resampling deterministic 4H -> ${DATA_CSV} / ${DATA_CSV_4H}"
  "${PYTHON_BIN}" scripts/fetch_hyperliquid_multitf.py \
    --coin "${COIN}" \
    --start "${START}" \
    --end "${END}" \
    --base-url "${BASE_URL}" \
    --output-dir "${DATA_DIR}" \
    --fill-missing
else
  echo "[1/6] Skipping fetch; using existing ${DATA_CSV}"
  if [[ ! -f "${DATA_CSV}" ]]; then
    echo "error: --skip-fetch set but data CSV does not exist: ${DATA_CSV}" >&2
    echo "tip: run without --skip-fetch first, or pass --data-csv to an existing file." >&2
    exit 1
  fi
  if [[ ! -f "${DATA_CSV_4H}" ]]; then
    echo "[1/6] 4H CSV missing; resampling -> ${DATA_CSV_4H}"
    "${PYTHON_BIN}" scripts/resample_ohlcv_csv.py \
      --csv "${DATA_CSV}" \
      --timeframe "1h" \
      --out-timeframe "4h" \
      --fill-missing \
      --output "${DATA_CSV_4H}"
  fi
fi

# Require at least header + 1 row.
if [[ ! -f "${DATA_CSV}" ]] || [[ "$(wc -l < "${DATA_CSV}")" -lt 2 ]]; then
  echo "error: data CSV is empty: ${DATA_CSV}" >&2
  echo "tip: try a smaller fetch window first (e.g. START=2024-01-01 END=2024-02-01)." >&2
  exit 1
fi

if [[ ! -f "${DATA_CSV_4H}" ]] || [[ "$(wc -l < "${DATA_CSV_4H}")" -lt 2 ]]; then
  echo "error: 4H CSV is empty: ${DATA_CSV_4H}" >&2
  exit 1
fi

echo "[2/6] Running nav replay"
"${PYTHON_BIN}" -m ssh_trader.nav.replay \
  --csv "${DATA_CSV}" \
  --timeframe "${INTERVAL}" \
  --fill-missing \
  --output "${OUT_DIR}/nav_regimes.csv"

echo "[3/6] Running backtest"
"${PYTHON_BIN}" -m ssh_trader.backtest.run \
  --csv "${DATA_CSV}" \
  --timeframe "${INTERVAL}" \
  --fill-missing \
  --initial-nav "${INITIAL_NAV}" \
  --output-metrics "${OUT_DIR}/metrics.csv" \
  --output-bars "${OUT_DIR}/bars.csv" \
  --output-trades "${OUT_DIR}/trades.csv"

echo "[4/6] Running shadow mode"
"${PYTHON_BIN}" -m ssh_trader.live.shadow_runner \
  --csv "${DATA_CSV}" \
  --timeframe "${INTERVAL}" \
  --fill-missing \
  --output "${OUT_DIR}/shadow_log.csv"

echo "[5/6] Dumping TA feature columns"
"${PYTHON_BIN}" scripts/dump_ta_features.py \
  --csv-1h "${DATA_CSV}" \
  --csv-4h "${DATA_CSV_4H}" \
  --fill-missing \
  --output "${OUT_DIR}/ta_features.csv"

echo "[6/6] Building dashboard"
"${PYTHON_BIN}" scripts/build_dashboard.py \
  --title "${TITLE}" \
  --bars "${OUT_DIR}/bars.csv" \
  --metrics "${OUT_DIR}/metrics.csv" \
  --shadow "${OUT_DIR}/shadow_log.csv" \
  --trades "${OUT_DIR}/trades.csv" \
  --ta-features "${OUT_DIR}/ta_features.csv" \
  --output "${OUT_DIR}/dashboard.html"

echo "Done."
echo "Dashboard: ${OUT_DIR}/dashboard.html"
echo "Replay CSV: ${OUT_DIR}/nav_regimes.csv"
echo "Backtest metrics: ${OUT_DIR}/metrics.csv"
echo "Backtest bars: ${OUT_DIR}/bars.csv"
echo "Backtest trades: ${OUT_DIR}/trades.csv"
echo "Shadow log: ${OUT_DIR}/shadow_log.csv"
echo "TA features: ${OUT_DIR}/ta_features.csv"
echo "Data 1H: ${DATA_CSV}"
echo "Data 4H: ${DATA_CSV_4H}"
