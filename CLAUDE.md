# CLAUDE.md — Synthetic Research Forum (SRF)

This file governs how Claude Code assists in this repository. Read it fully before touching any code.

---

## 1. Project Identity

**Synthetic Research Forum (SRF)** is a deterministic multi-agent epistemic discussion system that pressure-tests research papers, surfaces intellectual tensions, and generates structured synthesis artifacts.

It is not a conversational playground. It is an **intellectual execution engine.**

Stack:
- **OpenClaw Gateway** — agent runtime
- **Lobster Workflow Engine** — phase orchestration
- **PromptLedger** — prompt registry, trace/span lineage, token/cost telemetry (Mode 2 — Code-Based Tracking)
- **Railway** — deployment substrate
- **Language:** Python 3.11+
- **LLM provider:** Runtime configuration — `SRF_LLM_PROVIDER` / `SRF_LLM_MODEL` / `SRF_LLM_API_KEY`. No provider is hardcoded. Provider clients live in `src/srf/llm/` and are instantiated at startup based on config.

Key spec documents:
- `Requirements/srf_v_2_full_technical_specification.md` — canonical architecture reference
- `Requirements/srf_runtime_topology.md` — authoritative runtime topology: Railway service, Lobster workflow, OpenClaw debate loop, MCP tools, partial failure policy
- `Requirements/INTEGRATION_GUIDE.md` — PromptLedger Mode 2 integration patterns
- `Requirements/EPIC_TEMPLATE.md` — epic, story, bug, and tech debt standards
- `Requirements/Railway/` — Railway deployment reference PDFs

---

## 2. TDD — HARD RULE, NO EXCEPTIONS

Every piece of production code in this repository is written test-first. There are no exceptions.

```
1. Write the failing test first
2. Run it — confirm RED (import error or assertion failure both count)
3. Write the minimum implementation to pass
4. Run again — confirm GREEN
5. Refactor, then commit
```

**What this means in practice:**

- Do not write a function, class, or module until its test file exists and fails.
- Do not move to the next story until all tests for the current story are GREEN.
- Skipped tests (`@pytest.mark.skip`) are not acceptable as a workaround for broken implementations. Fix the code.
- Each Gherkin scenario in a story's Acceptance Criteria maps 1:1 to one `pytest` test function. Write those tests before the implementation.
- PromptLedger-dependent code must be testable without a live PromptLedger instance. Use `tracker=None` injection. Never mock the LLM provider client in integration tests — use `pytest-recording` or a real sandbox call.

Test locations:
```
tests/
  unit/           — pure logic, no I/O, no network, tracker=None
  integration/    — hits real external services (Railway, PromptLedger, configured LLM provider)
  fixtures/       — shared pytest fixtures, factory helpers
```

Run tests:
```bash
pytest tests/unit -v                    # fast, offline
pytest tests/integration -v --timeout=60  # requires live env vars
```

---

## 3. Epics, Stories, Bugs, and Tech Debt

All planning artifacts live in `requirements/` and follow `Requirements/EPIC_TEMPLATE.md` exactly. Read that file before creating any planning document.

### Epic files

**Filename:** `requirements/srf_epic_{NN}_{slug}.md`

Required sections in order:
```
Prerequisites → Context → What We Gain → Architecture Decisions (omit if none)
→ Stories → Implementation Order → Verification Checklist → Critical Files
```

Check existing epic files for the next unused epic number before creating a new one.

### Stories

Stories live inside their parent epic file. Every story requires:
- User story sentence: "As a `{role}`, I would like `{capability}`, so that `{benefit}`."
- `Files:` block — distinguish `NEW:` from `MODIFY:`
- `Acceptance Criteria:` — Gherkin scenarios only

Standard roles: `researcher`, `system`, `developer`, `MCP server`

Slicing rules:
- A story that touches >5 files is probably two stories.
- A story with >8 Gherkin scenarios is probably two stories.

### Bug documents

**Filename:** `requirements/bugs/BUG-{NN}-{slug}.md`

Required sections: `Symptom → Root Cause → Impact → Fix Required → Risks → TDD Plan → Files to Change`

Root cause labels: `PRIMARY`, `SECONDARY`, `CONTRIBUTING`. Each must include file + line + code snippet.

Update `**Fixed in commit:**` when resolved.

### Tech debt

**File:** `requirements/tech_debt_tracker.md` (single file, append at bottom — oldest first)

Add an entry when you hardcode something, skip an edge case, or leave a `# TODO` / `# FIXME`. Do not add entries for bugs or future features.

---

## 4. Progress Tracking

Track all in-flight work in `requirements/progress_summary.md`. This file is the authoritative record of what is done, in progress, and blocked.

### Format

```markdown
# SRF Progress

## Active Sprint

| Story | Title | Status | Notes |
|---|---|---|---|
| 1.1 | ... | In Progress | ... |
| 1.2 | ... | Blocked | Waiting on X |

## Completed

| Story | Title | Completed |
|---|---|---|
| 0.1 | ... | 2026-03-17 |

## Blocked / Deferred

| Story | Reason | Unblocked by |
|---|---|---|
```

### Status values

| Status | Meaning |
|---|---|
| `Not Started` | Not yet begun |
| `In Progress` | Active development |
| `Tests Written` | Tests exist, RED — implementation pending |
| `GREEN` | All tests pass, ready for review |
| `Blocked` | Cannot proceed — record reason |
| `Complete` | Merged, verified |

Update `progress.md` when status changes. Do not let it go stale.

### Definition of Complete — HARD RULE

A story is **never** marked `Complete` unless ALL of the following are true:

1. Every file listed in the story's `Files:` block exists in the repository.
2. Every Gherkin scenario in the story's `Acceptance Criteria` has a corresponding passing `pytest` test.
3. `pytest tests/unit -v` has been run in this conversation and the output confirms GREEN for that story's tests.
4. No story file is a stub, placeholder, or `echo` command standing in for real implementation.

**Before moving a story to `## Completed` in `progress_summary.md`**, explicitly verify each point above. If any file is missing or any test is absent, the story stays at `GREEN` or `Tests Written` — not `Complete`.

This rule exists because stories have been incorrectly closed (e.g. Story 1.1.5 — `.github/workflows/ci.yml` was never created but the story was marked Complete on 2026-03-19).

**CRITICAL:** After every commit, also update `requirements/progress_tracker.md` (newest
entries first) to reflect the detailed changes. Also review `README.md` and update it to reflect the current state.

**Entry template:**
```markdown
## [YYYY-MM-DD] - [Title]

### Summary
- Reference Epic and Story numbers where approporiate, Files changed, tests written, coverage %

### Decisions
- Technical choices + rationale, alternatives rejected

### Issues & Resolution
- Problems encountered, error messages, how fixed

### Lessons Learned
- Key insights, what worked/didn't work

### Next Steps
- [ ] Actionable tasks
```

---

## 5. Log File Storage

### Local development

```
logs/
  srf.log              — structured application log (JSON lines)
  workflow.log         — Lobster phase execution events
  promptledger.log     — PromptLedger span submission (errors only)
```

Logs rotate at 10 MB, keep 5 files. Never commit log files.

### Production (Railway)

Runtime logs go to Railway's built-in log aggregation (stdout/stderr). Structured JSON lines only — no ANSI, no unstructured print statements.

Debate artifacts are persisted to the workspace volume:
```
/data/workspace/forum/{forum_id}/
  preparation/          — agent preparation artifacts
  transcripts/          — turn-by-turn transcript (JSON)
  synthesis/            — synthesis and evaluation outputs
  logs/                 — forum-scoped execution log
```

### Log format

All application logs must be structured JSON with at minimum:
```json
{
  "timestamp": "2026-03-17T10:00:00Z",
  "level": "INFO",
  "component": "lobster.phase",
  "forum_id": "...",
  "message": "..."
}
```

Use `structlog` for all logging. Do not use `print()` in production code paths.

---

## 6. PromptLedger Integration Rules

SRF uses **Mode 2 (Code-Based Tracking)**. Prompts are defined in code (Git); PromptLedger executes all LLM calls and logs spans automatically via `tracker.execute()`.

### Primary call pattern — `tracker.execute()`

Every LLM call uses `tracker.execute()`. PromptLedger makes the provider call, creates the span, and writes `state["last_span_id"]` automatically:

```python
if tracker is not None:
    result = await tracker.execute(
        prompt_name="agent.paper_preparation",   # links to registered prompt
        messages=[...],                           # caller constructs messages (Mode 2)
        mode="mode2",
        state=state,        # reads trace_id/phase_span_id; writes last_span_id
        agent_id="paper-agent-1",
        max_tokens=1024,
    )
    return result.response_text
# tracker=None fallback: call provider directly (unit tests, local dev without PL)
return await call_provider_directly(messages, config)
```

### `log_span()` — non-LLM spans only

Use `tracker.log_span(SpanPayload(...))` **only** for spans that have no LLM call: workflow phase spans and guardrail child spans. Never use `log_span()` for LLM generation — use `execute()` instead.

```python
# Phase span (no LLM call)
state["phase_span_id"] = await tracker.log_span(SpanPayload(
    trace_id=state["trace_id"], name="open_discussion", kind="workflow.phase", status="ok",
))

# Guardrail child span (no LLM call — parented under the turn span)
await tracker.log_span(SpanPayload(
    trace_id=state["trace_id"], parent_span_id=state["last_span_id"],
    name="guardrail_check", kind="guardrail.check", status="ok",
))
```

### `log_tool_call()` — OpenClaw tool calls

Every tool call made by an agent during the debate loop (e.g. `enqueue_speaker`, `read_transcript`) must be logged with `tracker.log_tool_call()` using `state["last_span_id"]` as the parent:

```python
await tracker.log_tool_call(
    trace_id=state["trace_id"],
    tool_name="moderator.enqueue_speaker",
    tool_args={"agent_id": "paper-agent-2"},
    tool_result={"queued": True},
    success=True,
    duration_ms=12,
    parent_span_id=state["last_span_id"],
    agent_id="moderator",
)
```

### Rules

- All prompts are defined as Python constants in `src/srf/prompts/` and registered at startup via `register_code_prompts()`.
- Tracker is injected — never imported as a global singleton inside agent functions.
- Graceful degradation is mandatory: if `PROMPTLEDGER_API_URL` is absent, `tracker=None` and the system runs without observability using the direct provider fallback. It does not crash.
- `tracker=None` in all unit tests. Mock `tracker.execute()` — do not mock provider SDKs.
- `tracker.execute()` failures propagate — they represent LLM call failures, not observability failures. Only `log_span()` and `log_tool_call()` are fire-and-forget with 5xx resilience.
- Span IDs travel through `state["trace_id"]` and `state["last_span_id"]` — never through `contextvars` across Lobster step boundaries.
- `PROMPTLEDGER_API_KEY` must be a project-scoped key issued via `POST /v1/admin/projects`, not the PromptLedger admin key.

PromptLedger trace hierarchy:
```
trace (forum_id)
  phase spans          (workflow.phase)    ← log_span()
    turn spans         (llm.generation)   ← execute() — automatic
      tool call spans  (tool.call)        ← log_tool_call()
      guardrail spans  (guardrail.check)  ← log_span()
```

---

## 7. Agent and Prompt Governance

- Prompts never change autonomously. Every prompt edit goes through a pull request.
- Prompt changes that alter agent behaviour require a new epic story describing the change and its evaluation criteria.
- The CI pipeline runs `scripts/validate_prompts.py --dry-run` to assert no unregistered prompt changes have reached the branch. This check must pass before merge.
- Evaluation scores from the Evaluation Agent are provisional. Editorial review is required before any score drives a policy change.

---

## 8. Debate State — Immutability Rule

The debate transcript is append-only. Once a turn is written to the transcript, it is never modified. If a guardrail CRITICAL alert fires, the routing is overridden but the offending turn remains in the transcript with the alert attached as metadata.

---

## 9. Railway Deployment Rules

- SRF deploys via the **OpenClaw Gateway Railway template** (one-click deploy). OpenClaw is Node.js and provides the HTTP server, MCP transport, and agent runtime. SRF Python code runs as Lobster step scripts invoked by the exec tool.
- All config is environment variables. No secrets in code or committed `.env` files.
- The system must survive Railway sleep/wake cycles. Workspace state is on the persistent volume at `/data/workspace`. In-memory state is rebuilt from the workspace on wake.
- `scripts/srf_init.py` runs PromptLedger prompt registration + workspace directory init on startup. It is invoked via OpenClaw's exec tool before the first agent turn.
- Health check endpoint: `GET /health` — served by OpenClaw, must respond within 500 ms.

SRF Python script environment variables (set via Railway Variables):
```
SRF_LLM_PROVIDER           # e.g. anthropic, openai — tracker=None fallback only
SRF_LLM_MODEL              # e.g. claude-sonnet-4-6, gpt-4o
SRF_LLM_API_KEY            # provider key for tracker=None fallback only
PROMPTLEDGER_API_URL        # PromptLedger instance URL (optional)
PROMPTLEDGER_API_KEY        # project-scoped key — issue via POST /v1/admin/projects
SRF_LOG_LEVEL              # defaults to INFO
SRF_MAX_PREP_RETRIES       # retry attempts for failed agent preparation (default 3)
SRF_MIN_AGENTS             # minimum viable Paper Agents for debate (default 2)
SRF_MIN_PAPERS             # minimum successfully extracted papers (default 2)
SRF_ARXIV_DELAY_SECONDS    # rate-limit delay between arXiv fetches (default 3)
SRF_DEBATE_CONTEXT_TOKENS  # max chars of transcript context in agent prompts (default 60000)
```

OpenClaw Gateway variables (set via Railway Variables or /setup wizard):
```
SETUP_PASSWORD             # required — secures /setup web wizard
PORT=8080                  # required — must match Railway Public Networking port
OPENCLAW_STATE_DIR=/data/.openclaw      # recommended
OPENCLAW_WORKSPACE_DIR=/data/workspace  # recommended — SRF workspace root
OPENCLAW_GATEWAY_TOKEN     # recommended — secures MCP + webhook endpoints
```

Note: `SRF_WORKSPACE_ROOT` is not used. The workspace root is `OPENCLAW_WORKSPACE_DIR` (defaults to `/data/workspace`). SRF Python scripts read it from `os.environ.get("OPENCLAW_WORKSPACE_DIR", "/data/workspace")`. When `PROMPTLEDGER_API_URL` and `PROMPTLEDGER_API_KEY` are set, all LLM calls route through PromptLedger via `tracker.execute()`. `SRF_LLM_API_KEY` is only used in the `tracker=None` fallback path.

---

## 10. Code Style and Quality

- Python 3.11+. Type annotations on all function signatures.
- `async`/`await` throughout — no blocking I/O in the event loop.
- `ruff` for linting and formatting. Configuration in `pyproject.toml`.
- No `print()` statements in production paths — use `structlog`.
- No bare `except:` clauses. Catch specific exceptions.
- `if tracker is not None:` guards every PromptLedger call. Do not inline tracker availability checks any other way.
- Keep functions short. If a function needs more than one screenful to read, it should be split.

---

## 11. Skill Document Requirements

Every OpenClaw skill document (`SKILL.md`) in this repository must specify its error behaviour explicitly. This is not optional boilerplate — it is a hard governance requirement discovered from a production incident.

**The incident:** `trigger_newsletter_forum` called `parse_newsletter.py` via the exec tool. The script failed. The skill had no instruction for that case. The agent filled the silence by diagnosing the failure and directly editing `parse_newsletter.py` — a git-tracked source file — to add a workaround. The pipeline then ran. On the next redeploy, `git pull --ff-only` failed because the working tree was dirty. The repo was no longer the source of truth for what was running in production.

**The principle:** Any unspecified failure state in a skill document is an implicit grant of agent agency. A capable LLM with filesystem and exec tools will not sit idle when a step fails and it has not been told to stop.

### Required elements in every SRF skill document

**1. Error handling instructions for every exec tool call.**

Every skill that calls a script via exec must include:

> If the script exits with a non-zero code, report the full stderr output to the researcher verbatim and stop. Do not read other files to diagnose the cause. Do not edit any files. Do not retry.

Authorisation to investigate or fix must be explicitly stated. For SRF skills, it is never authorised.

**2. An explicit `/data/srf/` constraint.**

Every skill must include:

> This skill must never edit any file under `/data/srf/`. That directory is a git-tracked deployment clone. Editing it in response to errors bypasses version control and bypasses code review. All source-level fixes must be made in the repository by the developer and redeployed.

**3. Specified behaviour for every non-happy-path state.**

Do not write skills that only specify what to do when things work. For each step that can fail, the skill must answer: what does the agent do if this step produces an error or unexpected output?

The answer for SRF skills is almost always "report and stop." If the answer is anything else, it must be written down.

---

## 12. What Claude Should Never Do

- Do not write production code before its tests exist and fail.
- Do not modify a prompt template without also updating its registration payload and `validate_prompts.py`.
- Do not push directly to `main`. All changes go through a pull request.
- Do not skip the `EPIC_TEMPLATE.md` structure when creating planning documents.
- Do not add observability infrastructure calls outside the `if tracker is not None:` pattern.
- Do not use `tracker.log_span()` for LLM generation calls — use `tracker.execute()` instead.
- Do not call provider SDKs (anthropic, openai) directly in production paths when `tracker is not None` — route through `tracker.execute()`.
- Do not introduce blocking I/O (file reads, network calls) outside of explicitly async contexts.
- Do not store secrets in code, comments, or committed configuration files.
- Do not create `requirements/progress.md` entries without also updating the corresponding epic story's status.
- Do not mock provider SDKs in unit tests — mock `tracker.execute()` instead.
- Do not write a skill document that only specifies the happy path. Every skill must specify error handling for every exec call and every non-happy-path state.
