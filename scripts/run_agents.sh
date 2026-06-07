#!/usr/bin/env bash
# Launch a shared pool of generic agent workers. Every seeded agent's
# service_url points at one of these ports (round-robin); the broker passes the
# model config per dispatch, so any worker can execute any agent's task.
#
# Pool size + base port come from env (defaults match backend/config.py):
#   AGENT_WORKERS=16  AGENT_WORKER_BASE_PORT=9001
set -euo pipefail
cd "$(dirname "$0")/.."

WORKERS="${AGENT_WORKERS:-16}"
BASE_PORT="${AGENT_WORKER_BASE_PORT:-9001}"

pids=()
cleanup() {
  echo "stopping all agent workers..."
  for pid in "${pids[@]}"; do
    kill "$pid" 2>/dev/null || true
  done
}
trap cleanup EXIT INT TERM

for i in $(seq 0 $((WORKERS - 1))); do
  port=$((BASE_PORT + i))
  worker_id=$(printf "worker-%02d" "$((i + 1))")
  AGENT_ID="$worker_id" PORT="$port" python -m backend.agent.main &
  pids+=($!)
  echo "started $worker_id on :$port (pid $!)"
done

echo ""
echo "$WORKERS agent workers running on :$BASE_PORT-$((BASE_PORT + WORKERS - 1)) — Ctrl+C to stop"
wait
