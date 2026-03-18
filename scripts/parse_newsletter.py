"""CLI entrypoint — parse newsletter → cluster → generate → persist candidate configs.

Usage:
    python scripts/parse_newsletter.py --file newsletter.md [--dry-run]

Exit codes:
    0 — success (or dry-run with printed output)
    1 — error (file not found, parse error, clustering error, etc.)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

from srf.newsletter.clustering import cluster_papers
from srf.newsletter.config_generator import generate_candidate_config
from srf.newsletter.parser import parse_newsletter
from srf.newsletter.persistence import save_candidate_configs


# ---------------------------------------------------------------------------
# Core pipeline (importable for unit tests)
# ---------------------------------------------------------------------------


async def run_pipeline(
    *,
    newsletter_path: Path,
    workspace_root: Path,
    dry_run: bool,
    llm_client: Any,
    tracker: object | None,
) -> list[Path] | list[dict]:
    """Run the full parse → cluster → generate pipeline.

    Returns:
        In normal mode: list of written file Paths.
        In dry-run mode: list of serialised config dicts (nothing written).
    """
    doc = parse_newsletter(newsletter_path)
    newsletter_slug = _slug_from_path(newsletter_path)

    state: dict = {}
    clusters = await cluster_papers(doc, llm_client, tracker=tracker, state=state)

    configs = []
    for cluster in clusters:
        cluster.newsletter_slug = newsletter_slug
        config = await generate_candidate_config(
            cluster, llm_client, tracker=tracker, state=state
        )
        configs.append(config)

    if dry_run:
        import dataclasses
        return [dataclasses.asdict(c) for c in configs]

    return save_candidate_configs(configs, workspace_root, newsletter_slug=newsletter_slug)


def _slug_from_path(path: Path) -> str:
    return path.stem.replace(" ", "_").lower()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


async def _main(args: argparse.Namespace) -> int:
    import os
    from pathlib import Path

    newsletter_path = Path(args.file)
    workspace_root = Path(os.environ.get("SRF_WORKSPACE_ROOT", "/data/workspace"))

    # Build a minimal stub LLM client — replaced by real client in Epic 5
    llm_client = _build_stub_llm_client()
    tracker = _build_tracker()

    try:
        result = await run_pipeline(
            newsletter_path=newsletter_path,
            workspace_root=workspace_root,
            dry_run=args.dry_run,
            llm_client=llm_client,
            tracker=tracker,
        )
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.dry_run:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        for path in result:
            print(str(path))

    return 0


def _build_stub_llm_client() -> Any:
    """Return a minimal stub LLM client.

    The real provider-backed client is built in Epic 5 (src/srf/llm/).
    Until then, the CLI requires a running LLM provider configured via env vars.
    """
    import os

    provider = os.environ.get("SRF_LLM_PROVIDER", "")
    if provider == "anthropic":
        try:
            import anthropic

            class _AnthropicClient:
                def __init__(self) -> None:
                    self._client = anthropic.AsyncAnthropic(
                        api_key=os.environ["SRF_LLM_API_KEY"]
                    )
                    self._model = os.environ["SRF_LLM_MODEL"]

                async def complete(self, messages: list[dict]) -> Any:
                    system = next(
                        (m["content"] for m in messages if m["role"] == "system"), ""
                    )
                    user_messages = [m for m in messages if m["role"] != "system"]
                    response = await self._client.messages.create(
                        model=self._model,
                        max_tokens=1024,
                        system=system,
                        messages=user_messages,
                    )
                    response.content = response.content[0].text
                    return response

            return _AnthropicClient()
        except ImportError:
            pass

    # Fallback: raise at call time
    class _NoClient:
        async def complete(self, _messages: list[dict]) -> Any:
            raise RuntimeError(
                "No LLM client available. Set SRF_LLM_PROVIDER=anthropic and install the SDK."
            )

    return _NoClient()


def _build_tracker() -> object | None:
    import os

    if not os.environ.get("PROMPTLEDGER_API_URL"):
        return None
    try:
        from srf.config import SRFConfig
        from srf.observability import build_tracker

        config = SRFConfig.from_env()
        return build_tracker(config)
    except Exception:  # noqa: BLE001
        return None


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Parse a newsletter and generate candidate forum configs."
    )
    parser.add_argument("--file", required=True, help="Path to the newsletter Markdown file")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print candidate configs as JSON without writing files",
    )
    args = parser.parse_args()
    sys.exit(asyncio.run(_main(args)))


if __name__ == "__main__":
    main()
