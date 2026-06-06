"""Model stocks listed on the exchange at IPO."""

SEED_MODELS: list[dict] = [
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
        "model_id": "gemma-4-26b-a4b-it",
        "name": "Gemma 4 26B",
        "provider": "gcp",
        "tier": "lite",
    },
    {
        "model_id": "gpt-4.1-mini",
        "name": "GPT-4.1 Mini",
        "provider": "openai",
        "tier": "flash",
    },
    {
        "model_id": "gpt-4.1",
        "name": "GPT-4.1",
        "provider": "openai",
        "tier": "pro",
    },
]
