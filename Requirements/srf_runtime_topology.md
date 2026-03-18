# SRF Runtime Topology

This document is the authoritative reference for how SRF components are deployed, connected, and orchestrated at runtime. All subsequent epics and stories must be consistent with this topology. Any change to the topology requires updating this document first.

---

## 1. Railway Service Configuration

SRF runs as a **single persistent Railway service** — one container, always on, no per-phase cold starts.

```
Railway Service: srf-gateway
  Image:         Python 3.11 + OpenClaw Gateway + Lobster
  Volume:        /data/workspace  (persistent, survives deploys and sleeps)
  Port:          8080 (HTTP — health check + webhook receiver + MCP server)
  Restart:       always
```

### Environment Variables

```
# LLM provider (required)
SRF_LLM_PROVIDER
SRF_LLM_MODEL
SRF_LLM_API_KEY

# PromptLedger (optional — system runs without it)
PROMPTLEDGER_API_URL
PROMPTLEDGER_API_KEY

# Workspace
SRF_WORKSPACE_ROOT     # defaults to /data/workspace

# Logging
SRF_LOG_LEVEL          # defaults to INFO

# Gateway
SRF_GATEWAY_TOKEN      # secures MCP + webhook endpoints
SRF_MAX_PREP_RETRIES   # number of retry attempts for failed agent preparation (default 3)
SRF_MIN_AGENTS         # minimum viable Paper Agents for a debate to proceed (default 2)
```

### Volume Layout

```
/data/workspace/
  newsletters/           ← newsletter archive (copied in by MCP trigger)
  candidates/
    {newsletter_slug}/   ← CandidateForumConfig JSON files (Epic 3 output)
  forum/
    {forum_id}/
      state.json         ← Lobster workflow state, written at every phase boundary
      preparation/
        {agent_id}/      ← Paper Agent preparation artifacts
      transcripts/       ← append-only turn-by-turn JSON transcript
      synthesis/         ← synthesis and evaluation outputs
      logs/              ← forum-scoped structured log
  memory/
    {role}/              ← Agent memory store (Epic 2, post first complete run)
```

---

## 2. Gateway Startup Sequence

Every time the Railway container starts (initial deploy or wake from sleep), the Gateway executes this sequence before serving any requests:

```
1. Load SRFConfig.from_env()           → raise ConfigurationError if required vars absent
2. configure_logging(config)           → structlog JSON to stdout
3. tracker = build_tracker(config)     → None if PL not configured
4. register_prompts(tracker, prompts)  → no-op if tracker is None
5. Initialise workspace directories    → create /data/workspace structure if absent
6. Start HTTP server on :8080          → health, webhook, MCP endpoints now live
7. Log INFO "Gateway ready"            → startup complete
```

Step 4 (prompt registration) is the PromptLedger handshake. If PromptLedger is configured but unreachable, the Gateway logs a WARNING and continues — prompt registration failure is not fatal.

`GET /health` must respond within 500 ms from the moment step 6 completes.

---

## 3. The Two Trigger Flows

### Flow A — Newsletter Trigger (Epic 3)

Originates from Claude Desktop. Does not start a Lobster workflow. Produces candidate configs for human review.

```
Claude Desktop
  → calls MCP tool: trigger_newsletter_forum(source_path)
  → Gateway copies newsletter to /data/workspace/newsletters/
  → Gateway runs Epic 3 pipeline (parse → cluster → generate → save)
  → Gateway returns candidate config summaries to Claude Desktop
  → Status: awaiting_approval (no forum_id assigned yet)
```

### Flow B — Approval + Debate Trigger (Epic 8 gate, but established here)

Originates from Claude Desktop after human review of candidate configs. Starts the Lobster workflow.

```
Claude Desktop
  → calls MCP tool: review_forum_debate_format(config_path, decision="approved")
  → Gateway validates config
  → Gateway assigns forum_id, writes initial state.json
  → Gateway invokes Lobster: lobster exec workflows/srf_forum.yaml
  → Lobster begins phase execution (see Section 4)
```

---

## 4. Lobster Workflow — srf_forum.yaml

The Lobster workflow covers phases 4–15 of the SRF lifecycle. Phases 1–3 (newsletter parsing, candidate config, editorial approval) are pre-Lobster and handled by the MCP tools.

```yaml
name: srf_forum
version: "1.0"

steps:

  # ── Phase 4: Workspace Generation ──────────────────────────────────────────
  - name: workspace_setup
    run: python scripts/run_workspace_setup.py
    stdin: $trigger.json
    # Output: { forum_id, workspace_path, paper_refs, framing_question, topic }

  # ── Phase 5: Paper Extraction ───────────────────────────────────────────────
  - name: paper_extraction
    run: python scripts/run_paper_extraction.py
    stdin: $workspace_setup.json
    # Output: { ...prev, papers: [{ arxiv_id, title, abstract, full_text }] }

  # ── Phase 6: Agent Preparation ──────────────────────────────────────────────
  # Single script runs all Paper Agent preparations concurrently via asyncio.gather().
  # Partial failure policy: retry SRF_MAX_PREP_RETRIES times per agent.
  # If retries exhausted: mark agent degraded, continue if >= SRF_MIN_AGENTS remain.
  # If fewer than SRF_MIN_AGENTS succeed: abort workflow, write error state.
  - name: agent_preparation
    run: python scripts/run_preparation.py
    stdin: $paper_extraction.json
    # Output: { ...prev, agents: [{ agent_id, role, status, prep_artifact_path }] }

  # ── Phases 7–11: Debate ─────────────────────────────────────────────────────
  # The entire debate loop runs as a single Lobster step inside OpenClaw.
  # Moderator controls turn routing via enqueue_speaker tool (see Section 5).
  - name: debate
    run: openclaw run workflows/debate_workflow.yaml
    stdin: $agent_preparation.json
    # Output: { ...prev, transcript_path, turn_count, debate_status }

  # ── Phase 12: Synthesis ─────────────────────────────────────────────────────
  - name: synthesis
    run: python scripts/run_synthesis.py
    stdin: $debate.json
    # Output: { ...prev, synthesis_path }

  # ── Phase 13: Contribution Evaluation ──────────────────────────────────────
  - name: evaluation
    run: python scripts/run_evaluation.py
    stdin: $synthesis.json
    # Output: { ...prev, evaluation_path, evaluation_block }

  # ── Human Gate: Editorial Review ────────────────────────────────────────────
  # Lobster halts here. Gateway stores resume token in state.json.
  # Resumed by MCP tool: approve_editorial_review → POST /webhook/resume
  - name: editorial_review_gate
    approval:
      message: "Synthesis and evaluation complete. Review artifacts and approve for publication."
      data: $evaluation.json

  # ── Phase 14: Policy Proposals ──────────────────────────────────────────────
  - name: policy_proposals
    run: python scripts/run_policy_proposals.py
    stdin: $editorial_review_gate.json
    # Output: { ...prev, policy_proposal_path }

  # ── Phase 15: Publication ────────────────────────────────────────────────────
  - name: publication
    run: python scripts/run_publication.py
    stdin: $policy_proposals.json
    # Output: { ...prev, published_artifact_paths, forum_status: "complete" }
```

### State passing between steps

Every script reads its input from `stdin` (the JSON output of the previous step) and writes its full output to `stdout`. Lobster passes these as `$step.json` references. The complete workflow state — `forum_id`, `workspace_path`, `trace_id`, all span IDs — travels through every step in this chain. No step reaches into the filesystem to find its own inputs; everything arrives via stdin.

Each script also writes a checkpoint to `state.json` on the workspace volume before returning. If the Gateway process restarts mid-workflow, the state can be inspected and the workflow replayed from the last completed step.

---

## 5. The Debate Loop — debate_workflow.yaml (OpenClaw)

The debate is a single Lobster step that hands execution to OpenClaw's agent runtime. Inside this step, the Moderator agent drives turn routing dynamically.

```
OpenClaw debate_workflow.yaml
  │
  ├── Moderator agent (orchestrator — drives routing via tools)
  │     tools available:
  │       enqueue_speaker(agent_id, instruction)  ← routes next turn
  │       read_transcript()                        ← reads full debate state
  │       read_guardrail_signals()                 ← reads Guardrail evaluations
  │       close_debate(reason)                     ← terminates loop, writes closing
  │
  ├── Paper Agents × N (up to 3 — degraded agents absent, not substituted)
  │     each produces: { speaker, content, turn_id, parent_turn_id }
  │
  ├── Challenger Agent
  │     enters when Moderator calls enqueue_speaker("challenger", ...)
  │
  └── Guardrail Agent (silent — never speaks, always evaluates)
        runs after every turn
        signals: { ok | warning | critical }
        CRITICAL signal: forces Moderator routing decision next (cannot be bypassed)
```

### Hard limits (enforced by debate_workflow.yaml, not the Moderator)

```
max_total_turns:     40     (configurable via forum config)
max_turns_per_agent: 10
max_rounds:          5
```

If any hard limit is reached, OpenClaw closes the debate loop and passes control back to Lobster regardless of the Moderator's state. The Moderator does not override these limits — it operates within them.

### Transcript immutability

Every turn written to `transcripts/` is append-only. If a CRITICAL Guardrail signal fires, the offending turn remains in the transcript with the alert attached as metadata. The Moderator's subsequent routing decision is logged as a new turn. Nothing is deleted or modified.

---

## 6. HTTP Endpoints (Gateway)

The Gateway HTTP server exposes three endpoint groups:

```
GET  /health
     → 200 OK within 500 ms, always

POST /webhook/resume
     → Body: { resume_token, decision, reviewer_notes }
     → Resumes a halted Lobster workflow from its approval gate
     → Auth: SRF_GATEWAY_TOKEN header

POST /webhook/trigger
     → Body: { config_path }
     → Alternative to MCP tool for triggering a forum from an approved config
     → Auth: SRF_GATEWAY_TOKEN header

MCP  /mcp  (HTTP MCP transport — Claude Desktop connects here)
     → Exposes MCP tools: trigger_newsletter_forum, review_forum_debate_format,
       approve_editorial_review
     → Auth: SRF_GATEWAY_TOKEN header
```

Claude Desktop connects to the Railway service URL at `/mcp` using the HTTP MCP transport. The `SRF_GATEWAY_TOKEN` is configured in Claude Desktop's MCP server settings.

---

## 7. MCP Tools (Full Set)

| Tool | Trigger | Effect |
|---|---|---|
| `trigger_newsletter_forum` | Newsletter published in ResearchKG | Copies newsletter, runs Epic 3 pipeline, returns candidate configs. **Does not start Lobster.** |
| `review_forum_debate_format` | Human approves a candidate config | Validates config, assigns forum_id, starts Lobster workflow. |
| `approve_editorial_review` | Human approves post-synthesis review | Calls `POST /webhook/resume` with approval decision. Resumes publication phase. |

All three tools require `SRF_GATEWAY_TOKEN` authentication. All three log structured events to the application log.

---

## 8. Data Boundaries

| Data | Location | Lifetime | Owner |
|---|---|---|---|
| Active Lobster workflow context | Gateway in-memory | Duration of one forum run | Lobster |
| OpenClaw debate session state | Gateway in-memory | Duration of debate step | OpenClaw |
| PromptLedger tracker client | Gateway in-memory | Process lifetime | Gateway startup |
| Resume tokens | `/data/workspace/forum/{id}/state.json` | Until workflow completes | Gateway |
| Forum artifacts (prep, transcript, synthesis) | `/data/workspace/forum/{id}/` | Permanent | SRF |
| Candidate configs | `/data/workspace/candidates/` | Until consumed or rejected | SRF |
| Agent memory store | `/data/workspace/memory/{role}/` | Permanent, version-stamped | Epic 2 |
| Trace/span lineage | PromptLedger | Permanent | PromptLedger |
| Prompt registry | PromptLedger | Permanent | PromptLedger |

---

## 9. Partial Failure Policy

### Paper Agent preparation failure

```
For each Paper Agent:
  attempt preparation
  on failure: wait 5s, retry up to SRF_MAX_PREP_RETRIES (default 3)
  if retries exhausted:
    mark agent status = "degraded"
    log WARNING with agent_id and final error

After all agents attempted:
  if count(status == "ok") >= SRF_MIN_AGENTS (default 2):
    proceed — degraded agents are absent from debate, not substituted
    log WARNING listing degraded agents
  else:
    abort workflow
    write state.json { forum_status: "aborted", reason: "insufficient_agents" }
    log ERROR
```

### Synthesis / Evaluation failure

Retry up to `SRF_MAX_PREP_RETRIES`. If all retries exhausted, abort the workflow and write error state. Do not proceed to editorial review with a degraded synthesis — the evaluation artifact is the foundation of the memory governance chain.

### PromptLedger failure

Never blocks the pipeline. All `tracker.execute()` and `log_span()` calls are fire-and-forget with 5xx resilience (established in Story 1.5). A PromptLedger outage produces incomplete traces, not a failed forum run.

### LLM provider failure

Retry with exponential backoff up to 3 attempts. After 3 failures, abort the current step and write error state. Do not silently proceed with missing agent outputs.

---

## 10. PromptLedger Trace Hierarchy

Three span-creation mechanisms are used — the right tool depends on whether an LLM call is involved:

| Mechanism | When to use | Span kind |
|---|---|---|
| `tracker.execute()` | Every LLM call — creates span automatically, returns `result.span_id`, writes `state["last_span_id"]` | `llm.generation` |
| `tracker.log_span()` | Non-LLM spans: workflow phase boundaries, guardrail evaluations | `workflow.phase`, `guardrail.check` |
| `tracker.log_tool_call()` | Moderator OpenClaw tool calls during debate | `tool` |

```
trace (forum_id)
  │
  ├── phase: forum.newsletter_processing    log_span(kind=workflow.phase) — Epic 3
  │     ├── newsletter.paper_clustering     execute() auto-creates span — Epic 3
  │     └── newsletter.framing_question     execute() auto-creates span — Epic 3
  │
  ├── phase: forum.preparation              log_span(kind=workflow.phase) — Epic 5
  │     ├── agent.paper_preparation.{N}     execute() auto-creates span — Epic 5, parallel
  │     ├── agent.moderator_briefing        execute() auto-creates span — Epic 5
  │     └── agent.challenger_preparation    execute() auto-creates span — Epic 5
  │
  ├── phase: forum.debate                   log_span(kind=workflow.phase) — Epic 6
  │     ├── debate.turn.{turn_id}           execute() auto-creates span — Epic 6 per turn
  │     │     ├── {tool_name}               log_tool_call() — Moderator OpenClaw tools
  │     │     └── guardrail.{turn_id}       log_span(kind=guardrail.check) — child of turn
  │     └── ...
  │
  ├── synthesis                             execute() auto-creates span — Epic 7
  ├── evaluation                            execute() auto-creates span — Epic 7
  └── publication                           execute() auto-creates span — Epic 8
```

Span IDs travel through the Lobster workflow state dict (`state["trace_id"]`, `state["phase_span_id"]`, `state["last_span_id"]`), never through `contextvars` across step boundaries. `state["last_span_id"]` is written by every `tracker.execute()` call and is used as `parent_span_id` for child spans (guardrail checks, tool calls).

---

## 11. What Each Epic Builds in This Topology

| Epic | What it adds |
|---|---|
| 3 | MCP trigger tool, Epic 3 pipeline scripts, `/mcp` endpoint (partial) |
| 4 | `run_workspace_setup.py`, `run_paper_extraction.py`, `srf_forum.yaml` (skeleton) |
| 5 | `run_preparation.py` (parallel asyncio), preparation agent prompts |
| 6 | `debate_workflow.yaml`, Moderator + Paper Agent + Challenger + Guardrail |
| 7 | `run_synthesis.py`, `run_evaluation.py`, evaluation_block schema |
| 8 | `run_policy_proposals.py`, `run_publication.py`, `approve_editorial_review` MCP tool, `editorial_review_gate` approval in Lobster |
| 9 | Observability dashboards, cost reporting, drift detection hooks |
| 2 | Memory store, candidate extraction from evaluation_block, injection into preparation |
| 10 | Prompt governance reporting, longitudinal quality tracking |
