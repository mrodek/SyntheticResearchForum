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
   python scripts/parse_newsletter.py --source-path <source_path> --output-dir /data/workspace/newsletters
   ```

3. Review the parsed output. The script will produce a JSON file in `/data/workspace/newsletters/` listing extracted paper candidates and a `CandidateForumConfig`.

4. Summarise the candidate papers and proposed framing question for the researcher.

5. Ask the researcher whether they would like to proceed to the `review_forum_debate_format` step to stage the forum.

## Notes

- The script writes structured logs to stderr; stdout contains the output JSON path.
- If `source_path` is a URL, the script will attempt to fetch and parse the remote content.
- All paper candidates are deduplicated by arXiv ID before the config is generated.
