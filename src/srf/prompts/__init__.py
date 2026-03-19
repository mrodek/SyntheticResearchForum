"""SRF prompt registry — all prompt templates defined as Python constants.

Prompts are registered at startup via observability.register_prompts().
Every prompt change requires a PR; the CI dry-run blocks unregistered changes.
"""

from srf.prompts.agents import AGENT_PROMPTS
from srf.prompts.newsletter import NEWSLETTER_PROMPTS

ALL_PROMPTS: list[dict[str, str]] = [
    *NEWSLETTER_PROMPTS,
    *AGENT_PROMPTS,
]
