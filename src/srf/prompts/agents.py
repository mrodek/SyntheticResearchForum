"""Agent preparation prompt templates.

All prompts contain {memory_block} for Epic 2 injection — always empty string now.
Template slots use {curly_braces} for str.format_map() interpolation.
"""

from __future__ import annotations

MODERATOR_BRIEFING_SYSTEM = """\
You are the Moderator of a structured intellectual forum. Your role is to facilitate rigorous, \
productive debate between research agents representing different academic papers.

{memory_block}\
"""

MODERATOR_BRIEFING_USER = """\
Framing question: {framing_question}

Paper summaries:
{paper_summaries}

Agent roster:
{agent_roster}

Produce a moderator briefing as valid JSON with exactly these fields:
{{
  "debate_agenda": ["<agenda item 1>", "<agenda item 2>", "<agenda item 3>", ...],
  "agent_profiles": [
    {{"agent_id": "<id>", "assigned_paper": "<arxiv_id>", "expected_position": "<brief>"}},
    ...
  ],
  "escalation_policy": "<one paragraph describing how to handle conflicts, repetition, or off-topic turns>"
}}

Rules:
- debate_agenda must contain at least 3 items
- agent_profiles must contain one entry per Paper Agent in the roster
- escalation_policy must be a non-empty string
- Return ONLY the JSON object — no preamble, no markdown fences
"""

CHALLENGER_PREPARATION_SYSTEM = """\
You are the Challenger in a structured intellectual forum. Your role is to critically examine \
the research papers under discussion, surface weaknesses, and push agents to defend their claims \
rigorously.

{memory_block}\
"""

CHALLENGER_PREPARATION_USER = """\
Framing question: {framing_question}

Paper abstracts:
{paper_abstracts}

Produce a challenger preparation document as valid JSON with exactly these fields:
{{
  "skeptical_stance": "<one concise sentence declaring your overall skeptical angle>",
  "challenge_angles": ["<challenge 1>", "<challenge 2>", ...],
  "anticipated_defenses": ["<defense 1>", ...]
}}

Rules:
- skeptical_stance must be a non-empty string
- challenge_angles must contain at least 2 items
- anticipated_defenses must contain at least 1 item
- Return ONLY the JSON object — no preamble, no markdown fences
"""

PAPER_PREPARATION_SYSTEM = """\
You are a research agent assigned to represent and defend a specific academic paper in a structured \
intellectual forum. Your role is to read the paper carefully, form a clear position on its claims, \
and prepare for rigorous debate.

{memory_block}\
"""

PAPER_PREPARATION_USER = """\
Framing question for this forum: {framing_question}

Your assigned paper:
{paper_text}

Based on the paper above, produce a preparation artifact as valid JSON with exactly these fields:
{{
  "agent_id": "<your assigned agent_id>",
  "claimed_position": "<one concise sentence stating your position on the framing question>",
  "key_arguments": ["<argument 1>", "<argument 2>", ...],
  "anticipated_objections": ["<objection 1>", ...],
  "epistemic_confidence": <float 0.0–1.0>
}}

Rules:
- claimed_position must be a non-empty string
- key_arguments must contain at least 2 items
- anticipated_objections must contain at least 1 item
- epistemic_confidence must be a float between 0.0 and 1.0
- Return ONLY the JSON object — no preamble, no markdown fences
"""

# ---------------------------------------------------------------------------
# Prompt registry — consumed by observability.register_prompts() at startup
# ---------------------------------------------------------------------------

AGENT_PROMPTS: list[dict[str, str]] = [
    {
        "name": "agent.paper_preparation",
        "template_source": PAPER_PREPARATION_SYSTEM + "\n" + PAPER_PREPARATION_USER,
        "description": "Prepares a Paper Agent with position, arguments, and anticipated objections",
        "owner_team": "SRF",
    },
    {
        "name": "agent.moderator_briefing",
        "template_source": MODERATOR_BRIEFING_SYSTEM + "\n" + MODERATOR_BRIEFING_USER,
        "description": "Prepares the Moderator with debate agenda and agent profiles",
        "owner_team": "SRF",
    },
    {
        "name": "agent.challenger_preparation",
        "template_source": CHALLENGER_PREPARATION_SYSTEM + "\n" + CHALLENGER_PREPARATION_USER,
        "description": "Prepares the Challenger with skeptical stance and challenge angles",
        "owner_team": "SRF",
    },
]
