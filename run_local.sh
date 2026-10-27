#!/usr/bin/env bash
# Start every service as its own local process. Ctrl+C stops them all.
set -euo pipefail
cd "$(dirname "$0")"

export DICE_URL="${DICE_URL:-http://localhost:8001}"
export CHARACTER_URL="${CHARACTER_URL:-http://localhost:8002}"
export COMBAT_URL="${COMBAT_URL:-http://localhost:8003}"

mkdir -p logs
PIDS=()

start() {  # name port
  python3 -m uvicorn main:app --app-dir "services/$1" --port "$2" --log-level warning \
    > "logs/$1.log" 2>&1 &
  PIDS+=($!)
  echo "started $1 on :$2 (pid $!)"
}

cleanup() { echo; echo "stopping services..."; kill "${PIDS[@]}" 2>/dev/null || true; }
trap cleanup EXIT INT TERM

start dice 8001
start character 8002
start combat 8003
start gateway 8000

echo "gateway ready: http://localhost:8000/docs  (logs in ./logs)"
wait
