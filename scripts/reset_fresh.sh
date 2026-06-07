#!/usr/bin/env bash
# Wipe all users + market data, re-seed IPO state, print localStorage reset steps.
set -euo pipefail
cd "$(dirname "$0")/.."

export WEAVE_DISABLED=1
export EMBEDDINGS_FAKE=1

echo "==> Resetting Postgres + Redis to a fresh market..."
python3 -m backend.tools.reset_fresh
