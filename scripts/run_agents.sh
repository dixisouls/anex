#!/usr/bin/env bash
# Launch all 30 seed agents on ports 9001-9030 (matches seed_agents.service_url).
set -euo pipefail
cd "$(dirname "$0")/.."

declare -a AGENTS=(
  "writer-01:9001"
  "blogger-01:9002"
  "technical-writer-01:9003"
  "seo-writer-01:9004"
  "storyteller-01:9005"
  "marketer-01:9006"
  "social-media-01:9007"
  "coder-01:9008"
  "debugger-01:9009"
  "reviewer-01:9010"
  "devops-01:9011"
  "sql-analyst-01:9012"
  "security-01:9013"
  "researcher-01:9014"
  "analyst-01:9015"
  "factcheck-01:9016"
  "market-analyst-01:9017"
  "legal-analyst-01:9018"
  "translator-01:9019"
  "proofreader-01:9020"
  "summarizer-01:9021"
  "extractor-01:9022"
  "planner-01:9023"
  "strategist-01:9024"
  "product-manager-01:9025"
  "math-solver-01:9026"
  "scientist-01:9027"
  "economist-01:9028"
  "classifier-01:9029"
  "prompter-01:9030"
)

pids=()
cleanup() {
  echo "stopping all agents..."
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

echo ""
echo "all 30 agents running — Ctrl+C to stop"
wait
