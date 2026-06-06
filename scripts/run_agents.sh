#!/usr/bin/env bash
# Launch all six seed agents on ports 9001-9006 (matches seed_agents.service_url).
set -euo pipefail
cd "$(dirname "$0")/.."

declare -a AGENTS=(
  "writer-01:9001"
  "coder-01:9002"
  "summarizer-01:9003"
  "factcheck-01:9004"
  "translator-01:9005"
  "planner-01:9006"
)

pids=()
cleanup() {
  for pid in "${pids[@]}"; do
    kill "$pid" 2>/dev/null || true
  done
}
trap cleanup EXIT INT TERM

for spec in "${AGENTS[@]}"; do
  IFS=: read -r agent_id port <<< "$spec"
  AGENT_ID="$agent_id" PORT="$port" python -m backend.agent.main &
  pids+=($!)
  echo "started agent:$agent_id on :$port (pid $!)"
done

echo "agents running; Ctrl+C to stop"
wait
