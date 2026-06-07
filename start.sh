#!/usr/bin/env bash
# Start both the uvicorn API server and all agents with logs displayed
set -euo pipefail
cd "$(dirname "$0")"

echo "Starting Anex services..."
echo "========================"

# Array to track background process PIDs
pids=()

# Cleanup function to kill all processes on exit
cleanup() {
  echo ""
  echo "Shutting down services..."
  for pid in "${pids[@]}"; do
    kill "$pid" 2>/dev/null || true
  done
  exit 0
}
trap cleanup EXIT INT TERM

# Start uvicorn API server
echo "Starting API server on http://0.0.0.0:8000 with 4 workers..."
uvicorn backend.api.app:app --host 0.0.0.0 --port 8000 --workers 4 &
api_pid=$!
pids+=($api_pid)
echo "API server started (pid $api_pid)"

# Give the API server a moment to start
sleep 2

# Start all agents
echo ""
echo "Starting all 30 agents..."
./scripts/run_agents.sh &
agents_pid=$!
pids+=($agents_pid)
echo "Agents script started (pid $agents_pid)"

echo ""
echo "========================"
echo "All services running!"
echo "API Server: http://0.0.0.0:8000"
echo "Agents: ports 9001-9030"
echo "Press Ctrl+C to stop all services"
echo "========================"
echo ""

# Wait for all background processes
wait