"""Model stocks listed on the exchange at IPO.

Tiers drive AMM IPO price (config.TIER_IPO_PRICE):
  pro=50  flash=20  lite=8

provider must match model_router dispatch:
  "gcp"           -> google.genai (Gemini)
  "vertex_openai" -> Vertex AI OpenAI-compat endpoint (LLaMA, Grok, GLM)
  "openai"        -> standard OpenAI chat.completions (gpt-*)
"""

SEED_MODELS: list[dict] = [
    # ── GCP Gemini ────────────────────────────────────────────────────────────
    {
        "model_id": "gemini-3.1-pro-preview",
        "name": "Gemini 3.1 Pro",
        "provider": "gcp",
        "tier": "pro",
    },
    {
        "model_id": "gemini-3.5-flash",
        "name": "Gemini 3.5 Flash",
        "provider": "gcp",
        "tier": "flash",
    },
    {
        "model_id": "gemini-3.1-flash-lite",
        "name": "Gemini Flash Lite",
        "provider": "gcp",
        "tier": "lite",
    },
    {
        "model_id": "gemma-4-26b-a4b-it-maas",
        "name": "Gemma 4 26B",
        "provider": "gcp",
        "tier": "lite",
    },
    # ── Vertex AI third-party (OpenAI-compat endpoint) ────────────────────────
    {
        "model_id": "meta/llama-4-maverick-17b-128e-instruct-maas",
        "name": "LLaMA 4 Maverick",
        "provider": "vertex_openai",
        "tier": "flash",
    },
    {
        "model_id": "xai/grok-4.1-fast-non-reasoning",
        "name": "Grok 4.1 Fast",
        "provider": "vertex_openai",
        "tier": "flash",
    },
    {
        "model_id": "xai/grok-4.20-non-reasoning",
        "name": "Grok 4.20",
        "provider": "vertex_openai",
        "tier": "flash",
    },
    {
        "model_id": "xai/grok-4.1-fast-reasoning",
        "name": "Grok 4.1 Fast Reasoning",
        "provider": "vertex_openai",
        "tier": "pro",
    },
    {
        "model_id": "xai/grok-4.20-reasoning",
        "name": "Grok 4.20 Reasoning",
        "provider": "vertex_openai",
        "tier": "pro",
    },
    {
        "model_id": "zai-org/glm-5-maas",
        "name": "GLM 5",
        "provider": "vertex_openai",
        "tier": "pro",
    },
    # ── OpenAI ────────────────────────────────────────────────────────────────
    {
        "model_id": "gpt-5.5",
        "name": "GPT-5.5",
        "provider": "openai",
        "tier": "pro",
    },
    {
        "model_id": "gpt-5.4-mini",
        "name": "GPT-5.4 Mini",
        "provider": "openai",
        "tier": "flash",
    },
    {
        "model_id": "gpt-4.1",
        "name": "GPT-4.1",
        "provider": "openai",
        "tier": "pro",
    },
    {
        "model_id": "gpt-4.1-mini",
        "name": "GPT-4.1 Mini",
        "provider": "openai",
        "tier": "flash",
    },
]
