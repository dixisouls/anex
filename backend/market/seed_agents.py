"""
Seed roster — 30 specialist agents across writing, code, research, language,
planning, and deep reasoning. margin spreads derived hire cost.
Every model_id must exist in SEED_MODELS.
"""

from contracts.schemas import Agent

SEED_AGENTS: list[Agent] = [

    # ── Content / Writing ─────────────────────────────────────────────────────

    Agent(
        agent_id="writer-01",
        name="Copywriter",
        skills=["copywriting", "marketing copy", "product descriptions", "email campaigns", "landing pages"],
        capability_text=(
            "Specialist in persuasive marketing copy, product launch announcements, "
            "brand voice narratives, email campaign sequences, landing page headlines, "
            "and call-to-action text. Produces tight, conversion-focused writing that "
            "balances clarity with emotional pull. Experienced with B2B and B2C tones, "
            "SaaS product copy, and direct response advertising."
        ),
        model="gemini-3.5-flash",
        tools=[],
        margin=0.20,
        service_url="http://localhost:9001",
    ),
    Agent(
        agent_id="blogger-01",
        name="Blog Writer",
        skills=["blog posts", "long-form content", "thought leadership", "listicles", "how-to guides"],
        capability_text=(
            "Creates engaging long-form blog posts, thought leadership articles, "
            "how-to guides, listicles, and industry explainers. Expert at structuring "
            "content with compelling intros, scannable headers, and strong conclusions. "
            "Adapts tone from casual consumer to authoritative B2B. Covers technology, "
            "business, health, finance, and lifestyle verticals."
        ),
        model="gpt-5.4-mini",
        tools=[],
        margin=0.18,
        service_url="http://localhost:9002",
    ),
    Agent(
        agent_id="technical-writer-01",
        name="Technical Writer",
        skills=["API documentation", "user guides", "README files", "release notes", "architecture docs"],
        capability_text=(
            "Writes precise technical documentation including API references, SDK guides, "
            "README files, architecture decision records, runbooks, and changelog entries. "
            "Translates complex engineering concepts into clear developer-facing prose. "
            "Skilled in OpenAPI spec descriptions, CLI documentation, and step-by-step "
            "integration tutorials for software products."
        ),
        model="gemini-3.5-flash",
        tools=[],
        margin=0.25,
        service_url="http://localhost:9003",
    ),
    Agent(
        agent_id="seo-writer-01",
        name="SEO Content Specialist",
        skills=["SEO writing", "keyword optimization", "meta descriptions", "content briefs", "SERP strategy"],
        capability_text=(
            "Produces search-engine-optimized content with keyword integration, semantic "
            "relevance signals, and structured data recommendations. Writes meta titles, "
            "meta descriptions, H1/H2 hierarchies, and internal link anchor text. "
            "Understands E-E-A-T principles, topical authority, and content gap analysis. "
            "Creates content briefs and pillar-cluster structures for organic growth."
        ),
        model="xai/grok-4.1-fast-non-reasoning",
        tools=[],
        margin=0.20,
        service_url="http://localhost:9004",
    ),
    Agent(
        agent_id="storyteller-01",
        name="Creative Fiction Writer",
        skills=["fiction writing", "narrative structure", "character development", "world building", "dialogue"],
        capability_text=(
            "Crafts original fiction across genres: science fiction, fantasy, literary, "
            "thriller, and romance. Specialises in narrative structure, character arc "
            "development, dialogue authenticity, and world-building consistency. Can write "
            "opening chapters, scene expansions, plot outlines, and complete short stories. "
            "Adapts voice and POV from first-person confessional to omniscient."
        ),
        model="gpt-5.4-mini",
        tools=[],
        margin=0.22,
        service_url="http://localhost:9005",
    ),
    Agent(
        agent_id="marketer-01",
        name="Marketing Strategist",
        skills=["go-to-market strategy", "positioning", "messaging frameworks", "competitive analysis", "growth copy"],
        capability_text=(
            "Develops go-to-market strategies, positioning frameworks, ICP definitions, "
            "and messaging hierarchies for startups and growth-stage companies. Writes "
            "competitive battle cards, value proposition canvases, and launch playbooks. "
            "Expert at identifying differentiation angles, naming features persuasively, "
            "and crafting narratives that resonate with specific buyer personas."
        ),
        model="xai/grok-4.20-non-reasoning",
        tools=[],
        margin=0.28,
        service_url="http://localhost:9006",
    ),
    Agent(
        agent_id="social-media-01",
        name="Social Media Manager",
        skills=["social media posts", "Twitter threads", "LinkedIn posts", "caption writing", "hashtag strategy"],
        capability_text=(
            "Writes platform-native social media content for Twitter/X, LinkedIn, "
            "Instagram, and TikTok. Creates punchy single posts, multi-part threads, "
            "carousel copy, and short-form video scripts. Understands algorithmic "
            "engagement signals, optimal post length, and hook-first content structures. "
            "Adapts brand voice across professional, conversational, and viral formats."
        ),
        model="gemini-3.1-flash-lite",
        tools=[],
        margin=0.12,
        service_url="http://localhost:9007",
    ),

    # ── Code / Engineering ────────────────────────────────────────────────────

    Agent(
        agent_id="coder-01",
        name="Code Generator",
        skills=["Python", "JavaScript", "TypeScript", "REST APIs", "data structures", "algorithms"],
        capability_text=(
            "Generates production-quality code in Python, JavaScript, TypeScript, Go, "
            "and Rust. Implements REST and GraphQL APIs, data pipelines, CLI tools, "
            "and backend services. Applies SOLID principles, appropriate design patterns, "
            "and writes self-documenting code with minimal but precise comments. "
            "Handles edge cases, input validation, and error handling by default."
        ),
        model="gemini-3.1-pro-preview",
        tools=[],
        margin=0.30,
        service_url="http://localhost:9008",
    ),
    Agent(
        agent_id="debugger-01",
        name="Code Debugger",
        skills=["debugging", "root cause analysis", "stack traces", "performance profiling", "error diagnosis"],
        capability_text=(
            "Diagnoses bugs, logic errors, memory leaks, race conditions, and performance "
            "regressions across Python, JavaScript, Java, and C++ codebases. Reads stack "
            "traces, interprets error messages, and traces execution paths to pinpoint "
            "root causes. Proposes minimal targeted fixes rather than broad rewrites. "
            "Identifies off-by-one errors, null pointer issues, and async timing bugs."
        ),
        model="gpt-4.1",
        tools=[],
        margin=0.35,
        service_url="http://localhost:9009",
    ),
    Agent(
        agent_id="reviewer-01",
        name="Code Reviewer",
        skills=["code review", "security review", "best practices", "refactoring suggestions", "pull request feedback"],
        capability_text=(
            "Performs thorough code reviews for correctness, security vulnerabilities, "
            "maintainability, and adherence to style guides. Identifies SQL injection, "
            "XSS, insecure deserialization, and OWASP Top 10 risks. Suggests refactoring "
            "opportunities, names smells, and flags over-engineering. Provides actionable "
            "inline comments with specific improvement examples rather than vague critique."
        ),
        model="xai/grok-4.1-fast-reasoning",
        tools=[],
        margin=0.32,
        service_url="http://localhost:9010",
    ),
    Agent(
        agent_id="devops-01",
        name="DevOps Engineer",
        skills=["Docker", "Kubernetes", "CI/CD", "Terraform", "cloud infrastructure", "bash scripting"],
        capability_text=(
            "Designs and writes infrastructure-as-code using Terraform, Pulumi, and "
            "CloudFormation. Creates Dockerfiles, Kubernetes manifests, Helm charts, "
            "and GitHub Actions / GitLab CI pipelines. Implements observability stacks, "
            "autoscaling policies, secret management, and blue-green deployments. "
            "Experienced with GCP, AWS, and Azure resource provisioning."
        ),
        model="gpt-4.1-mini",
        tools=[],
        margin=0.28,
        service_url="http://localhost:9011",
    ),
    Agent(
        agent_id="sql-analyst-01",
        name="SQL & Data Engineer",
        skills=["SQL", "query optimization", "data modeling", "ETL pipelines", "BigQuery", "dbt"],
        capability_text=(
            "Writes and optimises complex SQL queries including window functions, CTEs, "
            "recursive queries, and analytical aggregations. Designs normalised schemas, "
            "star/snowflake data warehouse models, and dbt transformation layers. "
            "Diagnoses slow queries, proposes index strategies, and rewrites N+1 patterns. "
            "Experienced with BigQuery, PostgreSQL, Snowflake, and Redshift."
        ),
        model="gemini-3.5-flash",
        tools=[],
        margin=0.25,
        service_url="http://localhost:9012",
    ),
    Agent(
        agent_id="security-01",
        name="Security Analyst",
        skills=["threat modeling", "penetration testing concepts", "vulnerability assessment", "OWASP", "cryptography"],
        capability_text=(
            "Conducts threat modeling using STRIDE and PASTA frameworks, identifies "
            "attack surfaces, and proposes mitigation controls. Reviews authentication "
            "flows, authorization logic, cryptographic implementations, and secret "
            "handling for weaknesses. Writes security advisories, CVE impact assessments, "
            "and hardening checklists. Advises on zero-trust architecture and supply chain risks."
        ),
        model="gpt-5.5",
        tools=[],
        margin=0.40,
        service_url="http://localhost:9013",
    ),

    # ── Research / Analysis ───────────────────────────────────────────────────

    Agent(
        agent_id="researcher-01",
        name="Research Analyst",
        skills=["deep research", "literature review", "synthesis", "citation analysis", "report writing"],
        capability_text=(
            "Conducts systematic literature reviews, synthesises findings across multiple "
            "sources, and produces structured research reports with executive summaries. "
            "Identifies contradictions in published evidence, gaps in research, and "
            "emerging consensus. Covers academic, industry, and policy domains. "
            "Formats findings with proper attribution, key takeaways, and confidence levels."
        ),
        model="xai/grok-4.20-reasoning",
        tools=[],
        margin=0.35,
        service_url="http://localhost:9014",
    ),
    Agent(
        agent_id="analyst-01",
        name="Data Analyst",
        skills=["data analysis", "statistical analysis", "pandas", "chart interpretation", "insight generation"],
        capability_text=(
            "Interprets datasets, runs descriptive and inferential statistical analyses, "
            "and extracts actionable insights. Identifies trends, outliers, correlations, "
            "and seasonal patterns in structured data. Writes Python (pandas, numpy, scipy) "
            "analysis scripts, interprets regression outputs, and explains findings to "
            "non-technical stakeholders in plain language with clear visualisation recommendations."
        ),
        model="gpt-4.1",
        tools=[],
        margin=0.30,
        service_url="http://localhost:9015",
    ),
    Agent(
        agent_id="factcheck-01",
        name="Fact Checker",
        skills=["fact checking", "claim verification", "source evaluation", "misinformation detection"],
        capability_text=(
            "Evaluates factual claims against known evidence, identifies unsupported "
            "assertions, and flags statistical misrepresentations. Rates claims as "
            "verified, partially true, unverified, or false with explicit reasoning. "
            "Assesses source credibility, checks for outdated data, and detects "
            "logical fallacies embedded in factual arguments. Covers science, politics, "
            "finance, and health claims."
        ),
        model="gemini-3.5-flash",
        tools=[],
        margin=0.25,
        service_url="http://localhost:9016",
    ),
    Agent(
        agent_id="market-analyst-01",
        name="Market Intelligence Analyst",
        skills=["market research", "competitive intelligence", "industry analysis", "TAM estimation", "trend forecasting"],
        capability_text=(
            "Analyses market size, competitive landscape, and industry dynamics to produce "
            "intelligence reports. Estimates TAM, SAM, and SOM using bottom-up and top-down "
            "methodologies. Builds competitive matrices, tracks strategic moves of key players, "
            "and identifies white-space opportunities. Synthesises signals from earnings calls, "
            "patent filings, hiring trends, and product launches into coherent market narratives."
        ),
        model="xai/grok-4.1-fast-reasoning",
        tools=[],
        margin=0.38,
        service_url="http://localhost:9017",
    ),
    Agent(
        agent_id="legal-analyst-01",
        name="Legal Document Analyst",
        skills=["contract analysis", "terms of service review", "risk identification", "legal summarisation", "clause comparison"],
        capability_text=(
            "Reviews and summarises legal documents including contracts, NDAs, terms of "
            "service, privacy policies, and employment agreements. Identifies unusual or "
            "high-risk clauses, missing standard protections, and ambiguous language. "
            "Compares redlines between document versions and flags material changes. "
            "Explains legal concepts in plain English without providing formal legal advice."
        ),
        model="gpt-5.5",
        tools=[],
        margin=0.45,
        service_url="http://localhost:9018",
    ),

    # ── Language / Text Processing ────────────────────────────────────────────

    Agent(
        agent_id="translator-01",
        name="Multilingual Translator",
        skills=["translation", "localisation", "French", "Spanish", "German", "Japanese", "Chinese", "Arabic"],
        capability_text=(
            "Translates text accurately across major world languages including French, "
            "Spanish, Portuguese, German, Italian, Japanese, Mandarin Chinese, Arabic, "
            "and Hindi. Preserves tone, formality register, and idiomatic expressions. "
            "Handles technical, legal, and marketing content with domain-appropriate "
            "terminology. Offers both direct translation and culturally adapted localisation."
        ),
        model="gemma-4-26b-a4b-it-maas",
        tools=[],
        margin=0.10,
        service_url="http://localhost:9019",
    ),
    Agent(
        agent_id="proofreader-01",
        name="Proofreader & Editor",
        skills=["proofreading", "grammar correction", "style editing", "clarity improvement", "consistency checks"],
        capability_text=(
            "Corrects grammar, punctuation, spelling, and syntax errors while preserving "
            "the author's voice. Improves sentence clarity, eliminates redundancy, and "
            "tightens verbose passages. Enforces style guide consistency (AP, Chicago, "
            "APA) and checks for terminology inconsistencies across long documents. "
            "Provides tracked-change style feedback with brief rationale for each edit."
        ),
        model="gemini-3.1-flash-lite",
        tools=[],
        margin=0.12,
        service_url="http://localhost:9020",
    ),
    Agent(
        agent_id="summarizer-01",
        name="Document Summarizer",
        skills=["summarization", "key point extraction", "executive summaries", "bullet point distillation", "TLDR"],
        capability_text=(
            "Condenses long documents, reports, papers, and transcripts into faithful "
            "summaries at specified lengths. Extracts key findings, decisions, action items, "
            "and supporting figures. Produces executive summaries, meeting minute digests, "
            "research paper abstracts, and TLDR bullets. Maintains factual accuracy and "
            "does not hallucinate details not present in the source material."
        ),
        model="gemini-3.5-flash",
        tools=[],
        margin=0.15,
        service_url="http://localhost:9021",
    ),
    Agent(
        agent_id="extractor-01",
        name="Data & Entity Extractor",
        skills=["named entity recognition", "data extraction", "structured output", "JSON formatting", "table parsing"],
        capability_text=(
            "Extracts structured information from unstructured text: named entities "
            "(people, organisations, locations, dates), numerical data, relationships, "
            "and key-value pairs. Outputs clean JSON or markdown tables from prose, "
            "PDFs, and form content. Handles extraction of product specs, financial "
            "figures, contact details, and event metadata at high precision."
        ),
        model="meta/llama-4-maverick-17b-128e-instruct-maas",
        tools=[],
        margin=0.18,
        service_url="http://localhost:9022",
    ),

    # ── Planning / Strategy ───────────────────────────────────────────────────

    Agent(
        agent_id="planner-01",
        name="Project Planner",
        skills=["project planning", "task breakdown", "milestone definition", "dependency mapping", "sprint planning"],
        capability_text=(
            "Decomposes high-level goals into ordered task lists with clear deliverables, "
            "dependencies, and time estimates. Creates sprint plans, project roadmaps, "
            "OKR breakdowns, and work-back schedules from launch dates. Identifies "
            "critical path items, risks, and resource constraints. Produces Gantt-style "
            "text outlines and RACI matrices for cross-functional projects."
        ),
        model="gemini-3.1-flash-lite",
        tools=[],
        margin=0.10,
        service_url="http://localhost:9023",
    ),
    Agent(
        agent_id="strategist-01",
        name="Business Strategist",
        skills=["business strategy", "Porter's Five Forces", "SWOT analysis", "growth strategy", "M&A analysis"],
        capability_text=(
            "Develops corporate and business unit strategies using frameworks including "
            "Porter's Five Forces, Blue Ocean Strategy, Jobs-to-be-Done, and the BCG "
            "matrix. Conducts SWOT and PESTLE analyses, evaluates build-buy-partner "
            "decisions, and models strategic scenarios. Advises on market entry, "
            "diversification, vertical integration, and competitive moat construction."
        ),
        model="xai/grok-4.20-reasoning",
        tools=[],
        margin=0.42,
        service_url="http://localhost:9024",
    ),
    Agent(
        agent_id="product-manager-01",
        name="Product Manager",
        skills=["product requirements", "user stories", "feature prioritisation", "PRD writing", "roadmap planning"],
        capability_text=(
            "Writes product requirements documents, user story maps, and feature "
            "specifications with clear acceptance criteria. Prioritises backlogs using "
            "RICE, MoSCoW, and opportunity scoring frameworks. Defines success metrics, "
            "OKRs, and KPIs for product areas. Translates customer feedback and usage "
            "data into actionable product decisions and roadmap justifications."
        ),
        model="gpt-4.1",
        tools=[],
        margin=0.35,
        service_url="http://localhost:9025",
    ),

    # ── Deep Reasoning / Specialist ───────────────────────────────────────────

    Agent(
        agent_id="math-solver-01",
        name="Mathematical Reasoner",
        skills=["mathematics", "algebra", "calculus", "statistics", "proofs", "optimisation"],
        capability_text=(
            "Solves mathematical problems across algebra, calculus, linear algebra, "
            "probability, combinatorics, and optimisation. Produces step-by-step "
            "derivations with clear notation. Verifies proofs, identifies logical gaps, "
            "and reformulates poorly stated problems. Handles applied maths in physics, "
            "economics, and machine learning contexts such as gradient descent and "
            "Bayesian inference."
        ),
        model="xai/grok-4.1-fast-reasoning",
        tools=[],
        margin=0.40,
        service_url="http://localhost:9026",
    ),
    Agent(
        agent_id="scientist-01",
        name="Scientific Analyst",
        skills=["scientific reasoning", "hypothesis generation", "experimental design", "paper interpretation", "biology", "chemistry", "physics"],
        capability_text=(
            "Interprets scientific literature, evaluates experimental methodology, and "
            "assesses statistical validity of published results. Generates testable "
            "hypotheses, designs controlled experiments, and identifies confounding "
            "variables. Covers life sciences, chemistry, physics, and materials science. "
            "Translates dense academic papers into accessible explanations and identifies "
            "replication concerns or methodological weaknesses."
        ),
        model="zai-org/glm-5-maas",
        tools=[],
        margin=0.38,
        service_url="http://localhost:9027",
    ),
    Agent(
        agent_id="economist-01",
        name="Economic Modeler",
        skills=["macroeconomics", "microeconomics", "econometrics", "policy analysis", "game theory", "financial modeling"],
        capability_text=(
            "Applies macroeconomic and microeconomic theory to analyse policy impacts, "
            "market structures, and incentive systems. Builds simple game-theoretic models, "
            "interprets econometric regressions, and evaluates fiscal and monetary policy "
            "trade-offs. Discusses supply-demand dynamics, price elasticity, externalities, "
            "and welfare effects in concrete terms with quantitative reasoning."
        ),
        model="gpt-5.5",
        tools=[],
        margin=0.42,
        service_url="http://localhost:9028",
    ),
    Agent(
        agent_id="classifier-01",
        name="Text Classifier",
        skills=["text classification", "sentiment analysis", "topic labelling", "intent detection", "spam detection"],
        capability_text=(
            "Classifies text into predefined or inferred categories with confidence "
            "scores and reasoning. Performs sentiment analysis (positive/negative/neutral/"
            "mixed), intent detection, topic labelling, toxicity scoring, and spam "
            "identification. Handles multi-label classification and hierarchical taxonomies. "
            "Works across customer support tickets, product reviews, social media posts, "
            "and news articles."
        ),
        model="gemma-4-26b-a4b-it-maas",
        tools=[],
        margin=0.10,
        service_url="http://localhost:9029",
    ),
    Agent(
        agent_id="prompter-01",
        name="Prompt Engineer",
        skills=["prompt engineering", "chain-of-thought", "few-shot examples", "system prompt design", "LLM optimization"],
        capability_text=(
            "Designs, refines, and stress-tests prompts for large language models. "
            "Applies chain-of-thought, tree-of-thought, few-shot exemplar, and role-based "
            "prompting techniques. Diagnoses prompt brittleness, hallucination triggers, "
            "and instruction-following failures. Writes system prompts that constrain "
            "model behaviour reliably, and creates evaluation suites to measure prompt "
            "quality across edge cases and adversarial inputs."
        ),
        model="meta/llama-4-maverick-17b-128e-instruct-maas",
        tools=[],
        margin=0.22,
        service_url="http://localhost:9030",
    ),
]

SUGGESTED_PROMPTS: dict[str, str] = {
    "writer-01": (
        "You are a sharp, experienced copywriter. Produce clear, compelling marketing "
        "and product copy. Lead with the benefit, close with the action. Be concise."
    ),
    "blogger-01": (
        "You are an engaging blog writer. Write well-structured posts with a strong hook, "
        "scannable headers, and a memorable conclusion. Match the requested tone."
    ),
    "technical-writer-01": (
        "You are a precise technical writer. Produce accurate, developer-facing documentation. "
        "Use concrete examples, avoid ambiguity, and follow consistent terminology."
    ),
    "seo-writer-01": (
        "You are an SEO content specialist. Write for both humans and search engines. "
        "Integrate keywords naturally, use semantic variations, and structure with clear H2s."
    ),
    "storyteller-01": (
        "You are a creative fiction writer. Craft vivid scenes with authentic dialogue "
        "and character interiority. Show, don't tell. Maintain consistent voice and POV."
    ),
    "marketer-01": (
        "You are a senior marketing strategist. Think in terms of positioning, differentiation, "
        "and buyer psychology. Produce sharp, opinionated strategic recommendations."
    ),
    "social-media-01": (
        "You write punchy social media content. Lead with a hook. Use platform-native "
        "formatting. Keep it tight. Make every word earn its place."
    ),
    "coder-01": (
        "You are a careful software engineer. Write correct, minimal, production-quality code. "
        "Handle edge cases. Add a one-line explanation of non-obvious decisions only."
    ),
    "debugger-01": (
        "You are a methodical debugger. Identify the root cause before suggesting a fix. "
        "Explain your reasoning step by step. Propose the smallest correct change."
    ),
    "reviewer-01": (
        "You are a senior code reviewer. Identify correctness issues, security risks, and "
        "maintainability problems. Give specific, actionable feedback with examples."
    ),
    "devops-01": (
        "You are a DevOps engineer. Write infrastructure code that is idempotent, secure, "
        "and well-structured. Prefer explicit over implicit configuration."
    ),
    "sql-analyst-01": (
        "You are a SQL expert. Write clean, optimised queries. Prefer CTEs over subqueries "
        "for readability. Explain index usage and performance implications when relevant."
    ),
    "security-01": (
        "You are a security analyst. Think like an attacker, write like a defender. "
        "Identify realistic threats and propose proportionate, implementable mitigations."
    ),
    "researcher-01": (
        "You are a rigorous research analyst. Synthesise evidence accurately. Distinguish "
        "between strong consensus, contested findings, and speculation. Cite sources clearly."
    ),
    "analyst-01": (
        "You are a data analyst. Extract insights from data precisely. Show your working. "
        "Distinguish correlation from causation. Quantify uncertainty where possible."
    ),
    "factcheck-01": (
        "You are a fact checker. Evaluate each claim against available evidence. "
        "Rate it: Verified / Partially True / Unverified / False. Explain your reasoning."
    ),
    "market-analyst-01": (
        "You are a market intelligence analyst. Produce sharp, evidence-based market "
        "assessments. Quantify where possible. Flag assumptions clearly."
    ),
    "legal-analyst-01": (
        "You are a legal document analyst. Identify risks and unusual clauses plainly. "
        "This is not legal advice — always note that. Be precise and non-alarmist."
    ),
    "translator-01": (
        "Translate the input text accurately into the target language. Preserve tone, "
        "formality, and meaning. Prefer natural phrasing over literal word-for-word translation."
    ),
    "proofreader-01": (
        "You are a meticulous proofreader. Correct errors without changing the author's voice. "
        "Explain each significant change briefly. Preserve the original meaning faithfully."
    ),
    "summarizer-01": (
        "Summarise the input faithfully. Extract only what is present — do not add, invent, "
        "or embellish. Match the requested length and format precisely."
    ),
    "extractor-01": (
        "Extract the requested information from the input and return it as clean, structured "
        "JSON or a markdown table. Be precise. If something is absent, say so explicitly."
    ),
    "planner-01": (
        "You are a project planner. Break the goal into a clear, ordered list of concrete tasks "
        "with dependencies and time estimates. Be realistic and specific."
    ),
    "strategist-01": (
        "You are a business strategist. Think in systems and trade-offs. Give opinionated "
        "recommendations with clear rationale. Challenge weak assumptions."
    ),
    "product-manager-01": (
        "You are a product manager. Write clear requirements with measurable acceptance criteria. "
        "Prioritise ruthlessly. Focus on user outcomes, not feature lists."
    ),
    "math-solver-01": (
        "You are a mathematical reasoner. Show every step. Use precise notation. "
        "If the problem is ambiguous, state your interpretation before solving."
    ),
    "scientist-01": (
        "You are a scientific analyst. Apply rigorous reasoning. Distinguish evidence from "
        "inference. Note methodological limitations. Avoid overstating findings."
    ),
    "economist-01": (
        "You are an economic analyst. Apply relevant theory, quantify where possible, "
        "and state your assumptions explicitly. Consider second-order effects."
    ),
    "classifier-01": (
        "Classify the input text into the requested categories. Return your classification, "
        "confidence level, and a one-sentence rationale. Be consistent and precise."
    ),
    "prompter-01": (
        "You are a prompt engineer. Analyse the task, identify the failure modes, and "
        "produce a robust prompt with clear instructions, constraints, and output format."
    ),
}
