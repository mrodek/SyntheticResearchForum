name: srf_forum
version: "1.0"

steps:

  # ── Phase 4: Workspace Generation ──────────────────────────────────────────
  # Initial input arrives via $LOBSTER_ARGS_JSON (passed as argsJson at invocation).
  # The trigger JSON contains: forum_id, workspace_path, trace_id, config_path.
  - id: workspace_setup
    command: /bin/sh -c 'echo "$LOBSTER_ARGS_JSON" | /data/venv/bin/python /data/srf/scripts/run_workspace_setup.py'
    # Output: { forum_id, workspace_path, paper_refs, framing_question, topic, trace_id }

  # ── Phase 5: Paper Extraction ───────────────────────────────────────────────
  - id: paper_extraction
    command: /data/venv/bin/python /data/srf/scripts/run_paper_extraction.py
    stdin: $workspace_setup.json
    # Output: { ...prev, papers: [{ arxiv_id, abstract, full_text, extraction_status }] }

  # ── Phase 6: Agent Preparation ──────────────────────────────────────────────
  # Single script runs all Paper Agent preparations concurrently via asyncio.gather().
  # Partial failure: retry SRF_MAX_PREP_RETRIES per agent; abort if < SRF_MIN_AGENTS succeed.
  - id: agent_preparation
    command: /data/venv/bin/python /data/srf/scripts/run_preparation.py
    stdin: $paper_extraction.json
    # Output: { ...prev, agents: [{ agent_id, role, status, prep_artifact_path }] }

  # ── Phases 7–11: Debate ─────────────────────────────────────────────────────
  # Bridge script writes agents to state.json, prepares debate_context.json,
  # triggers run_forum_debate OpenClaw skill, polls for DEBATE_CLOSED sentinel,
  # validates transcript, and emits transcript metadata to stdout.
  - id: debate
    command: /data/venv/bin/python /data/srf/scripts/run_debate_bridge.py
    stdin: $agent_preparation.json
    # Output: { ...prev, transcript_path, turn_count, debate_status, close_reason }

  # ── Phase 12: Synthesis ─────────────────────────────────────────────────────
  - id: synthesis
    command: echo placeholder
    stdin: $debate.json
    # Output: { ...prev, synthesis_path }

  # ── Phase 13: Contribution Evaluation ──────────────────────────────────────
  - id: evaluation
    command: echo placeholder
    stdin: $synthesis.json
    # Output: { ...prev, evaluation_path, evaluation_block }

  # ── Human Gate: Editorial Review ────────────────────────────────────────────
  # Lobster halts here and returns a resumeToken.
  # Resumed by the approve_editorial_review OpenClaw skill via the lobster resume action.
  - id: editorial_review_gate
    approval: "Review synthesis and evaluation scores. Approve to proceed to publication?"

  # ── Phase 14: Policy Proposals ──────────────────────────────────────────────
  - id: policy_proposals
    command: echo placeholder
    stdin: $editorial_review_gate.json
    # Output: { ...prev, policy_proposal_path }

  # ── Phase 15: Publication ────────────────────────────────────────────────────
  - id: publication
    command: echo placeholder
    stdin: $policy_proposals.json
    # Output: { ...prev, published_artifact_paths, forum_status: "complete" }
