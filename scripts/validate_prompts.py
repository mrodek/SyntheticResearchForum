"""CI validation — assert no unregistered prompt template changes in this branch.

Usage:
    python scripts/validate_prompts.py

Exit codes:
    0 — all prompts in sync (or PromptLedger not configured — skip)
    1 — one or more prompts have unregistered changes
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import sys
from typing import Any

import httpx

# ---------------------------------------------------------------------------
# Prompt registry
# ---------------------------------------------------------------------------
# Import all SRF prompt templates here. As new prompts are added in
# src/srf/prompts/, add them to PROMPTS below.

PROMPTS: list[dict[str, str]] = []
# Example entry format:
# {
#     "name": "srf.agent.discussion",
#     "template_source": DISCUSSION_PROMPT,
#     "description": "Agent discussion turn prompt",
#     "owner_team": "SRF",
# }


# ---------------------------------------------------------------------------
# Public helpers (also used by unit tests)
# ---------------------------------------------------------------------------

def checksum(template: str) -> str:
    """Return the SHA-256 hex digest of the template source string."""
    return hashlib.sha256(template.encode()).hexdigest()


def skip_message() -> str:
    """Return the skip message when PromptLedger is not configured."""
    return "SKIP: PromptLedger not configured — prompt validation skipped."


# ---------------------------------------------------------------------------
# Core validation logic
# ---------------------------------------------------------------------------

async def run_validation() -> int:
    """Run the dry-run prompt registration check. Returns 0 (OK) or 1 (drift)."""
    url = os.environ.get("PROMPTLEDGER_API_URL")
    key = os.environ.get("PROMPTLEDGER_API_KEY")

    if not url or not key:
        print(skip_message())
        return 0

    payload: list[dict[str, Any]] = [
        {
            "name": p["name"],
            "template_source": p["template_source"],
            "template_hash": checksum(p["template_source"]),
            "description": p.get("description", ""),
            "owner_team": p.get("owner_team", "SRF"),
        }
        for p in PROMPTS
    ]

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{url}/v1/prompts/register-code",
            headers={"X-API-Key": key},
            json={"prompts": payload, "dry_run": True},
            timeout=30.0,
        )
        response.raise_for_status()

    data = response.json()
    changed = [d for d in data.get("details", []) if d.get("action") != "unchanged"]

    if changed:
        print("ERROR: The following prompts have unregistered template changes:")
        for item in changed:
            print(f"  {item['name']}: {item['action']}")
        print()
        print("Register the updated prompts before merging to main.")
        return 1

    unchanged_count = data.get("unchanged", len(payload))
    print(f"OK: all {unchanged_count} prompt(s) are in sync with PromptLedger.")
    return 0


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    exit_code = asyncio.run(run_validation())
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
