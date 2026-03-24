---
name: update_srf
description: Pull the latest SRF code from GitHub and reinstall the Python package on the Railway volume. Use this instead of a full redeploy when only Python code has changed.
---

# update_srf

Use this skill when the developer wants to apply a code change from the SRF GitHub repository to the running service without a full Railway redeploy.

This skill updates the SRF Python code in ~15 seconds. A full redeploy takes 5–10 minutes because it rebuilds OpenClaw from source — that rebuild is unnecessary for SRF Python changes.

## When to use

- SRF Python code has been pushed to `main` and needs to be live immediately
- A bug fix has been merged and the developer wants to verify it on the service
- Skills under `skills/` have been updated

## When NOT to use

- Environment variables have changed → use Railway redeploy
- OpenClaw version has changed → use Railway redeploy
- `bootstrap.sh` itself has changed → use Railway redeploy

## Instructions

1. Use the exec tool to run the update script:

   ```
   bash /data/srf/scripts/update_srf.sh
   ```

2. If the script exits with code 0, report the git SHA from stdout to the developer:

   > "SRF updated to `{sha}`."

3. The update log is written to `/data/workspace/logs/update_srf.log`. You do not need to read it on success.

## Error Handling

**This skill must never edit any file under `/data/srf/`.** That directory is a git-tracked deployment clone. Editing it in response to errors bypasses version control and code review, and causes `git pull` to fail on the next update. All source-level fixes must be made in the repository by the developer and pushed to GitHub.

If the script in step 1 exits with a non-zero code:
- Report the full stderr output to the developer verbatim.
- Stop immediately. Do not read other files to diagnose the cause. Do not edit any files. Do not retry.
- Tell the developer: "The update failed. Please check the error above, fix the underlying issue in the repository, push to GitHub, and re-invoke this skill."

If the script produces no output:
- Report that stdout was empty and stop.

Do not attempt to run `git pull`, `pip install`, or `chmod` commands directly. The script handles the unlock/pull/reinstall/relock sequence atomically. Running these steps manually risks leaving `/data/srf/` in an unlocked state.
