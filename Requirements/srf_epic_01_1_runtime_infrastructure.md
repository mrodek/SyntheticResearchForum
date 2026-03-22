# Epic 1.1: Runtime Infrastructure — OpenClaw Configuration, Lobster, Skills & Railway Deployment

## Prerequisites

- Epic 1 (Foundation) — complete. `SRFConfig`, `build_tracker`, `configure_logging`,
  `register_prompts()` are all called by `scripts/srf_init.py` (Story 1.1.2).

---

## Context

Epic 1 built the internal Python plumbing — config, logging, PromptLedger integration. But
nothing addressed how the system actually runs. OpenClaw Gateway IS the HTTP server, MCP
transport, and agent runtime; SRF does not build any of those. What SRF must build is:

- An initialisation script that registers prompts and initialises the workspace on startup
- OpenClaw Skills that expose SRF capabilities as MCP tools for Claude Desktop
- Lobster workflow configuration (correct field names, `alsoAllow` enablement)
- A Python script to validate and stage an approved forum config before Lobster fires
- Railway deployment configuration

OpenClaw is deployed via its **Railway one-click template** (Node.js, npm-based). Lobster is
a separate CLI installed on the same host. SRF Python code runs as Lobster step scripts invoked
via OpenClaw's exec tool.

**Architecture resolved:**
- OpenClaw provides: HTTP server (port 8080), `GET /health`, `POST /hooks/wake`,
  `POST /hooks/agent`, `/setup` wizard, `/openclaw` control UI, MCP transport at `/mcp`
- SRF does not build a custom HTTP server. No FastAPI.
- MCP tools are OpenClaw **Skills** (`SKILL.md` directories), not Python plugin classes.
- Auth token is `OPENCLAW_GATEWAY_TOKEN` (not `SRF_GATEWAY_TOKEN` — that name is retired).
- Workspace root is `OPENCLAW_WORKSPACE_DIR` (not `SRF_WORKSPACE_ROOT`).
- Lobster is invoked via the lobster tool in OpenClaw agent turns:
  `{ "action": "run", "pipeline": "workflows/srf_forum.yaml" }` and
  `{ "action": "resume", "token": "<resumeToken>", "approve": true }`.
- Lobster YAML fields: `id` (not `name`), `command` (not `run`), `approval: required`.

---

## What We Gain

| Gap (before) | After this epic |
|---|---|
| No gateway startup — PromptLedger registration never runs | `scripts/srf_init.py` registers prompts and initialises workspace directories |
| MCP tool functions unreachable from Claude Desktop | Three OpenClaw Skills expose trigger, review, and approve capabilities |
| Lobster not installed or enabled | `lobster` CLI installed; `alsoAllow: ["lobster"]` in OpenClaw config |
| `srf_forum.yaml` missing `id`/`command` field names | Corrected (done as part of Epic 4.4 fix) |
| No script to validate + stage an approved forum config | `scripts/validate_and_stage_forum.py` validates config, assigns forum_id, writes state |
| No Railway deployment — service cannot be created | Railway template deployed, env vars configured, volume mounted |
| No CI pipeline | GitHub Actions runs ruff + unit tests + validate_prompts on every push/PR |
| `.env.example` stale | All env vars from Epics 1–6 documented |

---

## Architecture Decisions

### OpenClaw Skills are natural language instruction files, not code

A Skill is a directory containing `SKILL.md` — YAML frontmatter + Markdown instructions that
tell the OpenClaw agent what to do when invoked. For SRF skills, the instructions tell the agent
to use the exec tool to run a Python script, or to use the lobster tool to run/resume a workflow.
The Python scripts do the actual logic; the skills are the routing layer.

```
skills/
  trigger_newsletter_forum/
    SKILL.md   ← instructs agent: exec python scripts/trigger_newsletter_forum.py
  review_forum_debate_format/
    SKILL.md   ← instructs agent: exec validate_and_stage_forum.py, then lobster run
  approve_editorial_review/
    SKILL.md   ← instructs agent: lobster resume with provided token
```

Skills are placed at `/data/.openclaw/workspace/skills/` (the path configured by
`OPENCLAW_STATE_DIR`). OpenClaw auto-discovers skills in that directory on startup.

### `scripts/srf_init.py` runs on first agent wake

OpenClaw does not have a Python startup hook. Instead, `srf_init.py` is listed in the skills
directory as a startup prerequisite: the trigger_newsletter_forum skill checks whether init has
run (by checking for a sentinel file) and runs it via exec if not. This is idempotent —
subsequent calls are no-ops. Alternatively, a dedicated `srf_startup` skill can be registered
and triggered via `POST /hooks/wake` immediately after deploy.

### `scripts/validate_and_stage_forum.py` is the pre-Lobster gate

The `review_forum_debate_format` skill calls this script before triggering the Lobster workflow.
It validates the CandidateForumConfig, assigns a `forum_id`, writes `state.json` with
`forum_status: "workspace_staged"`, and outputs the trigger JSON to stdout. The Lobster tool
then uses that output as the `$trigger.json` input to the workflow.

### Lobster must be installed on the OpenClaw host

The `lobster` CLI must be on PATH on the Railway container. This is done by adding a build step
to the OpenClaw Railway service that installs the lobster npm package globally:
`npm install -g @clawdbot/lobster`. Lobster is then enabled in OpenClaw
config via `tools.alsoAllow: ["lobster"]`.

### No custom webhook endpoints

OpenClaw provides `POST /hooks/wake` and `POST /hooks/agent` for programmatic triggering. SRF
does not build additional HTTP endpoints. The `approve_editorial_review` skill resumes Lobster
workflows entirely through the lobster tool — no POST /webhook/resume endpoint is needed.

---

## Stories

---

### Story 1.1.1 — OpenClaw & Lobster Installation + Base Configuration

**As a** developer,
**I would like** OpenClaw Gateway deployed on Railway with Lobster installed and enabled,
**so that** the SRF service is reachable, `GET /health` passes, and Lobster workflows can be
executed by OpenClaw agent turns.

**Files:**
- NEW: `railway.toml`
- NEW: `openclaw.config.json` _(or equivalent OpenClaw config file — confirm filename)_
- NEW: `tests/unit/test_runtime_deps.py`

**Acceptance Criteria:**

```gherkin
Scenario: GET /health returns 200 after Railway deploy
  Given the OpenClaw service is deployed on Railway via the one-click template
  When  GET /health is called
  Then  the response status is 200

Scenario: lobster CLI is available on PATH in the deployed container
  Given the Railway service is running
  When  "lobster --version" is run via POST /hooks/agent exec
  Then  it exits with code 0 and returns a version string

Scenario: lobster is listed in OpenClaw alsoAllow config
  Given openclaw.config.json (or equivalent)
  When  it is parsed
  Then  tools.alsoAllow contains "lobster"

Scenario: python is allowed in the exec tool safe bins
  Given openclaw.config.json
  When  it is parsed
  Then  the exec tool allowlist permits the python binary

Scenario: railway.toml declares port 8080, volume /data, and required env var keys
  Given railway.toml
  When  it is parsed
  Then  it declares port 8080
  And   it declares a volume mounted at /data
  And   it documents SETUP_PASSWORD, PORT, OPENCLAW_STATE_DIR,
        OPENCLAW_WORKSPACE_DIR, and OPENCLAW_GATEWAY_TOKEN

Scenario: unit test confirms lobster resolvable in local environment
  Given the development environment
  When  test_runtime_deps.py runs
  Then  shutil.which("lobster") is not None
  And   shutil.which("python") is not None
```

**TDD Notes:** The Railway and `GET /health` scenarios are deployment verification, not automated
unit tests — they are acceptance checks run manually after deploy. The `shutil.which` test is
the only automated unit test here. The `openclaw.config.json` and `railway.toml` structure tests
are lightweight JSON/TOML parse assertions.

---

### Story 1.1.2 — SRF Initialisation Script

**As a** system,
**I would like** a Python initialisation script that registers PromptLedger prompts and
initialises workspace directories on gateway startup,
**so that** all LLM calls are traceable from the first forum run and the workspace structure
exists before any Lobster step tries to write to it.

**Files:**
- NEW: `scripts/srf_init.py`
- NEW: `tests/unit/test_srf_init.py`

**Acceptance Criteria:**

```gherkin
Scenario: srf_init.py exits 0 and logs INFO "SRF init complete" on success
  Given all required SRF env vars are set
  And   a writable OPENCLAW_WORKSPACE_DIR
  And   a mock tracker that accepts register_prompts
  When  srf_init.py is run
  Then  it exits with code 0
  And   an INFO log is emitted containing "SRF init complete"

Scenario: srf_init.py calls register_prompts with all registered prompts
  Given a mock build_tracker returning a mock tracker
  When  srf_init.py is run
  Then  register_prompts was called once with the full ALL_PROMPTS list

Scenario: srf_init.py creates workspace subdirectories if absent
  Given OPENCLAW_WORKSPACE_DIR points to an empty tmp directory
  When  srf_init.py is run
  Then  newsletters/, candidates/, forum/, and memory/ directories exist under workspace root

Scenario: srf_init.py is idempotent — running it twice does not raise
  Given workspace directories already exist
  When  srf_init.py is run a second time
  Then  it exits with code 0 without raising FileExistsError

Scenario: srf_init.py exits 1 and logs ERROR when SRF_LLM_PROVIDER is absent
  Given SRF_LLM_PROVIDER is not set in the environment
  When  srf_init.py is run
  Then  it exits with code 1
  And   an ERROR log is emitted naming the missing variable

Scenario: srf_init.py completes without error when PROMPTLEDGER_API_URL is absent
  Given PROMPTLEDGER_API_URL is not set
  When  srf_init.py is run
  Then  it exits with code 0
  And   a WARNING is logged indicating "PromptLedger not configured — observability disabled"

Scenario: srf_init.py continues if register_prompts raises due to PromptLedger unreachable
  Given PROMPTLEDGER_API_URL is set but the endpoint returns 503
  When  srf_init.py is run
  Then  it exits with code 0
  And   a WARNING is logged containing "prompt registration failed"
```

**TDD Notes:** Use `subprocess.run` with crafted env vars and `tmp_path` workspace roots for the
script-level tests. Mock `build_tracker` and `register_prompts` at import level in unit tests
to avoid network calls. The idempotency test pre-creates the directories, then calls the script.

---

### Story 1.1.3 — Forum Staging Script

**As a** system,
**I would like** a script that validates an approved `CandidateForumConfig`, assigns a
`forum_id`, and writes the trigger JSON that Lobster reads as `$trigger.json`,
**so that** the `review_forum_debate_format` skill has a pre-Lobster validation gate that
catches bad configs before the workflow starts.

**Files:**
- NEW: `scripts/validate_and_stage_forum.py`
- NEW: `tests/unit/test_validate_and_stage_forum.py`

**Acceptance Criteria:**

```gherkin
Scenario: script exits 0 and writes trigger JSON to stdout for a valid config
  Given a valid CandidateForumConfig JSON file at the provided path
  And   a writable OPENCLAW_WORKSPACE_DIR
  When  validate_and_stage_forum.py --config-path /path/to/config.json is run
  Then  it exits with code 0
  And   stdout is valid JSON containing forum_id, workspace_path, and trace_id
  And   state.json exists at workspace_path/state.json with forum_status="workspace_staged"

Scenario: script exits 1 with a clear error when config file is not found
  Given --config-path points to a file that does not exist
  When  validate_and_stage_forum.py is run
  Then  it exits with code 1
  And   stderr contains "config file not found"

Scenario: script exits 1 when config JSON is malformed
  Given --config-path points to a file containing invalid JSON
  When  validate_and_stage_forum.py is run
  Then  it exits with code 1
  And   stderr contains "invalid config"

Scenario: script exits 1 when config has no paper_refs
  Given a CandidateForumConfig with an empty paper_refs list
  When  validate_and_stage_forum.py is run
  Then  it exits with code 1
  And   stderr contains "no papers"

Scenario: assigned forum_id matches the pattern forum-YYYYMMDD-{8 hex chars}
  Given a valid config
  When  validate_and_stage_forum.py is run
  Then  the forum_id in stdout JSON matches "forum-\\d{8}-[0-9a-f]{8}"

Scenario: script writes trace_id to stdout JSON for PromptLedger tracing
  Given a valid config
  When  validate_and_stage_forum.py is run
  Then  stdout JSON contains a non-empty trace_id string
```

**TDD Notes:** Unit tests use `subprocess.run` with `tmp_path` workspace. The `forum_id`
pattern test uses `re.match`. The `trace_id` is a UUID4 generated by the script — no
PromptLedger call needed at this stage; tracing begins from the first Lobster step.

---

### Story 1.1.4 — OpenClaw Skills (MCP Tools)

**As a** developer,
**I would like** three OpenClaw Skills that expose SRF capabilities as MCP tools for Claude
Desktop,
**so that** a researcher can trigger newsletter processing, approve a forum config, and
approve editorial review entirely from Claude Desktop.

**Files:**
- NEW: `skills/trigger_newsletter_forum/SKILL.md`
- NEW: `skills/review_forum_debate_format/SKILL.md`
- NEW: `skills/approve_editorial_review/SKILL.md`
- NEW: `tests/unit/test_skills.py`

**Acceptance Criteria:**

```gherkin
Scenario: trigger_newsletter_forum/SKILL.md has valid frontmatter with name and description
  Given skills/trigger_newsletter_forum/SKILL.md
  When  its YAML frontmatter is parsed
  Then  it contains a non-empty "name" field equal to "trigger_newsletter_forum"
  And   it contains a non-empty "description" field

Scenario: trigger_newsletter_forum skill instructs the agent to run the newsletter pipeline
  Given skills/trigger_newsletter_forum/SKILL.md
  When  its Markdown body is read
  Then  it references "scripts/trigger_newsletter_forum.py" or equivalent exec command
  And   it references the source_path parameter

Scenario: review_forum_debate_format/SKILL.md instructs agent to stage config then run Lobster
  Given skills/review_forum_debate_format/SKILL.md
  When  its Markdown body is read
  Then  it references "scripts/validate_and_stage_forum.py"
  And   it references running the srf_forum Lobster workflow

Scenario: approve_editorial_review/SKILL.md instructs agent to resume a Lobster workflow
  Given skills/approve_editorial_review/SKILL.md
  When  its Markdown body is read
  Then  it references the lobster resume action
  And   it references the resume_token parameter

Scenario: all three skills have distinct names and non-empty descriptions
  Given the three SKILL.md files
  When  each is parsed
  Then  each has a unique "name" value
  And   each has a "description" with at least 10 characters
```

**TDD Notes:** These tests are pure file-read assertions — no OpenClaw runtime needed. Parse
the YAML frontmatter with `yaml.safe_load` on the front-matter block. Assert key body phrases
as string contains checks. The skills are the authoritative source for how Claude Desktop
triggers SRF — they must match the Python scripts they reference.

---

### Story 1.1.5 — CI Pipeline & Railway Auto-Deploy

**As a** developer,
**I would like** a GitHub Actions CI workflow that validates every push and automatically
deploys to Railway when tests pass on `main`,
**so that** every SRF code change is tested before it reaches Railway and no manual
redeploy is needed.

**Files:**
- NEW: `.github/workflows/ci.yml`
- NEW: `tests/unit/test_ci_workflow.py`
- MODIFY: `.env.example`  _(add all vars from Epics 1–6)_

**Acceptance Criteria:**

```gherkin
Scenario: CI workflow runs on every push and pull request to main
  Given .github/workflows/ci.yml
  When  it is parsed as YAML
  Then  the trigger includes both push and pull_request targeting main

Scenario: CI runs ruff before pytest
  Given .github/workflows/ci.yml
  When  it is parsed
  Then  it contains a step running "ruff check src/ tests/ scripts/ skills/"
  And   it contains a step running "pytest tests/unit -v --tb=short"
  And   the ruff step precedes the pytest step

Scenario: CI runs validate_prompts.py on every push
  Given .github/workflows/ci.yml
  When  it is parsed
  Then  it contains a step running "python scripts/validate_prompts.py --dry-run"
  And   the step uses continue-on-error: false

Scenario: CI triggers Railway redeploy on push to main after tests pass
  Given .github/workflows/ci.yml
  When  it is parsed
  Then  it contains a step that POSTs to the Railway deploy hook URL
  And   that step only runs on push to main (not on pull_request)
  And   that step runs after pytest passes
  And   the deploy hook URL is read from secrets.RAILWAY_DEPLOY_HOOK

Scenario: .env.example contains all required SRF Python script variables
  Given .env.example
  When  it is read
  Then  it contains placeholder entries for:
        SRF_LLM_PROVIDER, SRF_LLM_MODEL, SRF_LLM_API_KEY,
        PROMPTLEDGER_API_URL, PROMPTLEDGER_API_KEY,
        SRF_LOG_LEVEL, SRF_MAX_PREP_RETRIES, SRF_MIN_AGENTS,
        SRF_MIN_PAPERS, SRF_ARXIV_DELAY_SECONDS, SRF_DEBATE_CONTEXT_TOKENS

Scenario: .env.example contains all required OpenClaw Gateway variables
  Given .env.example
  When  it is read
  Then  it contains placeholder entries for:
        SETUP_PASSWORD, PORT, OPENCLAW_STATE_DIR,
        OPENCLAW_WORKSPACE_DIR, OPENCLAW_GATEWAY_TOKEN

Scenario: CI workflow uses continue-on-error: false for all steps
  Given .github/workflows/ci.yml
  When  it is parsed
  Then  no step uses continue-on-error: true
```

**TDD Notes:** All tests are pure YAML/file parse assertions — no CI execution required. The
`.env.example` test iterates the expected variable names and asserts each appears as a line
in the file. The workflow YAML test uses `yaml.safe_load` to navigate the steps list.

**Railway setup required before this story is complete:**
- Service → Settings → Deploy → Deploy Trigger → copy the webhook URL
- Add as `RAILWAY_DEPLOY_HOOK` secret in the SRF GitHub repo (Settings → Secrets → Actions)
- Enable "Wait for CI" in Railway → service → Settings → Source

---

## Implementation Order

```
Story 1.1.1 (deploy OpenClaw + install Lobster — makes the service reachable)
  → Story 1.1.2 (srf_init.py — PromptLedger registration + workspace init)
    → Story 1.1.3 (validate_and_stage_forum.py — pre-Lobster staging gate)
      → Story 1.1.4 (Skills — MCP tool surface for Claude Desktop)
        → Story 1.1.5 (CI + deployment docs — wraps everything)
```

All stories are sequential.

---

## Verification Checklist

```bash
# After 1.1.1
lobster --version
# Deploy to Railway and verify:
# curl https://<railway-domain>/health → {"status": "ok"}

# After 1.1.2
pytest tests/unit/test_srf_init.py -v
python scripts/srf_init.py  # expect: INFO "SRF init complete", exit 0

# After 1.1.3
pytest tests/unit/test_validate_and_stage_forum.py -v

# After 1.1.4
pytest tests/unit/test_skills.py -v
# In Claude Desktop: connect to Railway URL at /mcp
# → tools list should include trigger_newsletter_forum, review_forum_debate_format, approve_editorial_review

# After 1.1.5
python -c "import yaml; ci = yaml.safe_load(open('.github/workflows/ci.yml')); print('CI ok')"

# Full epic suite
pytest tests/unit -v --tb=short
ruff check src/ tests/ scripts/ skills/
```

---

## Critical Files

**NEW:**
- `railway.toml`
- `openclaw.config.json`  _(OpenClaw configuration — alsoAllow lobster, exec allowlist)_
- `scripts/srf_init.py`
- `scripts/validate_and_stage_forum.py`
- `skills/trigger_newsletter_forum/SKILL.md`
- `skills/review_forum_debate_format/SKILL.md`
- `skills/approve_editorial_review/SKILL.md`
- `tests/unit/test_runtime_deps.py`
- `tests/unit/test_srf_init.py`
- `tests/unit/test_validate_and_stage_forum.py`
- `tests/unit/test_skills.py`
- `.github/workflows/ci.yml`

**MODIFY:**
- `.env.example`  _(add all missing vars from Epics 1–6)_
- `Requirements/progress_summary.md`
