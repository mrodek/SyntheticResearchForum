# SRF Runtime Topology

This document is the authoritative reference for how SRF components are deployed, connected, and orchestrated at runtime. All subsequent epics and stories must be consistent with this topology. Any change to the topology requires updating this document first.

---

## 1. Railway Service Configuration

SRF runs as a **single persistent Railway service** using the **OpenClaw Gateway Railway template** (one-click deploy). OpenClaw is a Node.js gateway that provides the HTTP server, MCP transport, agent runtime, and web control UI. Lobster (`@clawdbot/lobster`, installed via `npm install -g @clawdbot/lobster`) is a separate CLI tool installed alongside OpenClaw on the gateway host.

```
Railway Service: srf-gateway
  Runtime:       OpenClaw Gateway (Node.js, npm-based)
  Volume:        /data  (persistent — survives deploys and sleeps)
  Port:          8080 (HTTP — OpenClaw handles health, webhooks, MCP, control UI)
  Restart:       always
```

### Environment Variables

```
# SRF Python scripts (used by Lobster step scripts and srf_init.py)
SRF_LLM_PROVIDER       # e.g. anthropic, openai — tracker=None fallback only
SRF_LLM_MODEL          # e.g. claude-sonnet-4-6, gpt-4o
SRF_LLM_API_KEY        # provider key for tracker=None fallback only
PROMPTLEDGER_API_URL   # PromptLedger instance URL (optional)
PROMPTLEDGER_API_KEY   # project-scoped key (optional)
SRF_LOG_LEVEL          # defaults to INFO
SRF_MAX_PREP_RETRIES   # number of retry attempts for failed agent preparation (default 3)
SRF_MIN_AGENTS         # minimum viable Paper Agents for debate to proceed (default 2)
SRF_MIN_PAPERS         # minimum successfully extracted papers (default 2)
SRF_ARXIV_DELAY_SECONDS  # rate-limit delay between arXiv fetches (default 3)
SRF_DEBATE_CONTEXT_TOKENS  # max chars of transcript context in agent turn prompts (default 60000)

# OpenClaw Gateway (set via Railway Variables or /setup wizard)
SETUP_PASSWORD         # required — secures the /setup web wizard
PORT=8080              # required — must match Public Networking port
OPENCLAW_STATE_DIR=/data/.openclaw    # recommended
OPENCLAW_WORKSPACE_DIR=/data/workspace  # recommended — SRF workspace root
OPENCLAW_GATEWAY_TOKEN  # recommended — secures MCP + webhook endpoints
```

### Volume Layout

```
/data/
  .openclaw/             ← OpenClaw Gateway state (sessions, config, skills)
  workspace/
    newsletters/           ← newsletter archive (copied in by trigger_newsletter_forum skill)
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

## 2. Startup Sequence

OpenClaw Gateway starts automatically when the Railway container wakes. Before the first agent turn is served, `scripts/srf_init.py` must run via OpenClaw's exec tool or startup hook:

```
OpenClaw Gateway starts (managed by Railway)
  → OpenClaw loads config, skills, and tools (alsoAllow: ["lobster"])
  → OpenClaw exposes HTTP endpoints on :8080
  → scripts/srf_init.py is invoked (via exec tool on first agent wake or startup hook):
      1. SRFConfig.from_env()              → raise ConfigurationError if required vars absent
      2. configure_logging(config)         → structlog JSON to stdout
      3. tracker = build_tracker(config)   → None if PROMPTLEDGER_API_URL absent
      4. register_prompts(tracker, ALL_PROMPTS)  → no-op if tracker is None; WARNING if PL unreachable
      5. Initialise workspace directories  → create /data/workspace structure if absent
      6. Log INFO "SRF init complete"
```

`GET /health` is served by OpenClaw and must respond within 500 ms at all times — it does not depend on `srf_init.py` completing.

If PromptLedger is configured but unreachable, step 4 logs a WARNING and continues. Prompt registration failure is not fatal.

---

## 3. The Two Trigger Flows

### Flow A — Newsletter Trigger (Epic 3)

Originates from Claude Desktop via the `trigger_newsletter_forum` OpenClaw skill. Does not start a Lobster workflow. Produces candidate configs for human review.

```
Claude Desktop
  → MCP call → OpenClaw skill: trigger_newsletter_forum(source_path)
  → OpenClaw agent uses exec tool: python scripts/trigger_newsletter_forum.py
  → Script copies newsletter to /data/workspace/newsletters/
  → Script runs Epic 3 pipeline (parse → cluster → generate → save)
  → Script returns candidate config summaries
  → Status: awaiting_approval (no forum_id assigned yet)
```

### Flow B — Approval + Debate Trigger

Originates from Claude Desktop after human review of candidate configs. Starts the Lobster workflow via the `review_forum_debate_format` OpenClaw skill.

```
Claude Desktop
  → MCP call → OpenClaw skill: review_forum_debate_format(config_path, decision="approved")
  → OpenClaw agent uses exec tool: python scripts/validate_and_stage_forum.py
  → Script validates config, assigns forum_id, writes initial state.json
  → OpenClaw agent uses lobster tool: { "action": "run", "pipeline": "workflows/srf_forum.yaml" }
  → Lobster begins phase execution (see Section 4)
  → Lobster returns resumeToken immediately; workflow runs asynchronously
```

### Flow C — Editorial Review Resume

Originates from Claude Desktop after reviewing synthesis and evaluation artifacts.

```
Claude Desktop
  → MCP call → OpenClaw skill: approve_editorial_review(resume_token, decision)
  → OpenClaw agent uses lobster tool: { "action": "resume", "token": "<resumeToken>", "approve": true }
  → Lobster resumes from editorial_review_gate step
  → Policy proposals and publication phases execute
```

---

## 4. Lobster Workflow — srf_forum.yaml

The Lobster workflow covers phases 4–15 of the SRF lifecycle. Phases 1–3 (newsletter parsing, candidate config, editorial approval) are pre-Lobster and handled by OpenClaw skills + Python scripts.

Lobster step fields: `id` (step name), `command` (shell command), `stdin` (reference to prior step output as `$stepId.json` or `$stepId.stdout`), `approval` (set to `required` to pause and return a resumeToken).

```yaml
name: srf_forum
version: "1.0"

steps:

  # ── Phase 4: Workspace Generation ──────────────────────────────────────────
  - id: workspace_setup
    command: python scripts/run_workspace_setup.py
    stdin: $trigger.json
    # Output: { forum_id, workspace_path, paper_refs, framing_question, topic, trace_id }

  # ── Phase 5: Paper Extraction ───────────────────────────────────────────────
  - id: paper_extraction
    command: python scripts/run_paper_extraction.py
    stdin: $workspace_setup.json
    # Output: { ...prev, papers: [{ arxiv_id, abstract, full_text, extraction_status }] }

  # ── Phase 6: Agent Preparation ──────────────────────────────────────────────
  - id: agent_preparation
    command: python scripts/run_preparation.py
    stdin: $paper_extraction.json
    # Output: { ...prev, agents: [{ agent_id, role, status, prep_artifact_path }] }

  # ── Phases 7–11: Debate ─────────────────────────────────────────────────────
  - id: debate
    command: python scripts/run_debate.py
    stdin: $agent_preparation.json
    # Output: { ...prev, transcript_path, turn_count, debate_status }

  # ── Phase 12: Synthesis ─────────────────────────────────────────────────────
  - id: synthesis
    command: python scripts/run_synthesis.py
    stdin: $debate.json
    # Output: { ...prev, synthesis_path }

  # ── Phase 13: Contribution Evaluation ──────────────────────────────────────
  - id: evaluation
    command: python scripts/run_evaluation.py
    stdin: $synthesis.json
    # Output: { ...prev, evaluation_path, evaluation_block }

  # ── Human Gate: Editorial Review ────────────────────────────────────────────
  # Lobster pauses here and returns a resumeToken.
  # Resumed by the approve_editorial_review skill via lobster { "action": "resume", ... }.
  - id: editorial_review_gate
    approval: required

  # ── Phase 14: Policy Proposals ──────────────────────────────────────────────
  - id: policy_proposals
    command: python scripts/run_policy_proposals.py
    stdin: $editorial_review_gate.json
    # Output: { ...prev, policy_proposal_path }

  # ── Phase 15: Publication ────────────────────────────────────────────────────
  - id: publication
    command: python scripts/run_publication.py
    stdin: $policy_proposals.json
    # Output: { ...prev, published_artifact_paths, forum_status: "complete" }
```

### State passing between steps

Every script reads its input from `stdin` (the JSON output of the previous step) and writes its full output to `stdout`. Lobster passes these as `$stepId.json` references. The complete workflow state — `forum_id`, `workspace_path`, `trace_id`, all span IDs — travels through every step in this chain.

Each script also writes a checkpoint to `state.json` on the workspace volume before returning. If the container restarts mid-workflow, the state can be inspected and the workflow replayed from the last completed step.

---

## 5. The Debate Loop — scripts/run_debate.py

The debate loop runs as a single Lobster step (`id: debate`). The Python script `scripts/run_debate.py` implements the full agent orchestration loop directly — no nested OpenClaw invocation is required. Inside the loop, the Moderator drives turn routing by calling internal Python functions (not OpenClaw tools).

```
run_debate.py
  │
  ├── Moderator agent (orchestrator — drives routing via Python function calls)
  │     internal operations:
  │       enqueue_speaker(agent_id, instruction)  ← routes next turn
  │       read_transcript()                        ← reads full debate state
  │       read_guardrail_signals()                 ← reads Guardrail evaluations
  │       close_debate(reason)                     ← terminates loop
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
        CRITICAL signal: forces Moderator routing decision next
```

All agent LLM calls go through `tracker.execute()`. Tool calls made by the Moderator (enqueue_speaker, read_transcript, etc.) are logged with `tracker.log_tool_call()`.

### Hard limits (enforced by run_debate.py orchestrator, not the Moderator)

```
max_total_turns:     40     (configurable via forum config)
max_turns_per_agent: 10
max_rounds:          5
```

### Transcript immutability

Every turn written to `transcripts/` is append-only. If a CRITICAL Guardrail signal fires, the offending turn remains in the transcript with the alert attached as metadata. Nothing is deleted or modified.

---

## 6. HTTP Endpoints (OpenClaw Gateway)

OpenClaw provides all HTTP endpoints. SRF does not build a custom HTTP server.

```
GET  /health
     → 200 OK (provided by OpenClaw — always available)

GET  /setup
     → Web setup wizard (password: SETUP_PASSWORD)

GET  /openclaw
     → OpenClaw control UI

POST /hooks/wake
     → Body: { text: "event description" }
     → Enqueues a system event for the main OpenClaw session
     → Auth: Authorization: Bearer <OPENCLAW_GATEWAY_TOKEN>

POST /hooks/agent
     → Body: { message: "...", agentId: "..." }
     → Runs an isolated OpenClaw agent turn (used to trigger skills programmatically)
     → Auth: Authorization: Bearer <OPENCLAW_GATEWAY_TOKEN>

MCP  /mcp  (HTTP MCP transport — Claude Desktop connects here)
     → Exposes SRF skills as MCP tools: trigger_newsletter_forum,
       review_forum_debate_format, approve_editorial_review
     → Auth: OPENCLAW_GATEWAY_TOKEN
```

Claude Desktop connects to the Railway service URL at `/mcp` using the HTTP MCP transport.

---

## 7. MCP Tools → OpenClaw Skills

SRF capabilities exposed to Claude Desktop are defined as **OpenClaw Skills** — `SKILL.md` directories placed in `~/.openclaw/workspace/skills/` (mapped to `/data/.openclaw/workspace/skills/` on Railway). Skills are natural language instruction files that tell the OpenClaw agent how to use exec + lobster tools to accomplish SRF tasks.

| Skill | Trigger | Python script invoked |
|---|---|---|
| `trigger_newsletter_forum` | Newsletter published | `scripts/trigger_newsletter_forum.py` via exec tool |
| `review_forum_debate_format` | Human approves candidate config | `scripts/validate_and_stage_forum.py` via exec + lobster run |
| `approve_editorial_review` | Human approves post-synthesis review | lobster resume action |

All three skills require `OPENCLAW_GATEWAY_TOKEN` authentication on the MCP endpoint.

---

## 8. Data Boundaries

| Data | Location | Lifetime | Owner |
|---|---|---|---|
| OpenClaw sessions and routing state | `/data/.openclaw/` | Process lifetime + persistent | OpenClaw |
| PromptLedger tracker client | In-process (Python scripts) | Duration of one script execution | SRF |
| Lobster workflow resumeTokens | `/data/workspace/forum/{id}/state.json` | Until workflow completes | SRF |
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

Retry up to `SRF_MAX_PREP_RETRIES`. If all retries exhausted, abort the workflow and write error state. Do not proceed to editorial review with a degraded synthesis.

### PromptLedger failure

Never blocks the pipeline. All `tracker.execute()` failures propagate (they are LLM call failures, not observability failures). All `log_span()` and `log_tool_call()` failures are swallowed — a PromptLedger outage produces incomplete traces, not a failed forum run.

### LLM provider failure

Retry with exponential backoff up to 3 attempts. After 3 failures, abort the current step and write error state.

---

## 10. PromptLedger Trace Hierarchy

Three span-creation mechanisms are used:

| Mechanism | When to use | Span kind |
|---|---|---|
| `tracker.execute()` | Every LLM call — creates span automatically, returns `result.span_id`, writes `state["last_span_id"]` | `llm.generation` |
| `tracker.log_span()` | Non-LLM spans: workflow phase boundaries, guardrail evaluations | `workflow.phase`, `guardrail.check` |
| `tracker.log_tool_call()` | Moderator internal tool calls during debate | `tool` |

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
  │     │     ├── {tool_name}               log_tool_call() — Moderator internal tools
  │     │     └── guardrail.{turn_id}       log_span(kind=guardrail.check) — child of turn
  │     └── ...
  │
  ├── synthesis                             execute() auto-creates span — Epic 7
  ├── evaluation                            execute() auto-creates span — Epic 7
  └── publication                           execute() auto-creates span — Epic 8
```

Span IDs travel through the Lobster step state dict (`state["trace_id"]`, `state["phase_span_id"]`, `state["last_span_id"]`), passed via stdin/stdout JSON between steps.

---

## 11. What Each Epic Builds in This Topology

| Epic | What it adds |
|---|---|
| 1 | SRFConfig, structlog, PromptLedger tracker, span utilities, prompt validation CI |
| 1.1 | OpenClaw installation + config, Lobster install + allowlist, `scripts/srf_init.py`, OpenClaw skills (MCP tools), Railway deployment |
| 3 | `trigger_newsletter_forum` Python pipeline scripts, Epic 3 skill wired |
| 4 | `run_workspace_setup.py`, `run_paper_extraction.py`, `srf_forum.yaml` skeleton |
| 5 | `run_preparation.py` (parallel asyncio), preparation agent prompts |
| 6 | `run_debate.py`, Moderator + Paper Agent + Challenger + Guardrail, transcript model |
| 7 | `run_synthesis.py`, `run_evaluation.py`, evaluation_block schema |
| 8 | `run_policy_proposals.py`, `run_publication.py`, `approve_editorial_review` skill, editorial_review_gate resume |
| 9 | Observability dashboards, cost reporting, drift detection hooks |
| 2 | Memory store, candidate extraction from evaluation_block, injection into preparation |
| 10 | Prompt governance reporting, longitudinal quality tracking |
