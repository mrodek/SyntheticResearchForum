"""Integration test — Lobster step scripts end-to-end.

Skipped unless SRF_LLM_PROVIDER is configured (live env required).
"""

from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("SRF_LLM_PROVIDER"),
    reason="Set SRF_LLM_PROVIDER (and related vars) to run Lobster step integration tests",
)


def test_lobster_steps_placeholder() -> None:
    """Placeholder — full end-to-end step chaining tested in Epic 5."""
    pass
