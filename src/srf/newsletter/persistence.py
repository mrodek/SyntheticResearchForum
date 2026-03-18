"""Candidate config persistence — writes CandidateForumConfig objects to disk."""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import structlog

from srf.newsletter.models import CandidateForumConfig, PersistenceError

logger = structlog.get_logger(__name__)


def save_candidate_configs(
    configs: list[CandidateForumConfig],
    workspace_root: Path,
    *,
    newsletter_slug: str,
) -> list[Path]:
    """Persist each CandidateForumConfig to workspace_root/candidates/{slug}/candidate_N.json.

    Creates the output directory if it does not exist.

    Returns:
        List of paths to written files (1-based index in filename).

    Raises:
        PersistenceError: if the workspace root is not writable.
    """
    output_dir = Path(workspace_root) / "candidates" / newsletter_slug

    try:
        output_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise PersistenceError(
            f"Cannot create output directory under {workspace_root}: {exc}"
        ) from exc

    written: list[Path] = []
    for idx, config in enumerate(configs, start=1):
        path = output_dir / f"candidate_{idx}.json"
        try:
            path.write_text(
                json.dumps(_serialise(config), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError as exc:
            raise PersistenceError(
                f"Failed to write config to {path}: {exc}"
            ) from exc
        logger.info("candidate config written", path=str(path), slug=newsletter_slug)
        written.append(path)

    return written


def _serialise(config: CandidateForumConfig) -> dict:
    """Convert a CandidateForumConfig to a JSON-serialisable dict.

    Excludes source_papers (full PrimarySignal objects) — paper_refs contains the IDs.
    """
    d = dataclasses.asdict(config)
    # Drop the nested source_papers list (verbose; paper_refs carries the identity keys)
    d.pop("source_papers", None)
    return d
