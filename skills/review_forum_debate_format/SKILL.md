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
   /data/venv/bin/python /data/srf/scripts/validate_and_stage_forum.py --config-path <config_path>
   ```

   The script exits 0 on success and writes trigger JSON to stdout. Capture this output — it contains `forum_id`, `workspace_path`, and `trace_id`.

3. Parse the trigger JSON from stdout.

4. Serialise the trigger JSON object to a JSON string (i.e. `JSON.stringify(triggerJson)` or `json.dumps(trigger_json)`).

5. Use the lobster tool to launch the srf_forum workflow with the serialised trigger string:

   ```
   {"action": "run", "pipeline": "/data/srf/workflows/srf_forum.yaml", "argsJson": "<serialised trigger JSON string>"}
   ```

6. Confirm to the researcher that the forum debate pipeline has been launched. Provide the `forum_id` and note that they will be prompted for editorial approval when the debate completes.

## Error Handling

**This skill must never edit any file under `/data/srf/`.** That directory is a git-tracked deployment clone. Editing it in response to errors bypasses version control and code review, and causes `git pull` to fail on the next redeploy. All source-level fixes must be made in the repository by the developer and redeployed.

| Failure | Required action |
|---|---|
| Script in step 2 exits non-zero | Report the full stderr output to the researcher verbatim. Stop. Do not read other files to diagnose the cause. Do not edit any files. Do not retry. Tell the researcher to fix the underlying issue and re-invoke the skill. |
| Script exits 0 but stdout is empty or not valid JSON | Report what was received (empty output, parse error). Stop. Do not attempt to construct or guess the trigger JSON. |
| Lobster tool in step 5 returns an error | Report the lobster error response to the researcher verbatim. Stop. The forum workspace may have been created by step 2 — note the `workspace_path` so the researcher can inspect or clean up manually. |

## Notes

- The `validate_and_stage_forum.py` script creates the forum workspace directory and writes `state.json`.
- The Lobster `srf_forum` workflow runs the full pipeline: paper fetching → extraction → agent preparation → debate → synthesis → editorial review gate.
- The editorial review approval step will invoke the `approve_editorial_review` skill.
