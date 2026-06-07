"""Generate a large specialist agent roster with Gemini 3.5 Flash.

One-time dev tool. The output is committed to data/generated_agents.json and
loaded at seed time, so runtime seeding never calls an LLM.

    python -m backend.market.gen_agents [total_agents]

For each of six domains it asks the model to invent distinct specialist agents
(name, skills, capability_text), then assigns ids, models, and margins. If the
LLM under-delivers or errors for a domain, a deterministic template fills the
gap so the script always produces a complete roster.
"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

from backend.config import GCP_CHAT_MODEL
from backend.infra.model_router import generate
from backend.market.seed_models import SEED_MODELS

DATA_DIR = Path(__file__).resolve().parent / "data"
OUT_PATH = DATA_DIR / "generated_agents.json"

# slug -> human domain description used in the generation prompt
DOMAINS: dict[str, str] = {
    "content": (
        "content creation and writing: marketing copy, blogs, documentation, "
        "scripts, social media, branding, UX writing, newsletters, ghostwriting"
    ),
    "engineering": (
        "software engineering: backend, frontend, data engineering, ML, "
        "infrastructure/devops, testing/QA, security, mobile, databases, APIs"
    ),
    "research": (
        "research and analysis: market, scientific, financial, competitive, "
        "legal, data, policy, UX, and intelligence research"
    ),
    "language": (
        "language tasks: translation, localization, proofreading, summarization, "
        "transcription cleanup, information extraction, copy editing, tone adaptation"
    ),
    "strategy": (
        "strategy and planning: product, business, go-to-market, operations, "
        "project management, growth, pricing, partnerships"
    ),
    "reasoning": (
        "reasoning and specialist analysis: mathematics, science, economics, "
        "classification, prompt engineering, logic, forecasting, optimization"
    ),
}

MODEL_IDS: list[str] = [m["model_id"] for m in SEED_MODELS]

_SKILL_POOL: dict[str, list[str]] = {
    "content": ["copywriting", "editing", "storytelling", "SEO", "brand voice", "scripts", "newsletters", "UX writing"],
    "engineering": ["python", "typescript", "APIs", "testing", "CI/CD", "databases", "performance", "refactoring"],
    "research": ["synthesis", "data analysis", "sourcing", "competitive analysis", "forecasting", "reporting", "fact-checking"],
    "language": ["translation", "localization", "proofreading", "summarization", "extraction", "tone", "grammar"],
    "strategy": ["roadmaps", "positioning", "prioritization", "pricing", "OKRs", "GTM", "operations"],
    "reasoning": ["math", "logic", "statistics", "modeling", "classification", "optimization", "prompt design"],
}


def _prompt(domain: str, n: int) -> str:
    return (
        f"Invent {n} DISTINCT specialist AI agents for an agent marketplace, all "
        f"within the domain of {domain}.\n"
        "Each agent must be a narrow, unique specialization - no duplicates and no "
        "generic 'assistant'. Vary the roles widely across the domain.\n"
        "Reply ONLY with a JSON list. Each element must be an object:\n"
        '{"name": "<2-4 word role title>", '
        '"skills": ["<5 short skill tags>"], '
        '"capability_text": "<3-4 sentences describing exactly what this agent does '
        'and excels at>"}'
    )


def _extract_json_list(raw: str) -> list:
    start = raw.find("[")
    end = raw.rfind("]") + 1
    if start < 0 or end <= start:
        return []
    try:
        data = json.loads(raw[start:end])
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _clean(items: list) -> list[dict]:
    out: list[dict] = []
    seen: set[str] = set()
    for it in items:
        if not isinstance(it, dict):
            continue
        name = str(it.get("name", "")).strip()
        cap = str(it.get("capability_text", "")).strip()
        skills = it.get("skills") or []
        skills = [str(s).strip() for s in skills if str(s).strip()][:6]
        if not name or not cap or not skills:
            continue
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append({"name": name, "skills": skills, "capability_text": cap})
    return out


def _template_agents(slug: str, count: int, start: int) -> list[dict]:
    """Deterministic fallback specialists so the roster is always complete."""
    pool = _SKILL_POOL[slug]
    rng = random.Random(f"tmpl:{slug}")
    out: list[dict] = []
    for k in range(count):
        skills = rng.sample(pool, k=min(5, len(pool)))
        focus = skills[0]
        out.append(
            {
                "name": f"{slug.capitalize()} Specialist {start + k}",
                "skills": skills,
                "capability_text": (
                    f"Specialist agent focused on {focus} within {slug}. "
                    f"Handles {', '.join(skills)} with precision and delivers "
                    f"production-ready results tailored to the request."
                ),
            }
        )
    return out


def _generate_domain(slug: str, domain: str, n: int) -> list[dict]:
    try:
        raw = generate(GCP_CHAT_MODEL, "gcp", _prompt(domain, n))["output"]
        items = _clean(_extract_json_list(raw))
        print(f"  {slug}: LLM returned {len(items)} valid agents")
    except Exception as exc:  # noqa: BLE001
        items = []
        print(f"  {slug}: LLM failed ({exc!r}); using templates")
    if len(items) < n:
        items += _template_agents(slug, n - len(items), start=len(items) + 1)
    return items[:n]


def build(total: int) -> list[dict]:
    per = max(1, total // len(DOMAINS))
    agents: list[dict] = []
    gi = 0
    for slug, domain in DOMAINS.items():
        print(f"generating {per} {slug} agents...")
        for j, spec in enumerate(_generate_domain(slug, domain, per), start=1):
            agents.append(
                {
                    "agent_id": f"{slug}-{j:03d}",
                    "name": spec["name"],
                    "skills": spec["skills"],
                    "capability_text": spec["capability_text"],
                    "model": MODEL_IDS[gi % len(MODEL_IDS)],
                    "margin": round(random.Random(f"{slug}-{j}").uniform(0.10, 0.35), 2),
                    "tools": [],
                    "category": slug,
                }
            )
            gi += 1
    return agents


def main() -> None:
    total = int(sys.argv[1]) if len(sys.argv) > 1 else 204
    agents = build(total)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(agents, indent=2, ensure_ascii=False))
    print(f"\nwrote {len(agents)} agents to {OUT_PATH}")


if __name__ == "__main__":
    main()
