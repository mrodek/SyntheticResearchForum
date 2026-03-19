---
name: review_forum_debate_format
description: Review and approve a CandidateForumConfig, stage the forum workspace, and launch the SRF debate pipeline via Lobster. Called after trigger_newsletter_forum when the researcher approves the paper selection and framing.
---

# review_forum_debate_format

Use this skill when a researcher has reviewed the candidate forum configuration produced by `trigger_newsletter_forum` and wants to launch the full Synthetic Research Forum debate pipeline.

## Parameters

- **config_path** (required): Path to the `CandidateForumConfig` JSON file produced by the newsletter processing step. Typically under `/data/workspace/newsletters/<slug>/candidate_config.json`.

## Instructions

1. Confirm the `config_path` parameter has been provided. If not, ask the researcher to provide the path to the `CandidateForumConfig` JSON file.

2. Use the exec tool to validate and stage the forum:

   ```
   python scripts/validate_and_stage_forum.py --config-path <config_path>
   ```

   The script exits 0 on success and writes trigger JSON to stdout. Capture this output — it contains `forum_id`, `workspace_path`, and `trace_id`.

3. Parse the trigger JSON from stdout. If the script exits non-zero, report the error from stderr to the researcher and stop.

4. Use the lobster tool to launch the srf_forum workflow with the trigger JSON:

   ```
   {"action": "run", "pipeline": "workflows/srf_forum.yaml", "input": <trigger_json>}
   ```

5. Confirm to the researcher that the forum debate pipeline has been launched. Provide the `forum_id` and note that they will be prompted for editorial approval when the debate completes.

## Notes

- The `validate_and_stage_forum.py` script creates the forum workspace directory and writes `state.json`.
- The Lobster `srf_forum` workflow runs the full pipeline: paper fetching → extraction → agent preparation → debate → synthesis → editorial review gate.
- The editorial review approval step will invoke the `approve_editorial_review` skill.
