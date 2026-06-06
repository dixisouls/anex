"""
Seed roster.

Six distinct specialists so the market has variety to select from. Two are
deliberately weak (a lite model and a vague capability_text) so the demo shows
an agent getting starved. Starting reputation is equal at 0.5 so divergence is
earned, not seeded. Prices are spread so the rank step has something to trade
off. service_url points at the localhost port each agent will run on in dev
(Track A), and gets repointed to a Cloud Run URL at the cloud cutover.

Only the Agent fields are written to Redis here. The system prompt that defines
each agent's behavior belongs to the agent service (Track A), so SUGGESTED_PROMPTS
below is a handoff aid for Track A, not something this module stores.

The model strings are tier labels the agent service maps to real Vertex model
ids. Track A confirms the exact ids. The upgrade module (B5) swaps an agent up
this ladder: flash-lite -> flash -> pro.
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
        price=5.0,
        service_url="http://localhost:9001",
    ),
    Agent(
        agent_id="coder-01",
        name="Code Generator",
        skills=["coding", "debugging"],
        capability_text="Generates and debugs code snippets and small programs in Python and JavaScript",
        model="gemini-3.1-pro-preview",
        tools=[],
        price=8.0,
        service_url="http://localhost:9002",
    ),
    Agent(
        agent_id="summarizer-01",
        name="Data Summarizer",
        skills=["summarization", "analysis"],
        capability_text="Summarizes long documents and extracts key points and figures from data",
        model="gemini-3.5-flash",
        tools=[],
        price=4.0,
        service_url="http://localhost:9003",
    ),
    Agent(
        agent_id="factcheck-01",
        name="Fact Checker",
        skills=["research", "verification"],
        capability_text="Checks claims for factual accuracy and flags unsupported or incorrect statements",
        model="gemini-3.5-flash",
        tools=[],
        price=6.0,
        service_url="http://localhost:9004",
    ),
    # Deliberately weak: vague capability, cheap lite model. Should match poorly
    # and lose hires as the market diverges.
    Agent(
        agent_id="translator-01",
        name="Translator",
        skills=["translation"],
        capability_text="Translates text",
        model="gemma-4-26b-a4b-it",
        tools=[],
        price=3.0,
        service_url="http://localhost:9005",
    ),
    # Deliberately weak: vague capability, cheap lite model.
    Agent(
        agent_id="planner-01",
        name="Planner",
        skills=["planning"],
        capability_text="Makes plans",
        model="gemini-3.1-flash-lite-preview",
        tools=[],
        price=3.0,
        service_url="http://localhost:9006",
    ),
]

# Handoff to Track A. Not written to Redis by the seeder.
SUGGESTED_PROMPTS: dict[str, str] = {
    "writer-01": "You are a sharp copywriter. Write clear, compelling marketing and technical copy. Keep it tight.",
    "coder-01": "You are a careful software engineer. Produce correct, minimal code with a one line explanation.",
    "summarizer-01": "You summarize documents into the key points and figures. Be faithful and concise.",
    "factcheck-01": "You verify claims. State whether each claim is supported, and flag anything unsupported.",
    "translator-01": "Translate the input.",
    "planner-01": "Make a plan.",
}