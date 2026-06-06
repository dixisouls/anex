"""
Seed roster. margin spreads derived hire cost; model must exist in SEED_MODELS.
"""

from contracts.schemas import Agent

SEED_AGENTS: list[Agent] = [
    Agent(
        agent_id="writer-01",
        name="Copywriter",
        skills=["writing", "summarization"],
        capability_text="Writes and summarizes marketing and technical copy, blog posts, and product announcements",
        model="gemini-3.5-flash",
        tools=[],
        margin=0.20,
        service_url="http://localhost:9001",
    ),
    Agent(
        agent_id="coder-01",
        name="Code Generator",
        skills=["coding", "debugging"],
        capability_text="Generates and debugs code snippets and small programs in Python and JavaScript",
        model="gemini-3.1-pro-preview",
        tools=[],
        margin=0.30,
        service_url="http://localhost:9002",
    ),
    Agent(
        agent_id="summarizer-01",
        name="Data Summarizer",
        skills=["summarization", "analysis"],
        capability_text="Summarizes long documents and extracts key points and figures from data",
        model="gemini-3.5-flash",
        tools=[],
        margin=0.15,
        service_url="http://localhost:9003",
    ),
    Agent(
        agent_id="factcheck-01",
        name="Fact Checker",
        skills=["research", "verification"],
        capability_text="Checks claims for factual accuracy and flags unsupported or incorrect statements",
        model="gemini-3.5-flash",
        tools=[],
        margin=0.25,
        service_url="http://localhost:9004",
    ),
    Agent(
        agent_id="translator-01",
        name="Translator",
        skills=["translation"],
        capability_text="Translates text",
        model="gemma-4-26b-a4b-it-maas",
        tools=[],
        margin=0.10,
        service_url="http://localhost:9005",
    ),
    Agent(
        agent_id="planner-01",
        name="Planner",
        skills=["planning"],
        capability_text="Makes plans",
        model="gemini-3.1-flash-lite",
        tools=[],
        margin=0.10,
        service_url="http://localhost:9006",
    ),
]

SUGGESTED_PROMPTS: dict[str, str] = {
    "writer-01": "You are a sharp copywriter. Write clear, compelling marketing and technical copy. Keep it tight.",
    "coder-01": "You are a careful software engineer. Produce correct, minimal code with a one line explanation.",
    "summarizer-01": "You summarize documents into the key points and figures. Be faithful and concise.",
    "factcheck-01": "You verify claims. State whether each claim is supported, and flag anything unsupported.",
    "translator-01": "Translate the input.",
    "planner-01": "Make a plan.",
}
