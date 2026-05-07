#!/bin/bash
set -euo pipefail

if pgrep -f "uvicorn app.main:app --host 0.0.0.0 --port 8000" >/dev/null 2>&1; then
  pkill -f "uvicorn app.main:app --host 0.0.0.0 --port 8000"
  echo "Stopped uvicorn app.main:app on port 8000."
  exit 0
fi

PIDS="$(lsof -ti :8000 || true)"
if [ -n "${PIDS}" ]; then
  kill ${PIDS}
  echo "Stopped process(es) on port 8000: ${PIDS}"
  exit 0
fi

echo "No running process found for uvicorn/port 8000."
