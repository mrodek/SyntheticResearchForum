---
name: trigger_newsletter_forum
description: Parse an AI research newsletter and identify candidate papers for forum debate. Runs the SRF newsletter processing pipeline given a source file path or URL.
---

# trigger_newsletter_forum

Use this skill when a researcher provides a newsletter PDF, Markdown file, or URL and wants to identify candidate research papers for a Synthetic Research Forum debate.

## Parameters

- **source_path** (required): Path to the newsletter file (PDF or Markdown) or a URL pointing to the newsletter content.

## Instructions

1. Confirm the `source_path` parameter has been provided. If not, ask the researcher to provide the path or URL to the newsletter.

2. Use the exec tool to run the newsletter parsing pipeline:

   ```
   /data/venv/bin/python /data/srf/scripts/parse_newsletter.py --file <source_path>
   ```

3. Review the parsed output. The script will produce one or more JSON files in `/data/workspace/candidates/{newsletter_slug}/` — one `candidate_N.json` per identified tension axis, each containing a `CandidateForumConfig`.

4. Summarise the candidate papers and proposed framing question for the researcher.

5. Ask the researcher whether they would like to proceed to the `review_forum_debate_format` step to stage the forum.

## Error Handling

**This skill must never edit any file under `/data/srf/`.** That directory is a git-tracked deployment clone. Editing it in response to errors bypasses version control and code review, and causes `git pull` to fail on the next redeploy. All source-level fixes must be made in the repository by the developer and redeployed.

If the script in step 2 exits with a non-zero code:
- Report the full stderr output to the researcher verbatim.
- Stop immediately. Do not read other files to diagnose the cause. Do not edit any files. Do not retry.
- Tell the researcher: "The pipeline failed. Please check the error above, fix the underlying issue in the repository, and re-invoke this skill."

If the script produces no output or output that cannot be located:
- Report what was observed (empty stdout, missing file, etc.) and stop.

Do not attempt to work around failures by modifying scripts, adding fallback logic, or running alternative commands. The pipeline is deterministic by design; workarounds applied in a skill session are ephemeral and will be lost on the next redeploy.

## Notes

- The script writes structured logs to stderr; stdout contains the paths of the written candidate JSON files (one per line).
- Candidates are written to `/data/workspace/candidates/{newsletter_slug}/candidate_N.json`.
- All paper candidates are deduplicated by arXiv ID before configs are generated.
- The script accepts only local file paths (`--file`). URLs are not supported.
