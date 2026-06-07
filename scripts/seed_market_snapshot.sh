#!/usr/bin/env bash
# Apply a realistic mid-session market (mixed trends, reps, trades, task history).
# Run ./scripts/reset_fresh.sh first.
set -euo pipefail
cd "$(dirname "$0")/.."

export WEAVE_DISABLED=1
export EMBEDDINGS_FAKE=1

echo "==> Applying market snapshot..."
python3 -m backend.tools.market_snapshot
