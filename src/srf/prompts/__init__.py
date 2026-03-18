"""SRF prompt registry — all prompt templates defined as Python constants.

Prompts are registered at startup via observability.register_prompts().
Every prompt change requires a PR; the CI dry-run blocks unregistered changes.
"""
