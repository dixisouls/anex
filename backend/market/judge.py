"""Judge: score agent output against the subtask (single GCP call, JSON)."""

import json

import weave

from backend.config import GCP_CHAT_MODEL
from backend.infra.model_router import generate


@weave.op
def judge(subtask_text: str, output: str) -> tuple[float, str]:
    prompt = (
        "Score how well OUTPUT satisfies TASK from 0.0 to 1.0. "
        'Reply ONLY JSON: {"score": <float>, "reason": "<one line>"}.\n\n'
        f"TASK:\n{subtask_text}\n\nOUTPUT:\n{output}\n"
    )
    raw = generate(GCP_CHAT_MODEL, "gcp", prompt)["output"]
    try:
        data = json.loads(raw[raw.find("{") : raw.rfind("}") + 1])
        return max(0.0, min(1.0, float(data["score"]))), str(data.get("reason", ""))
    except Exception:
        return 0.5, "judge parse fallback"
