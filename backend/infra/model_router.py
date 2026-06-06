"""Single entry point mapping model id + provider to a chat client."""

import weave

from backend.infra.weave_init import init_weave

init_weave()


@weave.op
def generate(model: str, provider: str, prompt: str, system: str | None = None) -> str:
    if provider == "openai":
        return _openai_generate(model, prompt, system)
    return _gcp_generate(model, prompt, system)


def _gcp_generate(model: str, prompt: str, system: str | None) -> str:
    from google import genai

    from backend.config import GCP_LOCATION, GCP_PROJECT

    client = genai.Client(vertexai=True, project=GCP_PROJECT, location=GCP_LOCATION)
    contents = f"{system}\n\n{prompt}" if system else prompt
    return client.models.generate_content(model=model, contents=contents).text


def _openai_generate(model: str, prompt: str, system: str | None) -> str:
    from openai import OpenAI

    oai = OpenAI()
    inp = f"{system}\n\n{prompt}" if system else prompt
    return oai.responses.create(model=model, input=inp).output_text
