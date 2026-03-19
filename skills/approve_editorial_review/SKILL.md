---
name: approve_editorial_review
description: Approve or reject the editorial review of a completed SRF debate synthesis. Resumes the Lobster workflow at the editorial approval gate using the resume_token provided in the approval notification.
---

# approve_editorial_review

Use this skill when a researcher receives an editorial review notification for a completed Synthetic Research Forum debate and wants to approve or reject the synthesis for publication.

## Parameters

- **resume_token** (required): The Lobster workflow resume token provided in the editorial review notification. This token identifies the paused workflow step waiting for editorial approval.
- **decision** (required): Either `"approve"` or `"reject"`.
- **notes** (optional): Editorial notes or feedback to attach to the decision. Included in the synthesis artifact metadata.

## Instructions

1. Confirm `resume_token` and `decision` have been provided. If not, ask the researcher.

2. Validate `decision` is either `"approve"` or `"reject"`. If neither, ask the researcher to clarify.

3. Use the lobster tool to resume the paused workflow:

   ```
   {"action": "resume", "token": <resume_token>, "input": {"decision": <decision>, "notes": <notes>}}
   ```

4. If `decision` is `"approve"`:
   - Confirm to the researcher that the synthesis has been approved and will be published to the forum output directory.

5. If `decision` is `"reject"`:
   - Confirm to the researcher that the synthesis has been rejected.
   - Ask if they would like to provide specific feedback for the next debate iteration.

## Notes

- The `resume_token` is a Lobster workflow identifier — it is only valid once and expires when the workflow is either resumed or times out.
- Editorial approval is the final gate before synthesis artifacts are written to the `/data/workspace/forum/<forum_id>/synthesis/` output directory.
- All decisions (approve and reject) are logged with the `forum_id` and `trace_id` for auditability.
