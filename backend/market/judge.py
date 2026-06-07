"""Judge: score agent output against the subtask (single GCP call, JSON)."""

import json

import weave

from backend.config import JUDGE_MODEL
from backend.infra.model_router import generate

_RUBRIC = (
    "You are a fair, generous-but-calibrated evaluator of an AI agent's work. Score how "
    "well OUTPUT completes TASK from 0.0 to 1.0 using these anchored bands:\n"
    "  0.90-1.00  Excellent: fully completes the task, accurate and directly usable as-is.\n"
    "  0.75-0.89  Good: clearly on-task and useful, only minor gaps or polish needed.\n"
    "  0.60-0.74  Adequate: usable core but with notable gaps, omissions, or small errors.\n"
    "  0.45-0.59  Partial/mismatched: not quite the right deliverable or the wrong kind of "
    "work, but coherent, well-formed, and tangentially useful - give it the benefit of the doubt.\n"
    "  0.20-0.44  Poor: barely relevant or largely incorrect, though still a real attempt.\n"
    "  0.00-0.19  Failing: empty, incoherent, off-topic, a refusal, or asks for input instead "
    "of attempting the work.\n"
    "Guidelines:\n"
    "- Be generous to good-faith, coherent attempts; reserve the bottom band for outputs that "
    "are empty, garbled, refusals, or completely off-topic.\n"
    "- A coherent attempt that misses the intended task but still offers something useful "
    "belongs around 0.5, not near zero.\n"
    "- Judge substance and correctness, not length or verbosity.\n"
    "- When TASK is underspecified, reward a sensible attempt that states its assumptions; "
    "do not punish reasonable assumptions.\n"
    "- Start from the band that best fits, then nudge within it; avoid defaulting to 0 or 1.\n"
)


@weave.op
def judge(subtask_text: str, output: str) -> tuple[float, str]:
    prompt = (
        f"{_RUBRIC}\n"
        'Reply ONLY JSON: {"score": <float 0.0-1.0>, "reason": "<one concise sentence>"}.\n\n'
        f"TASK:\n{subtask_text}\n\nOUTPUT:\n{output}\n"
    )
    raw = generate(JUDGE_MODEL, "gcp", prompt)["output"]
    try:
        data = json.loads(raw[raw.find("{") : raw.rfind("}") + 1])
        return max(0.0, min(1.0, float(data["score"]))), str(data.get("reason", ""))
    except Exception:
        return 0.5, "judge parse fallback"
