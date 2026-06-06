"""
Assert every seed agent references a model listed in SEED_MODELS (FK-safe roster).

    python -m tests.0002_seed_models
    pytest tests/0002_seed_models.py
"""

from backend.market.seed_agents import SEED_AGENTS
from backend.market.seed_models import SEED_MODELS


def test_every_agent_model_is_listed():
    listed = {m["model_id"] for m in SEED_MODELS}
    assert {a.model for a in SEED_AGENTS} <= listed


if __name__ == "__main__":
    test_every_agent_model_is_listed()
    print("0002_seed_models passed.")
