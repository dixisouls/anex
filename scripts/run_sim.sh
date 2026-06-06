#!/usr/bin/env bash
# Run sim poster/investor loops in a separate process (recommended for heavy load).
set -euo pipefail
cd "$(dirname "$0")/.."

exec python -m backend.sim.main "$@"
