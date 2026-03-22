"""Newsletter prompt templates — clustering and framing question.

Both prompts are defined as Python constants and registered at startup.
Template slots use {curly_braces} for string.format() interpolation.
"""

from __future__ import annotations

CLUSTERING_PROMPT = """\
You are an expert research analyst. Your task is to map a set of research papers to \
thematic tension axes identified by a newsletter editor.

The user message will provide:
- Tension axes: {tension_axes}
- Paper summaries: {paper_summaries}

For each tension axis, identify which papers (by title) most directly address that tension. \
A paper may appear under multiple axes if it genuinely speaks to more than one.

Return ONLY valid JSON with this exact structure:
{
  "axis name": ["Paper Title One", "Paper Title Two"],
  ...
}

Include only axes that have at least one matching paper. \
Use the exact paper titles as provided. Do not add explanations outside the JSON."""

FRAMING_QUESTION_PROMPT = """\
You are a research forum moderator composing a focused debate question. \
Given a set of papers grouped around a shared thematic tension, write a single \
precise framing question that:

1. Captures the core intellectual disagreement the papers represent
2. Is specific enough to guide a structured debate
3. Is open-ended enough that reasonable experts could take opposing positions

Return ONLY the framing question as a plain string — no preamble, no quotation marks, \
no explanation.

Tension axes:
{tension_axes}

Papers:
{paper_titles}"""

# ---------------------------------------------------------------------------
# Prompt registry — consumed by observability.register_prompts() at startup
# and by scripts/validate_prompts.py in CI.
# ---------------------------------------------------------------------------

NEWSLETTER_PROMPTS: list[dict[str, str]] = [
    {
        "name": "newsletter.paper_clustering",
        "template_source": CLUSTERING_PROMPT,
        "description": "Maps Primary Signal papers to Pattern Watch tension axes via structured LLM call",
        "owner_team": "SRF",
    },
    {
        "name": "newsletter.framing_question",
        "template_source": FRAMING_QUESTION_PROMPT,
        "description": "Composes a focused debate framing question from a paper cluster",
        "owner_team": "SRF",
    },
]
