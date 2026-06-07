"""Single entry point mapping model id + provider to a chat client.

Returns {"output": str, "usage": {"input_tokens": int, "output_tokens": int},
         "model": str, "provider": str} so Weave traces token counts.

provider values:
  "gcp"           -- native Gemini via google.genai (Vertex AI)
  "vertex_openai" -- third-party models on Vertex AI OpenAI-compat endpoint
                     (LLaMA 4, Grok, GLM 5); LLaMA uses us-east5, rest global
  "openai"        -- standard OpenAI chat.completions (gpt-*)
"""

import weave

from backend.infra.weave_init import init_weave

init_weave()

_VERTEX_LLAMA_BASE = "https://us-east5-aiplatform.googleapis.com"
_VERTEX_GLOBAL_BASE = "https://aiplatform.googleapis.com"


@weave.op
def generate(model: str, provider: str, prompt: str, system: str | None = None) -> dict:
    if provider == "openai":
        return _openai_generate(model, prompt, system)
    if provider == "vertex_openai":
        return _vertex_openai_generate(model, prompt, system)
    return _gcp_gemini_generate(model, prompt, system)


def _gcp_gemini_generate(model: str, prompt: str, system: str | None) -> dict:
    from google import genai

    from backend.config import GCP_LOCATION, GCP_PROJECT

    client = genai.Client(vertexai=True, project=GCP_PROJECT, location=GCP_LOCATION)
    contents = f"{system}\n\n{prompt}" if system else prompt
    resp = client.models.generate_content(model=model, contents=contents)
    usage = {}
    if hasattr(resp, "usage_metadata") and resp.usage_metadata is not None:
        usage = {
            "input_tokens": getattr(resp.usage_metadata, "prompt_token_count", 0),
            "output_tokens": getattr(resp.usage_metadata, "candidates_token_count", 0),
        }
    return {"output": resp.text, "usage": usage, "model": model, "provider": "gcp"}


def _vertex_openai_generate(model: str, prompt: str, system: str | None) -> dict:
    import subprocess

    from openai import OpenAI

    from backend.config import GCP_LOCATION, GCP_PROJECT

    token = subprocess.check_output(["gcloud", "auth", "print-access-token"]).decode().strip()
    if model.startswith("meta/"):
        base_url = f"{_VERTEX_LLAMA_BASE}/v1/projects/{GCP_PROJECT}/locations/us-east5/endpoints/openapi"
    else:
        base_url = f"{_VERTEX_GLOBAL_BASE}/v1/projects/{GCP_PROJECT}/locations/{GCP_LOCATION}/endpoints/openapi"

    client = OpenAI(base_url=base_url, api_key=token)
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    resp = client.chat.completions.create(model=model, messages=messages)
    choice = resp.choices[0].message
    output = choice.content or getattr(choice, "reasoning_content", None) or ""
    usage = {}
    if resp.usage:
        usage = {
            "input_tokens": resp.usage.prompt_tokens,
            "output_tokens": resp.usage.completion_tokens,
        }
    return {"output": output, "usage": usage, "model": model, "provider": "vertex_openai"}


def _openai_generate(model: str, prompt: str, system: str | None) -> dict:
    import os

    from openai import OpenAI

    from backend.config import OPENAI_API_KEY

    client = OpenAI(api_key=OPENAI_API_KEY or os.getenv("OPENAI_API_KEY"))
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    resp = client.chat.completions.create(model=model, messages=messages)
    choice = resp.choices[0].message
    output = choice.content or getattr(choice, "reasoning_content", None) or ""
    usage = {}
    if resp.usage:
        usage = {
            "input_tokens": resp.usage.prompt_tokens,
            "output_tokens": resp.usage.completion_tokens,
        }
    return {"output": output, "usage": usage, "model": model, "provider": "openai"}
