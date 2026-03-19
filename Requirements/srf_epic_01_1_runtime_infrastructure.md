# Epic 1.1: Runtime Infrastructure — Gateway, Lobster, OpenClaw & Railway Deployment

## Prerequisites

- Epic 1 (Foundation) — complete. `SRFConfig`, `build_tracker`, `configure_logging`, prompt
  registration, and `register_prompts()` are all called by the gateway startup sequence.

---

## Context

Epic 1 built the internal plumbing — config, logging, PromptLedger integration. But nothing in
that epic, or in Epics 3 or 4, addresses how the system actually runs. There is no entrypoint,
no HTTP server, no way to receive MCP tool calls from Claude Desktop, no way to invoke Lobster
when a forum is approved, and no way to deploy to Railway. The MCP tool functions in
`src/srf/mcp/tools.py` exist in isolation — nothing exposes them over HTTP. The `srf_forum.yaml`
exists — but there is no code that runs `lobster exec` against it. The OpenClaw and Lobster
runtimes are referenced throughout the topology but never installed.

This epic closes that gap entirely. After it completes, the SRF service can start on Railway,
pass a health check, receive Claude Desktop MCP calls, trigger Lobster workflows, and resume
halted approval gates. All subsequent epics' end-to-end integration tests also become runnable
for the first time.

> **Note on sequencing:** Epics 1, 3, and 4 unit tests pass without this epic because they mock
> subprocess calls and do not require Lobster or OpenClaw to be installed. However, no integration
> test that involves actual workflow execution can pass until Story 1.1.1 is complete. This epic
> should be delivered before Epic 5 integration tests are written.

---

## What We Gain

| Gap (before) | After this epic |
|---|---|
| Lobster and OpenClaw not installed anywhere | Both installed, version-pinned, available on PATH in dev and CI |
| No application entrypoint | `src/srf/gateway/main.py` implements the 7-step startup sequence |
| `GET /health` unimplemented — Railway health check fails | Health endpoint responds within 500 ms; Railway keeps the service alive |
| MCP tool functions unreachable from Claude Desktop | `/mcp` HTTP MCP transport exposes all registered tools |
| No way to trigger `lobster exec` from code | `LobsterRunner` spawns the subprocess, captures output, handles errors |
| Approved forums silently go nowhere | `POST /webhook/trigger` and the `review_forum_debate_format` MCP path both invoke `LobsterRunner` |
| `POST /webhook/resume` unimplemented — approval gates cannot be resumed | Resume endpoint resumes a halted Lobster workflow from its approval gate |
| No auth on gateway endpoints | `SRF_GATEWAY_TOKEN` middleware guards all non-health endpoints |
| No Dockerfile or railway.toml | Railway can build and deploy the service |
| No CI pipeline | GitHub Actions runs ruff + unit tests on every push; `validate_prompts.py` runs on every PR |
| Log rotation unimplemented | File handler rotates at 10 MB, retains 5 files |
| `.env.example` stale | All env vars from Epics 1–6 documented with placeholder values |

---

## Architecture Decisions

### OPEN: Confirm OpenClaw and Lobster installation method before Story 1.1.1

**This is a blocking decision.** The correct implementation of Story 1.1.1 depends entirely on
how these tools are distributed. Before writing any code, confirm:

1. Are `lobster` and `openclaw` pip-installable packages? If so, what are the exact package
   names and minimum versions?
2. Are they provided as pre-built binaries (apt, curl installer, etc.)?
3. Are they provided via a Docker base image (e.g., `FROM openclaw/gateway:latest`)?
4. Do they expose a Python SDK (importable from SRF code), or are they purely CLI tools?

The stories below are written to be correct regardless of the answer, but the implementation of
Story 1.1.1 and Story 1.1.6 will differ significantly depending on it. Flag this decision in the
epic before proceeding.

### OPEN: Confirm whether OpenClaw provides the HTTP server

The topology names the service "OpenClaw Gateway." If OpenClaw IS the HTTP server (i.e., it
handles `/health`, `/webhook/*`, `/mcp` and we configure it rather than writing route handlers),
then Stories 1.1.2, 1.1.4, and 1.1.5 become configuration stories, not code stories. If
OpenClaw only provides the agent runtime (`openclaw run`), then we build the HTTP server
ourselves (likely FastAPI). Confirm before implementing Story 1.1.2.

This document assumes we write our own HTTP server until confirmed otherwise.

### OPEN: Confirm MCP transport implementation

The `/mcp` endpoint uses the HTTP MCP transport. This can be implemented via:
- The official MCP Python SDK (`pip install mcp`), which provides a server class
- A thin hand-rolled implementation of the MCP JSON-RPC envelope

Confirm which approach before Story 1.1.5.

### Lobster is invoked as a subprocess — not imported

`LobsterRunner` spawns `lobster exec workflows/srf_forum.yaml` via `asyncio.create_subprocess_exec`.
It does not import a Lobster Python API. stdin is the trigger JSON; stdout is the initial step
output. stderr is captured for error reporting. The subprocess is fire-and-await: the gateway
waits for Lobster to acknowledge the workflow has started, then releases the HTTP response. It
does not block waiting for the entire workflow to complete.

### `SRF_GATEWAY_TOKEN` middleware — all endpoints except `/health`

Every endpoint except `GET /health` requires the `Authorization: Bearer <token>` header to match
`SRF_GATEWAY_TOKEN`. If the token is absent or wrong, respond 401. The health endpoint must
always be reachable by Railway's health checker — no auth there.

### Local development: run the gateway directly with `python -m srf.gateway`

No Docker required for local development. `python -m srf.gateway` starts the HTTP server on
port 8080. Lobster and OpenClaw must be installed in the local virtual environment (or on PATH
if binary). A `.env` file is loaded by the gateway startup if `python-dotenv` is installed
(listed as an optional dev dependency).

### Log rotation on local dev; Railway stdout-only in production

When `SRF_LOG_FILE` is set, the logging setup configures a `RotatingFileHandler` (10 MB / 5
files) in addition to the structured stdout handler. When `SRF_LOG_FILE` is absent (Railway
production), stdout only. This keeps Railway log aggregation clean while allowing local file-
based debugging.

---

## Stories

---

### Story 1.1.1 — Lobster & OpenClaw Dependency Setup

**As a** developer,
**I would like** Lobster and OpenClaw installed and version-pinned in the project's dependency
configuration,
**so that** any developer can reproduce the full runtime environment with a single install command
and CI can verify the binaries are present.

> **Prerequisite:** Resolve the "OPEN: Confirm installation method" architecture decision above
> before implementing this story.

**Files:**
- MODIFY: `pyproject.toml`
- NEW or MODIFY: `Dockerfile` _(create if absent; modify if base image already exists)_
- NEW: `tests/unit/test_runtime_deps.py`

**Acceptance Criteria:**

```gherkin
Scenario: lobster CLI is available on PATH after install
  Given the project is installed according to its installation instructions
  When  the command "lobster --version" is run
  Then  it exits with code 0
  And   the output contains a version string

Scenario: openclaw CLI is available on PATH after install
  Given the project is installed according to its installation instructions
  When  the command "openclaw --version" is run
  Then  it exits with code 0
  And   the output contains a version string

Scenario: pyproject.toml declares lobster and openclaw as dependencies
  Given the file pyproject.toml
  When  it is parsed
  Then  it declares lobster and openclaw as dependencies (pinned to minimum versions)

Scenario: Dockerfile produces an image where both CLIs are on PATH
  Given the Dockerfile builds successfully
  When  "docker run --rm srf lobster --version" is executed
  Then  it exits with code 0
  When  "docker run --rm srf openclaw --version" is executed
  Then  it exits with code 0

Scenario: unit test asserts lobster is importable or callable without running the full gateway
  Given the installed environment
  When  the runtime deps unit test runs
  Then  it confirms lobster is resolvable (shutil.which or importlib.util.find_spec, depending on type)
  And   it confirms openclaw is resolvable by the same method
```

**TDD Notes:** The unit test does `shutil.which("lobster")` and asserts it is not None — it does
not actually invoke Lobster. This passes in any environment where the binary is installed. The
Dockerfile scenario is an integration test; skip in CI if Docker is not available.

---

### Story 1.1.2 — Gateway Application Entrypoint & Startup Sequence

**As a** system,
**I would like** an application entrypoint that executes the canonical gateway startup sequence
and starts the HTTP server,
**so that** the service can be started with a single command and reaches a healthy state in the
correct order.

**Startup sequence (from topology §2):**
```
1. Load SRFConfig.from_env()
2. configure_logging(config)
3. tracker = build_tracker(config)
4. register_prompts(tracker, ALL_PROMPTS)
5. Initialise workspace directories
6. Start HTTP server on :8080
7. Log INFO "Gateway ready"
```

**Files:**
- NEW: `src/srf/gateway/__init__.py`
- NEW: `src/srf/gateway/main.py`
- NEW: `src/srf/gateway/server.py`  _(HTTP app — FastAPI or equivalent)_
- NEW: `tests/unit/test_gateway_startup.py`
- MODIFY: `src/srf/logging.py`  _(add rotating file handler when SRF_LOG_FILE is set)_

**Acceptance Criteria:**

```gherkin
Scenario: gateway startup calls all 7 steps in order
  Given mock implementations of all startup dependencies
  When  run_startup(config) is called
  Then  configure_logging was called first
  And   build_tracker was called after configure_logging
  And   register_prompts was called after build_tracker
  And   workspace initialisation was called after register_prompts
  And   the HTTP server was started last

Scenario: startup raises ConfigurationError and halts if SRF_LLM_PROVIDER is absent
  Given SRF_LLM_PROVIDER is not set
  When  run_startup() is called
  Then  it raises ConfigurationError before starting the HTTP server

Scenario: startup continues if register_prompts fails due to PromptLedger unreachable
  Given a tracker that raises on register_code_prompts
  When  run_startup(config) is called
  Then  a WARNING is logged containing "prompt registration failed"
  And   the HTTP server starts normally

Scenario: GET /health responds 200 within 500 ms once startup completes
  Given the gateway server is started
  When  GET /health is requested
  Then  the response status is 200
  And   the response body is valid JSON containing "status": "ok"

Scenario: python -m srf.gateway starts the server on port 8080
  Given the module is invoked as __main__
  When  "python -m srf.gateway" is run
  Then  a server is listening on port 8080

Scenario: log rotation is configured when SRF_LOG_FILE is set
  Given SRF_LOG_FILE is set to a writable path
  When  configure_logging(config) is called
  Then  a RotatingFileHandler is active with maxBytes=10_485_760 and backupCount=5

Scenario: no RotatingFileHandler is configured when SRF_LOG_FILE is absent
  Given SRF_LOG_FILE is not set
  When  configure_logging(config) is called
  Then  no file handler is active — stdout only
```

**TDD Notes:** Mock the HTTP server start with a flag rather than binding a real port. Use
dependency injection so `run_startup()` accepts callable parameters for each step (allows
replacing with mocks in unit tests). The `GET /health` scenario uses `httpx.AsyncClient` against
a real test server instance — use `pytest-anyio` or `anyio` for async HTTP test client support.

---

### Story 1.1.3 — Lobster Workflow Subprocess Runner

**As a** system,
**I would like** a `LobsterRunner` class that invokes `lobster exec` as a subprocess, passes
trigger JSON via stdin, and captures the result,
**so that** approved forums can be kicked off programmatically from the webhook and MCP trigger
paths.

**Files:**
- NEW: `src/srf/gateway/lobster_runner.py`
- NEW: `tests/unit/test_lobster_runner.py`

**Acceptance Criteria:**

```gherkin
Scenario: LobsterRunner.run() invokes lobster exec with the correct workflow path
  Given a mock subprocess with lobster available
  When  LobsterRunner(workflow="workflows/srf_forum.yaml").run(trigger_json={...}) is called
  Then  subprocess was called with ["lobster", "exec", "workflows/srf_forum.yaml"]
  And   the trigger JSON was written to the subprocess stdin as UTF-8 encoded JSON

Scenario: LobsterRunner.run() returns the parsed stdout JSON on success
  Given a mock subprocess that exits 0 and writes {"forum_id": "forum-1"} to stdout
  When  LobsterRunner.run(trigger_json={...}) is called
  Then  the returned dict equals {"forum_id": "forum-1"}

Scenario: LobsterRunner.run() raises WorkflowLaunchError when lobster exits non-zero
  Given a mock subprocess that exits 1 with stderr "workflow file not found"
  When  LobsterRunner.run(trigger_json={...}) is called
  Then  it raises WorkflowLaunchError
  And   the error message contains "workflow file not found"

Scenario: LobsterRunner.run() raises WorkflowLaunchError when stdout is not valid JSON
  Given a mock subprocess that exits 0 with non-JSON stdout
  When  LobsterRunner.run(trigger_json={...}) is called
  Then  it raises WorkflowLaunchError with a message indicating the parse failure

Scenario: LobsterRunner.run() raises WorkflowLaunchError when lobster is not found on PATH
  Given lobster is not installed (shutil.which returns None)
  When  LobsterRunner.run(trigger_json={...}) is called
  Then  it raises WorkflowLaunchError with a message indicating lobster is not available

Scenario: LobsterRunner.run() logs the forum_id and workflow at INFO on success
  Given a mock subprocess that exits 0 with valid JSON containing forum_id
  When  LobsterRunner.run(trigger_json={"forum_id": "forum-abc", ...}) is called
  Then  an INFO log is emitted containing forum_id="forum-abc"
```

**TDD Notes:** Inject the subprocess function as a parameter (`subprocess_fn=asyncio.create_subprocess_exec`) so unit tests can substitute a mock without patching globals. Never call a real `lobster` subprocess in unit tests — always mock. The `WorkflowLaunchError` is a new exception defined in `src/srf/gateway/lobster_runner.py`.

---

### Story 1.1.4 — HTTP Webhook Endpoints & Gateway Authentication

**As a** system,
**I would like** `POST /webhook/trigger` and `POST /webhook/resume` endpoints protected by
`SRF_GATEWAY_TOKEN` authentication,
**so that** forums can be triggered programmatically and halted approval gates can be resumed
without requiring Claude Desktop.

**Files:**
- NEW: `src/srf/gateway/webhooks.py`
- NEW: `src/srf/gateway/auth.py`
- NEW: `tests/unit/test_webhooks.py`
- NEW: `tests/unit/test_gateway_auth.py`
- MODIFY: `src/srf/gateway/server.py`  _(register routes)_

**Acceptance Criteria:**

```gherkin
Scenario: POST /webhook/trigger with valid token triggers a Lobster workflow
  Given a valid SRF_GATEWAY_TOKEN in the Authorization header
  And   request body { "config_path": "/path/to/config.json" }
  And   a mock LobsterRunner that returns {"forum_id": "forum-xyz"}
  When  POST /webhook/trigger is called
  Then  the response status is 202
  And   the response body contains forum_id="forum-xyz"
  And   LobsterRunner.run() was called with the config path in the trigger JSON

Scenario: POST /webhook/resume with valid token resumes a halted workflow
  Given a valid SRF_GATEWAY_TOKEN in the Authorization header
  And   request body { "resume_token": "tok-123", "decision": "approved", "reviewer_notes": "LGTM" }
  And   a mock LobsterRunner that handles resume
  When  POST /webhook/resume is called
  Then  the response status is 202
  And   LobsterRunner.resume() was called with resume_token and decision

Scenario: all webhook endpoints return 401 when Authorization header is absent
  Given no Authorization header in the request
  When  POST /webhook/trigger is called
  Then  the response status is 401
  And   the response body contains an error message

Scenario: all webhook endpoints return 401 when Authorization header has wrong token
  Given Authorization: Bearer wrong-token
  When  POST /webhook/trigger is called
  Then  the response status is 401

Scenario: GET /health returns 200 without any Authorization header
  Given no Authorization header
  When  GET /health is called
  Then  the response status is 200

Scenario: POST /webhook/trigger returns 400 when config_path is absent from body
  Given a valid SRF_GATEWAY_TOKEN
  And   request body {} (missing config_path)
  When  POST /webhook/trigger is called
  Then  the response status is 400
  And   the response body indicates config_path is required

Scenario: POST /webhook/trigger returns 500 and logs ERROR when LobsterRunner raises
  Given a mock LobsterRunner that raises WorkflowLaunchError("lobster not found")
  When  POST /webhook/trigger is called with valid auth and body
  Then  the response status is 500
  And   an ERROR is logged containing "lobster not found"
```

**TDD Notes:** Use `httpx.AsyncClient(app=app, base_url="http://test")` for all endpoint tests — never bind a real port. `auth.py` is a single dependency function (`require_gateway_token`) that reads `SRF_GATEWAY_TOKEN` from config. Mock `LobsterRunner` with a `MagicMock` that has `run` and `resume` as `AsyncMock`. The `resume` method is a new method on `LobsterRunner` that invokes `lobster resume <token>` (or equivalent Lobster API — confirm with Lobster docs).

---

### Story 1.1.5 — MCP HTTP Transport & Tool Registration

**As a** system,
**I would like** a `POST /mcp` endpoint that exposes the SRF MCP tools over the HTTP MCP
transport,
**so that** Claude Desktop can connect to the Railway service URL and call
`trigger_newsletter_forum`, `review_forum_debate_format`, and `approve_editorial_review`.

> **Prerequisite:** Resolve the "OPEN: Confirm MCP transport implementation" architecture
> decision before implementing this story.

**Files:**
- NEW: `src/srf/gateway/mcp_server.py`
- NEW: `tests/unit/test_mcp_server.py`
- MODIFY: `src/srf/gateway/server.py`  _(register /mcp route)_
- MODIFY: `src/srf/mcp/tools.py`  _(inject LobsterRunner and tracker as dependencies rather
  than constructing them internally, if not already done)_

**Acceptance Criteria:**

```gherkin
Scenario: POST /mcp responds to MCP initialize request
  Given a valid SRF_GATEWAY_TOKEN
  And   an MCP initialize JSON-RPC request body
  When  POST /mcp is called
  Then  the response contains the server name and protocol version
  And   the response lists the available tool names

Scenario: tool list includes trigger_newsletter_forum, review_forum_debate_format, approve_editorial_review
  Given a valid MCP tools/list request
  When  POST /mcp is called
  Then  the response tools array contains all three tool names
  And   each tool entry contains a description and inputSchema

Scenario: POST /mcp routes tools/call for trigger_newsletter_forum to the Python tool function
  Given a valid MCP tools/call request for trigger_newsletter_forum with source_path argument
  And   a mock implementation of the tool function that returns {"status": "ok"}
  When  POST /mcp is called
  Then  the response contains the tool function's return value
  And   the tool function was called with source_path from the request

Scenario: POST /mcp returns 401 without valid SRF_GATEWAY_TOKEN
  Given no Authorization header
  When  POST /mcp is called
  Then  the response status is 401

Scenario: MCP tool call errors are returned as MCP error responses, not HTTP 500s
  Given a mock tool function that raises a ValueError("invalid path")
  When  POST /mcp tools/call is called for that tool
  Then  the HTTP response status is 200
  And   the MCP response body contains an error field with the message
```

**TDD Notes:** Mock all tool function implementations — this story tests the transport layer, not the tool logic. If using the MCP Python SDK, the server object is testable in isolation by calling its handler methods directly without an HTTP layer. If hand-rolling, test the JSON-RPC envelope parsing and routing. Tool dependencies (`tracker`, `LobsterRunner`) are injected at server construction time; tests provide mocks.

---

### Story 1.1.6 — Railway Deployment & CI Pipeline Configuration

**As a** developer,
**I would like** a Dockerfile and `railway.toml` that produce a deployable Railway service, and a
GitHub Actions CI workflow that gates every push,
**so that** the service deploys reliably and no code with failing tests or lint errors reaches
`main`.

**Files:**
- NEW or MODIFY: `Dockerfile`
- NEW: `railway.toml`
- NEW: `.github/workflows/ci.yml`
- MODIFY: `.env.example`  _(add all vars from Epics 1–6 that are missing)_

**Acceptance Criteria:**

```gherkin
Scenario: Docker image builds successfully
  Given the Dockerfile
  When  "docker build -t srf ." is run
  Then  it exits with code 0
  And   the image contains python 3.11+, lobster, and openclaw on PATH

Scenario: docker run --rm srf python -m srf.gateway --help exits 0
  Given the built Docker image
  When  "docker run --rm srf python -m srf.gateway --help" is run
  Then  it exits with code 0

Scenario: railway.toml declares the correct port, restart policy, and volume mount
  Given the file railway.toml
  When  it is parsed
  Then  it declares port 8080
  And   it declares restart = "always"
  And   it declares a volume mount at /data/workspace

Scenario: CI workflow runs on every push and pull request to main
  Given .github/workflows/ci.yml
  When  it is parsed as YAML
  Then  the trigger includes push and pull_request targeting main

Scenario: CI workflow runs ruff check before pytest
  Given .github/workflows/ci.yml
  When  it is parsed
  Then  it contains a step running "ruff check src/ tests/ scripts/"
  And   it contains a step running "pytest tests/unit -v --tb=short"
  And   ruff runs before pytest

Scenario: CI workflow runs validate_prompts.py on pull requests
  Given .github/workflows/ci.yml
  When  it is parsed
  Then  it contains a step running "python scripts/validate_prompts.py --dry-run"
  And   this step is configured to skip gracefully when PROMPTLEDGER_API_URL is absent

Scenario: .env.example contains all required environment variables
  Given .env.example
  When  it is read
  Then  it contains placeholder entries for all of the following vars:
        SRF_LLM_PROVIDER, SRF_LLM_MODEL, SRF_LLM_API_KEY,
        PROMPTLEDGER_API_URL, PROMPTLEDGER_API_KEY,
        SRF_GATEWAY_TOKEN,
        SRF_WORKSPACE_ROOT, SRF_LOG_LEVEL, SRF_LOG_FILE,
        SRF_MAX_PREP_RETRIES, SRF_MIN_AGENTS, SRF_MIN_PAPERS,
        SRF_ARXIV_DELAY_SECONDS, SRF_DEBATE_CONTEXT_TOKENS
```

**TDD Notes:** The Dockerfile and railway.toml scenarios are integration tests — skip in
environments without Docker. The `.env.example` scenario is a pure file-read test; no
environment setup needed. The `.github/workflows/ci.yml` scenario is a YAML parse test.
The CI file should use `continue-on-error: false` for all steps — a failing lint or test must
block merge.

---

## Implementation Order

```
Story 1.1.1 (install Lobster + OpenClaw — unblocks everything that invokes them)
  → Story 1.1.2 (gateway entrypoint + health — makes the service startable)
    → Story 1.1.3 (Lobster runner — provides the subprocess invocation layer)
      ┌─ Story 1.1.4 (webhooks + auth — depends on 1.1.3 for LobsterRunner)
      └─ Story 1.1.5 (MCP transport — depends on 1.1.2 for the server app)
           → Story 1.1.6 (deployment config — wraps everything above into a deployable artifact)
```

Stories 1.1.4 and 1.1.5 can be developed in parallel once 1.1.3 is complete.

---

## Verification Checklist

```bash
# After 1.1.1
lobster --version
openclaw --version
pytest tests/unit/test_runtime_deps.py -v

# After 1.1.2
pytest tests/unit/test_gateway_startup.py -v
python -m srf.gateway &  # start in background
curl http://localhost:8080/health  # expect {"status": "ok"}
kill %1

# After 1.1.3
pytest tests/unit/test_lobster_runner.py -v

# After 1.1.4
pytest tests/unit/test_webhooks.py tests/unit/test_gateway_auth.py -v

# After 1.1.5
pytest tests/unit/test_mcp_server.py -v

# After 1.1.6
docker build -t srf . && docker run --rm srf python -m srf.gateway --help
python -c "import yaml; ci = yaml.safe_load(open('.github/workflows/ci.yml')); print('CI ok')"

# Full epic suite
pytest tests/unit -v --tb=short
ruff check src/ tests/ scripts/
```

---

## Critical Files

**NEW:**
- `src/srf/gateway/__init__.py`
- `src/srf/gateway/main.py`  _(entrypoint + startup sequence)_
- `src/srf/gateway/server.py`  _(HTTP app, route registration)_
- `src/srf/gateway/auth.py`  _(SRF_GATEWAY_TOKEN dependency)_
- `src/srf/gateway/webhooks.py`  _(POST /webhook/trigger, POST /webhook/resume)_
- `src/srf/gateway/lobster_runner.py`  _(LobsterRunner, WorkflowLaunchError)_
- `src/srf/gateway/mcp_server.py`  _(MCP HTTP transport, tool registration)_
- `Dockerfile`  _(or modify if exists)_
- `railway.toml`
- `.github/workflows/ci.yml`
- `tests/unit/test_runtime_deps.py`
- `tests/unit/test_gateway_startup.py`
- `tests/unit/test_lobster_runner.py`
- `tests/unit/test_webhooks.py`
- `tests/unit/test_gateway_auth.py`
- `tests/unit/test_mcp_server.py`

**MODIFY:**
- `pyproject.toml`  _(add lobster, openclaw, fastapi/httpx as dependencies)_
- `src/srf/logging.py`  _(add rotating file handler)_
- `src/srf/gateway/server.py`  _(route registration in Stories 1.1.4, 1.1.5)_
- `src/srf/mcp/tools.py`  _(dependency injection for LobsterRunner + tracker)_
- `.env.example`  _(add all missing vars)_
- `Requirements/progress_summary.md`
