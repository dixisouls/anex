"""
Agent entrypoint. One image, parameterized by env.

    AGENT_ID=writer-01 PORT=9001 python -m backend.agent.main

See scripts/run_agents.sh to launch all 30 seed agents.
"""

import os

import uvicorn

from backend.agent.base import build_app

AGENT_ID = os.environ["AGENT_ID"]
PORT = int(os.environ.get("PORT", "9001"))

app = build_app(AGENT_ID)


def main() -> None:
    uvicorn.run(app, host="0.0.0.0", port=PORT)


if __name__ == "__main__":
    main()
