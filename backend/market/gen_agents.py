"""Generate capability definitions for the tiered agent roster.

One-time dev tool. Output is committed to data/capabilities.json and expanded
into tiered agents at seed time via backend.market.capabilities.

    python -m backend.market.gen_agents [capability_count]

For each of six domains the model invents distinct capability families
(name, skills, capability_text, tier coverage). The script assigns tier_models
and margins, then writes capabilities.json (not flat agents).
"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

from backend.config import GCP_CHAT_MODEL
from backend.infra.model_router import generate
from backend.market.capabilities import DEFAULT_TIER_MODELS

DATA_DIR = Path(__file__).resolve().parent / "data"
OUT_PATH = DATA_DIR / "capabilities.json"

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

_FAST_SLUGS = {"language", "content"}


def _prompt(domain: str, n: int) -> str:
    return (
        f"Invent {n} DISTINCT specialist AI capability families for an agent "
        f"marketplace, all within the domain of {domain}.\n"
        "Each capability must be a narrow, unique specialization.\n"
        "Reply ONLY with a JSON list. Each element must be an object:\n"
        '{"capability_id": "<kebab-case slug>", '
        '"name": "<2-4 word role title>", '
        '"skills": ["<5 short skill tags>"], '
        '"capability_text": "<3-4 sentences>", '
        '"tiers": ["pro","flash","lite"] or ["flash","lite"] or ["flash"]}'
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
        cap_id = str(it.get("capability_id", "")).strip()
        name = str(it.get("name", "")).strip()
        cap = str(it.get("capability_text", "")).strip()
        skills = it.get("skills") or []
        skills = [str(s).strip() for s in skills if str(s).strip()][:6]
        tiers = it.get("tiers") or ["pro", "flash", "lite"]
        tiers = [str(t).strip() for t in tiers if str(t).strip() in {"pro", "flash", "lite"}]
        if not cap_id or not name or not cap or not skills or not tiers:
            continue
        if cap_id in seen:
            continue
        seen.add(cap_id)
        out.append(
            {
                "capability_id": cap_id,
                "name": name,
                "skills": skills,
                "capability_text": cap,
                "tiers": tiers,
            }
        )
    return out


def _template_capabilities(slug: str, count: int, start: int) -> list[dict]:
    rng = random.Random(f"tmpl:{slug}")
    pool = {
        "content": ["copywriting", "editing", "SEO", "brand voice", "scripts"],
        "engineering": ["python", "APIs", "testing", "CI/CD", "databases"],
        "research": ["synthesis", "analysis", "sourcing", "reporting", "forecasting"],
        "language": ["translation", "proofreading", "summarization", "tone", "grammar"],
        "strategy": ["roadmaps", "positioning", "pricing", "GTM", "operations"],
        "reasoning": ["math", "logic", "statistics", "classification", "optimization"],
    }[slug]
    out: list[dict] = []
    for k in range(count):
        skills = rng.sample(pool, k=min(5, len(pool)))
        focus = skills[0]
        tiers = ["flash", "lite"] if slug in _FAST_SLUGS else ["pro", "flash", "lite"]
        out.append(
            {
                "capability_id": f"{slug}-specialist-{start + k}",
                "name": f"{slug.capitalize()} Specialist {start + k}",
                "skills": skills,
                "capability_text": (
                    f"Specialist capability focused on {focus} within {slug}. "
                    f"Handles {', '.join(skills)} with precision."
                ),
                "tiers": tiers,
            }
        )
    return out


def _generate_domain(slug: str, domain: str, n: int) -> list[dict]:
    try:
        raw = generate(GCP_CHAT_MODEL, "gcp", _prompt(domain, n))["output"]
        items = _clean(_extract_json_list(raw))
        print(f"  {slug}: LLM returned {len(items)} valid capabilities")
    except Exception as exc:  # noqa: BLE001
        items = []
        print(f"  {slug}: LLM failed ({exc!r}); using templates")
    if len(items) < n:
        items += _template_capabilities(slug, n - len(items), start=len(items) + 1)
    return items[:n]


def build(total_capabilities: int) -> list[dict]:
    per = max(1, total_capabilities // len(DOMAINS))
    capabilities: list[dict] = []
    for slug, domain in DOMAINS.items():
        print(f"generating {per} {slug} capabilities...")
        for j, spec in enumerate(_generate_domain(slug, domain, per), start=1):
            tiers = spec["tiers"]
            tier_models = {t: DEFAULT_TIER_MODELS[t] for t in tiers}
            capabilities.append(
                {
                    "capability_id": spec["capability_id"],
                    "name": spec["name"],
                    "skills": spec["skills"],
                    "capability_text": spec["capability_text"],
                    "margin": round(random.Random(f"{slug}-{j}").uniform(0.10, 0.35), 2),
                    "tiers": tiers,
                    "tier_models": tier_models,
                    "suggested_prompt": None,
                }
            )
    return capabilities


def main() -> None:
    total = int(sys.argv[1]) if len(sys.argv) > 1 else 40
    capabilities = build(total)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(capabilities, indent=2, ensure_ascii=False))
    agent_count = sum(len(c["tiers"]) for c in capabilities)
    print(f"\nwrote {len(capabilities)} capabilities ({agent_count} tiered agents) to {OUT_PATH}")


if __name__ == "__main__":
    main()
