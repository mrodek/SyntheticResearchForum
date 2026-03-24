# SRF Progress Tracker

Newest entries first. Each entry references the epic/story, files changed, and decisions made.

---

## [2026-03-24] - Story 1.1.7: entrypoint-owned git clone, simplified bootstrap

### Summary
- Epic 1.1, Story 1.1.7 — resolves open design question from Story 1.1.6
- MODIFY: `mrodek/clawdbot-railway-template` `entrypoint.sh` — add SRF-specific git clone/pull block (root context, before privilege drop) with project-specific commentary
- MODIFY: `Requirements/Railway/RAILWAY_SETUP_GUIDE.md` — Step 8 updated with entrypoint.sh SRF block and simplified bootstrap.sh; Step 11 updated to supersede update_srf skill
- MODIFY: `README.md` — deployment section updated with entrypoint/bootstrap split and source protection explanation
- MODIFY: `Requirements/srf_epic_01_1_runtime_infrastructure.md` — Story 1.1.7 added, implementation order updated
- Story 1.1.6 (`update_srf` skill) superseded — Railway Restart replaces it

### Decisions
- Git clone/pull moves to `entrypoint.sh` (root context). `/data/srf` stays permanently root-owned. `openclaw` process can read but never write to source files.
- `bootstrap.sh` simplified to 4 lines: venv create, pip install (non-editable), skills copy. No git, no chmod.
- Non-editable pip install (`pip install /data/srf[...]` without `-e`) — writes nothing back to `/data/srf`, only into `/data/venv/lib/`.
- Railway Restart (~30s) replaces `update_srf` skill for code updates. Restart re-runs entrypoint as root → pulls latest → bootstrap reinstalls.
- `entrypoint.sh` must have prominent project-specific commentary marking the git clone section so template reusers know what to change.

### Issues & Resolution
- Story 1.1.6 `update_srf.sh` could not work: it runs as `openclaw` and cannot `chmod u+w` or `git pull` into root-owned `/data/srf`. Superseded rather than fixed — the root design is better.

### Next Steps
- [ ] Apply entrypoint.sh SRF block to `mrodek/clawdbot-railway-template` and redeploy
- [ ] Create simplified bootstrap.sh on the volume via OpenClaw exec tool
- [ ] Verify Railway Restart picks up new SRF code end-to-end

---

## [2026-03-24] - Railway: entrypoint privilege model and Dockerfile useradd fix

### Summary
- MODIFY: `Requirements/Railway/RAILWAY_SETUP_GUIDE.md` — documented container startup sequence, privilege drop model, root-ownership of `/data/srf`, and open design question for bootstrap
- No code changes — documentation and architectural understanding only

### Decisions
- `/data/srf` is intentionally left root-owned by `entrypoint.sh`. The `openclaw` process (which runs all skills and scripts) cannot write to it. This is the **primary** source protection — enforced by the OS, not by prompt instructions.
- Skill document instructions ("never edit `/data/srf/`") are Level 2 / defence in depth. The filesystem would block writes anyway.
- `chmod -R a-w` in bootstrap.sh is redundant given root-ownership. Removed from bootstrap design.
- `update_srf.sh` as designed cannot work — it runs as `openclaw` and cannot `chmod u+w` or `git pull` into a root-owned directory.

### Issues & Resolution
- Template PR #2 (`mrodek/clawdbot-railway-template`, merged 2026-03-22) added `entrypoint.sh` to fix volume ownership but omitted `RUN useradd -r -s /bin/false -m -d /home/openclaw openclaw` from the Dockerfile runtime stage. This causes `chown: invalid user: 'openclaw:openclaw'` and a crash loop on every deploy.
- Fix: add the `useradd` line to the runtime stage of `Dockerfile` in the template fork. No custom Start Command needed once fixed.
- Root cause of original restart failure (2026-03-24 session): the service was working before PR #2 landed. The PR introduced the chown step without creating the user.

### Next Steps
- [ ] Add `RUN useradd -r -s /bin/false -m -d /home/openclaw openclaw` to `mrodek/clawdbot-railway-template` Dockerfile runtime stage
- [ ] Resolve open design question: how does bootstrap.sh populate `/data/srf` given that it runs as `openclaw` and `/data/srf` is root-owned?
- [ ] Revisit `update_srf.sh` — current implementation cannot work under the root-ownership model

---

## [2026-03-24] - Story 1.1.6: update_srf skill and script

### Summary
- Epic 1.1, Story 1.1.6 — fast SRF code update without full Railway redeploy
- NEW: `scripts/update_srf.sh` — unlock/pull/pip/relock with trap-based relock on failure
- NEW: `skills/update_srf/SKILL.md` — exec-only skill, error handling, /data/srf edit prohibition
- NEW: `tests/unit/test_update_srf.py` — 11 tests; 5 pass on Windows, 6 bash-execution tests skip (run on Linux CI)
- MODIFY: `Requirements/Railway/RAILWAY_SETUP_GUIDE.md` — Option A/B/C protection table, restart procedures, promptledger extra, Step 11 (update_srf)
- MODIFY: `Requirements/srf_epic_01_1_runtime_infrastructure.md` — Story 1.1.6 added

### Decisions
- Option B (filesystem lock) chosen for /data/srf protection: `chmod -R a-w` after every pull, unlock before. Defence in depth alongside skill document instructions.
- Script is the logic; skill is only the routing layer. Avoids probabilistic execution of a deterministic procedure.
- pip install includes `[anthropic,openai,promptledger]` — promptledger extra was previously missing from bootstrap.sh.
- Bash-execution tests marked `@_BASH_TESTS` (skip on win32) — they exercise the relock-on-failure guarantee which requires a real bash environment.

### Issues & Resolution
- `openclaw start` identified as the correct Railway Start Command (was previously undiscovered). Documented in RAILWAY_SETUP_GUIDE.md with full "what not to do" list from troubleshooting session.
- `openclaw gateway --foreground` is not a valid flag. `openclaw gateway` only starts WebSocket server, not HTTP stack.
- Dockerfile ENTRYPOINT crashes with `chown: invalid user: 'openclaw:openclaw'` when Start Command is cleared — must always be set to `openclaw start`.

### Next Steps
- [ ] Confirm Railway service starts cleanly with `openclaw start`
- [ ] Verify bootstrap.sh runs on new service and /data/srf is locked after startup
- [ ] Run update_srf skill end-to-end on Railway to confirm relock cycle works

---

## [2026-03-23] - BUG-008: tracker.execute() missing model field causes PL 500

### Summary
- BUG-008: `Requirements/bugs/BUG-008-tracker-execute-missing-model-field.md` — new bug document
- FIXED: `src/srf/agents/preparation.py` — added `model={"provider": config.llm_provider, "model_name": config.llm_model}` to all three `tracker.execute()` calls (prepare_paper_agent, prepare_moderator, prepare_challenger)
- TESTS: 3 new tests in `test_paper_agent_preparation.py` and `test_moderator_challenger_preparation.py`
- Test suite: 221 passed, 5 skipped, 0 failures

### Decisions
- Passed `model` as a kwarg to `execute()` at each call site rather than configuring it at constructor time. `config` is already available at all three call sites (used for tracker=None fallback path).
- Model dict shape `{"provider": "...", "model_name": "..."}` matches the `/v1/executions/run` API schema from CR-001.

### Issues & Resolution
- Root cause: PL server's `execution.py:240` does `request_body['model']` — crashes with `KeyError: 'model'` when field absent.
- The PL SDK's `execute()` reference docs don't document a `model` parameter, but the underlying API requires it. Passing as kwarg resolves the 500.

### Next Steps
- [ ] Redeploy Railway (bootstrap.sh will git reset --hard to pick up fix)
- [ ] Re-run srf_init.py, then re-run the Lobster pipeline for the staged forum

---

## [2026-03-23] - BUG-005: srf_forum.yaml wrong file extension and invalid approval syntax

### Summary
- BUG-005: `Requirements/bugs/BUG-005-workflow-wrong-extension-and-approval-syntax.md` — new bug document
- RENAMED: `workflows/srf_forum.yaml` → `workflows/srf_forum.lobster` — Lobster requires `.lobster` extension
- FIXED: `editorial_review_gate` approval value: `required` → human-readable prompt string
- FIXED: `skills/review_forum_debate_format/SKILL.md` pipeline path updated to `srf_forum.lobster`
- UPDATED: `tests/unit/test_run_debate_bridge.py` — 3 new BUG-005 tests; existing tests updated to `.lobster`
- UPDATED: `tests/unit/test_run_paper_extraction.py`, `test_run_preparation.py` — path updated to `.lobster`
- Test suite: 216 passed, 5 skipped, 0 failures

### Decisions
- **`.lobster` is the required extension**: Lobster README explicitly shows `lobster run path/to/workflow.lobster`. YAML content inside is unchanged — `yaml.safe_load()` still parses it correctly.
- **`approval:` takes a prompt string**: The value is displayed to the human reviewer at the gate. `required` is not a valid string in this context.

### Issues & Resolution
- Discovered during live Railway session: OpenClaw agent found `lobster run --file path/to/workflow.lobster` in the Lobster help and began exploring the CLI, confirming our `.yaml` file would not be found.

### Next Steps
- [ ] Push to GitHub and redeploy Railway
- [ ] Re-run the staged forum (forum-20260323-03ede4e5) by directly invoking the lobster tool with the known trigger JSON

---

## [2026-03-22] - BUG-004: srf_forum.yaml invalid input reference and relative Python paths

### Summary
- BUG-004: `Requirements/bugs/BUG-004-workflow-lobster-input-and-paths.md` — new bug document
- FIXED: `workflows/srf_forum.yaml` — `workspace_setup` command now pipes `$LOBSTER_ARGS_JSON` via shell; all Python step commands use absolute `/data/venv/bin/python` and `/data/srf/scripts/` paths
- FIXED: `skills/review_forum_debate_format/SKILL.md` — Lobster invocation now uses `argsJson` (not invalid `input`) with absolute pipeline path `/data/srf/workflows/srf_forum.yaml`; serialisation instruction added
- UPDATED: `tests/unit/test_run_debate_bridge.py` — 2 new tests (`test_srf_forum_yaml_workspace_setup_does_not_reference_trigger_step`, `test_srf_forum_yaml_python_steps_use_absolute_paths`)
- UPDATED: `tests/unit/test_run_paper_extraction.py` — stale path assertions updated to verify absolute paths
- UPDATED: `tests/unit/test_run_preparation.py` — stale path assertion updated to verify absolute paths
- UPDATED: `tests/unit/test_runtime_deps.py` — `test_railway_toml_has_start_command_with_lobster_install` renamed and corrected; Lobster is installed via bootstrap.sh on persistent volume, not in railway.toml startCommand
- Test suite: 213 passed, 5 skipped, 0 failures

### Decisions
- **Lobster initial input via `$LOBSTER_ARGS_JSON`**: Lobster has no `$trigger` step concept. Initial workflow data is passed at invocation via `argsJson` and accessed inside steps as the `$LOBSTER_ARGS_JSON` env var. First step uses `echo "$LOBSTER_ARGS_JSON" | python ...` shell pipe.
- **Absolute paths required**: Lobster's cwd defaults to the OpenClaw gateway working directory (not `/data/srf`). All Python steps must use `/data/venv/bin/python` and `/data/srf/scripts/` absolute paths.
- **Lobster installed via bootstrap.sh**: Railway container filesystem resets on redeploy; `/data` volume persists. Lobster source cloned to `/data/lobster` and wrapper at `/usr/local/bin/lobster` recreated each startup by bootstrap.sh.
- **`argsJson` not `input`**: The Lobster plugin tool schema parameter is `argsJson` (a JSON-serialised string). `input` does not exist.

### Issues & Resolution
- Tests in `test_run_paper_extraction.py` and `test_run_preparation.py` were asserting the old buggy relative path commands — updated to verify absolute paths instead.
- `test_railway_toml_has_start_command_with_lobster_install` was written for a path not taken (installing Lobster via railway.toml startCommand). Corrected to reflect bootstrap.sh approach.

### Lessons Learned
- When a bug fix changes the canonical form of a value (e.g. relative → absolute path), existing tests that assert the old form must be updated as part of the same fix.

### Next Steps
- [ ] Redeploy Railway to pick up BUG-003 fix (double-brace CLUSTERING_PROMPT) and updated skills (bootstrap.sh already updated on volume)
- [ ] Verify Lobster binary functional after next Railway startup
- [ ] Begin Epic 7: Synthesis, Evaluation & Post-Debate Processing

---

## [2026-03-21] - Governance: Skill Error Handling Rule

### Summary
- Added Section 11 (Skill Document Requirements) to `CLAUDE.md` — hard governance rule for all skill documents
- Updated `Requirements/openclaw_native_vision.md` — new section "The Silent Failure Path: Skill Error Handling" documenting the incident, root cause, and architectural principle
- Updated `Requirements/srf_epic_06b_openclaw_native_debate.md` — new Architecture Decision + Error Handling section in SKILL.md spec + 2 new Acceptance Criteria scenarios for Story 6B.2
- Updated `skills/trigger_newsletter_forum/SKILL.md` — added explicit Error Handling section closing the gap that caused the incident

### Decisions
- **"Report and stop" is the safe default** — any deviation (investigate, retry, fix) must be explicitly authorised in the skill document; for SRF skills it is never authorised
- **`/data/srf/` is explicitly off-limits** — stated in every skill document and in CLAUDE.md; this is the boundary between the agent layer and the deterministic layer
- **Error handling is structural, not optional** — added to CLAUDE.md "What Claude Should Never Do" so it applies to all future skill authoring in this session and beyond

### Issues & Resolution
- Root cause of the incident: `trigger_newsletter_forum/SKILL.md` had no instruction for what to do when `parse_newsletter.py` exited non-zero. The agent filled the silence by editing source files — rational behaviour, wrong outcome.
- The fix is not technical — it is governance. Skills must specify failure paths as carefully as they specify happy paths.

### Lessons Learned
- Unspecified failure states in skill documents are implicit grants of agent agency
- A capable LLM with filesystem and exec tools will always attempt to be helpful — the only way to constrain that helpfulness is explicit instruction
- The damage from this class of error is not the agent's action itself but the side effect on the git working tree, which breaks the deployment contract

### Next Steps
- [ ] When writing `skills/run_forum_debate/SKILL.md` (Story 6B.2), include the Error Handling section before any other section is considered complete
- [ ] Audit any future skills for unspecified failure paths before merging

---

## [2026-03-21] - BUG-003: Clustering Prompt Double-Brace

### Summary
- Created `Requirements/bugs/BUG-003-clustering-prompt-double-brace.md`
- Added `test_clustering_prompt_json_example_uses_single_braces` to `tests/unit/test_newsletter_clustering.py` (RED → GREEN)
- Fixed `src/srf/prompts/newsletter.py`: `{{` → `{` and `}}` → `}` in `CLUSTERING_PROMPT` JSON example
- Tests: 177 passing, 5 skipped, 1 pre-existing failure (Story 1.1.5 railway.toml test)

### Decisions
- `CLUSTERING_PROMPT` is a static string — `.format()` is never called on it. `{{`/`}}` escape sequences only resolve during `.format()`, so they appeared literally to the LLM as malformed JSON notation.
- Fix is minimal: change only the JSON example block. The `{tension_axes}` and `{paper_summaries}` placeholders in the descriptive text are intentional and remain unchanged.

### Issues & Resolution
- LLM returned empty content (`""`) → `json.loads("")` raised `Expecting value: line 1 column 1 (char 0)`
- Root cause: `{{` and `}}` in the JSON example block confused the model
- The OpenClaw agent on Railway had added a heuristic fallback to work around this — that fallback is not committed to repo; the real fix is now in the prompt

### Next Steps
- [ ] Redeploy on Railway and rerun `parse_newsletter.py` — should now get real LLM clustering instead of heuristic fallback
- [ ] Story 1.1.5 — implement `.github/workflows/ci.yml`
- [ ] Decide: Epic 6 (Python debate) vs Epic 6B (OpenClaw-native debate)

---

## [2026-03-20] - BUG-001: Newsletter Parser Format Mismatch

### Summary
- Created `Requirements/bugs/BUG-001-newsletter-parser-format-mismatch.md` — documents 3 root causes
- Added `tests/fixtures/newsletters/actual_format.md` — fixture with actual newsletter format (bold header, `[Link](URL)` links, paragraph Pattern Watch)
- Added 3 failing tests (RED) for each root cause, then fixed `src/srf/newsletter/parser.py` (GREEN)
- Tests: 175 passing, 4 skipped, 1 pre-existing failure (Story 1.1.5 railway.toml test)

### Decisions
- **Bold issue header fallback** — `_parse_content` now tries `## Issue #N` regex first, then `**Issue #N**` bold regex; both formats remain valid
- **Markdown link URL fallback** — `_parse_one_signal` tries `**URL:**` label extraction first; if empty, tries `[Link](URL)` pattern via new `_extract_markdown_link()` helper
- **Paragraph Pattern Watch fallback** — `_extract_bullets()` result used when non-empty; otherwise new `_extract_paragraphs()` helper splits body on blank lines
- No fixture files modified; all 11 pre-existing parser tests remain GREEN

### Issues & Resolution
- Root cause 1: `re.search(r"^## Issue #(\d+)...")` never matched `**Issue #1 — ...**` — fixed with bold inline regex fallback
- Root cause 2: `_extract_field(body, "URL")` looked for `**URL:**` label absent in actual format — fixed with `_extract_markdown_link()` helper
- Root cause 3: `_extract_bullets(pw_body)` returned `[]` for prose paragraphs — fixed with `_extract_paragraphs()` fallback

### Next Steps
- [ ] Redeploy on Railway and rerun `parse_newsletter.py` against `.newsletters/weekly_field_notes_issue_1.md`
- [ ] Story 1.1.5 — implement `.github/workflows/ci.yml`
- [ ] Begin Epic 6: Debate Engine

---

## [2026-03-19] - Railway Deployment Fixes & Dockerfile

### Summary
- Added `Dockerfile` — Node.js 20 base with Python 3.11 installed; builds OpenClaw, Lobster, and SRF Python package at image build time
- Simplified `railway.toml` startCommand to `openclaw start` (installs now happen at build, not runtime)
- Fixed 5 pre-deploy blockers identified during deploy readiness review:
  1. `railway.toml` — added `pip install + npm install @clawdbot/openclaw` to startCommand (now moved to Dockerfile)
  2. `scripts/validate_and_stage_forum.py` — trigger JSON now includes `config_path` so `run_workspace_setup.py` can read it
  3. `config/openclaw.json` — skills loader now checks `./skills` (repo) before `/data/workspace/skills` (volume)
  4. `config/exec-approvals.json` — added bare `python` and `python3` to exec allowlist
  5. `CLAUDE.md` — added "Definition of Complete" hard rule to prevent stories being marked complete without verification
- Added `Requirements/Railway/RAILWAY_SETUP_GUIDE.md` — step-by-step Railway configuration guide
- Reopened Story 1.1.5 (CI Pipeline) — was incorrectly marked Complete; `.github/workflows/ci.yml` never existed

### Decisions
- **Dockerfile over railpack** — Railway's railpack auto-detector only installed Python (not Node.js); Dockerfile gives explicit control over both runtimes
- **Install at build time not runtime** — moves `npm install` and `pip install` to Docker build layer so failures surface in build logs and startup is instant
- **Node.js 20 base image** — OpenClaw requires Node >= 20; Python 3.11 added via apt on top

### Issues & Resolution
- Railway build used railpack, detected Python-only project, installed Python 3.13 via mise but not Node.js → `openclaw` never installed → healthcheck failed on every attempt
- Fix: `Dockerfile` with `node:20-slim` base + `python3.11` apt install

### Next Steps
- [ ] Push Dockerfile + fixes → confirm Railway build succeeds and `/health` passes
- [ ] Run `/setup` wizard at `https://<service>.up.railway.app/setup`
- [ ] Run `python scripts/srf_init.py` via OpenClaw exec tool
- [ ] Story 1.1.5 — implement `.github/workflows/ci.yml` (TDD)
- [ ] Begin Epic 6: Debate Engine

---

## [2026-03-19] - Story 1.1.5 Reopened: CI Pipeline Never Implemented

### Summary
- Story 1.1.5 (CI Pipeline & Deployment Documentation) was incorrectly marked Complete on 2026-03-19
- `.github/workflows/ci.yml` was never created — the story's primary deliverable is missing
- Story moved back to `Not Started` in `progress_summary.md`
- `CLAUDE.md` updated with a hard "Definition of Complete" rule to prevent recurrence

### Issues & Resolution
- Root cause: story marked Complete without verifying all `Files:` block entries exist in the repo
- Fix: added explicit pre-completion checklist to `CLAUDE.md` §4 (Progress Tracking)

### Next Steps
- [ ] Story 1.1.5 — write `tests/unit/test_ci_workflow.py` (RED), then create `.github/workflows/ci.yml` (GREEN)
- [ ] Enable "Wait for CI" in Railway once workflow is live

---

## [2026-03-19] - Epic 5 Complete: Agent Preparation Phase

### Summary
- Epic 5, Stories 5.1–5.5 — all GREEN; 165 unit tests pass, 4 skipped
- **New (src):** `src/srf/llm/__init__.py`, `src/srf/llm/fallback.py`; `src/srf/agents/{__init__,models,roster,preparation,orchestrator}.py`; `src/srf/prompts/agents.py`
- **Modified (src):** `src/srf/prompts/__init__.py` (+`ALL_PROMPTS` aggregating newsletter + agent prompts); `src/srf/config.py` (+`paper_token_budget`, `max_prep_retries`)
- **New (scripts):** `scripts/run_preparation.py` — reads paper extraction JSON from stdin, runs parallel preparation via `asyncio.gather()`, emits preparation summary JSON to stdout
- **Modified (scripts):** `scripts/srf_init.py` — added new config fields to inline `SRFConfig` construction
- **Modified (workflows):** `workflows/srf_forum.yaml` — `agent_preparation` step wired to `python scripts/run_preparation.py`
- **New (tests):** `tests/unit/test_llm_fallback.py` (6 tests), `test_agent_roster.py` (6), `test_paper_agent_preparation.py` (7), `test_moderator_challenger_preparation.py` (7), `test_preparation_orchestrator.py` (5), `test_run_preparation.py` (2)
- **New (tests/integration):** `test_llm_fallback_integration.py`, `test_preparation_integration.py`
- **Modified (pyproject.toml):** Added optional `anthropic` and `openai` dependency groups

### Decisions
- **`call_provider_directly()` is the tracker=None fallback only** — primary LLM path is always `tracker.execute()`; provider SDKs lazy-imported inside function body so module imports cleanly without SDKs installed
- **`LLMError` wraps provider exceptions** — prevents provider-specific exceptions leaking into caller code; carries status code context for debugging
- **`list[PaperContent]` directly in `build_roster()`** — no ExtractionResult wrapper; simpler contract confirmed before implementation
- **`{memory_block}` slot in all preparation prompts** — always empty string in this epic; Epic 2 populates without template changes
- **Paper text truncated at sentence boundary** — `_budget_paper_text()` finds the last `.`/`!`/`?` at or before `SRF_PAPER_TOKEN_BUDGET` chars; logs WARNING with arxiv_id and chars_dropped
- **Moderator failure aborts; Challenger degrades gracefully** — Moderator is the routing control plane; Challenger is valuable but not structurally required
- **Moderator and Challenger receive summaries/abstracts only** — not full paper text; keeps token usage proportional to role
- **`asyncio.gather(return_exceptions=True)`** — all preparations fan out concurrently; exceptions collected and processed per-agent
- **`paper_token_budget` and `max_prep_retries` added to SRFConfig** — from `SRF_PAPER_TOKEN_BUDGET` (default 80000) and `SRF_MAX_PREP_RETRIES` (default 3) env vars
- **`ALL_PROMPTS` aggregated in `src/srf/prompts/__init__.py`** — single import point for `srf_init.py` prompt registration

### Issues & Resolution
- ruff auto-fix (SIM117) corrupted two tests by merging `with patch(...)` and `with pytest.raises(...)` blocks — fixed by combining into single `with (...)` using parenthesised form
- B905 `zip()` without `strict=` — fixed by adding `strict=True` to `zip()` calls in orchestrator and test
- `SRFConfig` field addition broke existing tests using inline construction — updated `test_llm_fallback.py`, `srf_init.py` to include `paper_token_budget` and `max_prep_retries`

### Next Steps
- [ ] Story 1.1.3 — `scripts/validate_and_stage_forum.py`
- [ ] Story 1.1.4 — Three OpenClaw Skills (SKILL.md files)
- [ ] Story 1.1.5 — `.github/workflows/ci.yml` + `.env.example` update
- [ ] Epic 6: Debate Engine: Core Discussion Loop (depends on Epic 5 complete — ✓)

---

## [2026-03-18] - Epic 1.1 Stories 1.1.1–1.1.2: Runtime Infrastructure GREEN

### Summary
- Epic 1.1, Stories 1.1.1 and 1.1.2 — all GREEN; 118 unit tests pass, 4 skipped
- **New (config):** `railway.toml`, `config/openclaw.json`, `config/exec-approvals.json`
- **New (scripts):** `scripts/srf_init.py` — validates required env vars, creates workspace subdirs, builds PromptLedger tracker, registers prompts; idempotent; exits 1 on missing required vars
- **New (tests):** `tests/unit/test_runtime_deps.py` (11 tests, 1 skipped), `tests/unit/test_srf_init.py` (6 tests)
- **Modified:** `pyproject.toml` (+`tomli>=2.0.0; python_version < '3.11'`)
- Commits: `b3545af` (Story 1.1.1), this commit (Story 1.1.2)

### Decisions
- **OpenClaw is Node.js** — deployed via Railway one-click template; `railway.toml` adds Lobster install step (`npm install -g @clawdbot/lobster`) and healthcheck config
- **`OPENCLAW_WORKSPACE_DIR`** replaces old `SRF_WORKSPACE_ROOT` as the primary workspace env var for the init script; `srf.config.SRFConfig` retains `SRF_WORKSPACE_ROOT` for the Python agent runtime
- **Python in exec-approvals, not safeBins** — OpenClaw docs exclude interpreters from `safeBins`; Python paths must be in `exec-approvals.json` allowlist instead
- **`srf_init.py` uses subprocess-compatible output** — both structlog (stderr) and explicit `print("SRF init complete")` (stdout) so tests can detect success in either stream
- **Tests use Python 3.11** — `srf` package requires Python 3.11+; the Anaconda 3.9 env cannot install it; tests must be run with `py -3.11 -m pytest`

### Issues & Resolution
- `tomllib` import failed on Python 3.9 — fixed with `try: import tomllib except ImportError: import tomli as tomllib` + `tomli` dev dep
- `import srf_init` in test_srf_init_calls_register_prompts always failed (scripts/ not on sys.path) — removed; only `importlib.util.spec_from_file_location` approach remains
- ruff F401/I001 in test file — fixed by removing unused `json`, `AsyncMock`, `os` imports and running `ruff --fix`
- pip backtracking in Python 3.9 Anaconda env — `srf` requires 3.11+; install via `py -3.11 -m pip install -e ".[dev]"`

### Next Steps
- [ ] Story 1.1.3 — `scripts/validate_and_stage_forum.py`
- [ ] Story 1.1.4 — Three OpenClaw Skills (SKILL.md files)
- [ ] Story 1.1.5 — `.github/workflows/ci.yml` + `.env.example` update

---

## [2026-03-18] - Epic 4 Complete: Workspace Management & Paper Extraction

### Summary
- Epic 4, Stories 4.1–4.4 — all GREEN; 102 unit tests pass, 3 skipped (Windows chmod)
- **New (src):** `src/srf/workspace/{__init__,models,init}.py`; `src/srf/extraction/{__init__,models,fetcher,extractor}.py`
- **New (scripts):** `scripts/run_workspace_setup.py`, `scripts/run_paper_extraction.py`
- **New (workflows):** `workflows/srf_forum.yaml` — full 9-step skeleton; workspace_setup and paper_extraction fully wired, phases 6–15 stubbed
- **New (tests):** `test_workspace_init.py`, `test_paper_fetcher.py`, `test_paper_extractor.py`, `test_run_workspace_setup.py`, `test_run_paper_extraction.py`; `tests/fixtures/papers/_builders.py`; integration stubs for fetcher and Lobster
- **Modified:** `src/srf/config.py` (+`arxiv_delay_seconds`, `min_papers`); `pyproject.toml` (+`pdfplumber`, `fpdf2`, `pyyaml`); `tests/unit/test_config.py`
- Commit: `9ae90e1`

### Decisions
- **`papers/` added to workspace subdirectories** — fetcher writes to `workspace_path/papers/`; cleaner to create it with the workspace than have the fetcher create it on demand
- **`sleep_fn` injected into fetcher** — makes rate-limit delay and retry sleep deterministic in unit tests without real waits; `asyncio.sleep` is the production default
- **Retry only on 429/5xx** — 404 means the paper doesn't exist; retrying is pointless; 429/500–504 are transient
- **`pdfplumber` over `pypdf`** — handles column layouts and academic PDF formatting more reliably; image-only PDFs (no embedded text) flagged as `extraction_status="image_only"` rather than silent empty string
- **Abstract heuristic** — finds "Abstract" or "Abstract:" header line, captures following paragraph until next short title-case line; simple but reliable for well-formatted PDFs
- **Scripts route logs to stderr** — `configure_logging(stream=sys.stderr)` called at startup so structlog output doesn't pollute the JSON stdout that Lobster reads
- **`UP035`/`UP017` ruff rules ignored** — `typing.Callable` and `timezone.utc` are idiomatic with class-level datetime imports; rules added to `[tool.ruff.lint] ignore`
- **Workflow YAML is a skeleton** — all 9 steps from the topology are present; only workspace_setup and paper_extraction are fully wired; subsequent epics MODIFY this file to replace `echo placeholder` stubs

### Issues & Resolution
- structlog defaulted to stdout, corrupting Lobster JSON output — fixed by calling `configure_logging(stream=sys.stderr)` at the top of each script's `main()`
- `datetime.UTC` alias is Python 3.11+ module-level access, not accessible as `datetime.datetime.UTC` with class import — reverted to `timezone.utc`

### Lessons Learned
- Scripts that write JSON to stdout must configure all logging to stderr before importing any library code that logs at module level

### Next Steps
- [ ] Epic 5: Agent Preparation Phase (depends on Epic 4 complete — ✓)
- [ ] Wire `call_provider_directly()` in Epic 5 Story 5.1 (referenced stub from Epic 3)
- [ ] Integration test for real arXiv fetch: `pytest tests/integration/test_paper_fetcher_integration.py -v` (requires `SRF_RUN_INTEGRATION=1`)

---

## [2026-03-18] - Git Repository Initialized

### Summary
- Initialized git repository; created initial commit `d84a316` capturing all work from Epics 1 and 3
- 69 files, 10 499 insertions
- Added `.ruff_cache/` and `.claude/settings.local.json` to `.gitignore`

### Decisions
- Single initial commit rather than reconstructed history — no prior VCS existed
- `.claude/settings.local.json` excluded (local tool config, not project state)

### Issues & Resolution
- No prior git history existed; progress_tracker bootstrapped from file state and epic documents

### Lessons Learned
- Initialize git at project start, not after Epics 1–3 are complete

### Next Steps
- [ ] Create remote repository and push
- [ ] Begin Epic 4: Workspace Management & Paper Extraction

---

## [2026-03-17] - Epic 3 Complete: Newsletter Parsing & Forum Config Generation

### Summary
- Epic 3, Stories 3.1–3.5 — all GREEN
- **New files (src):** `src/srf/newsletter/__init__.py`, `models.py`, `parser.py`, `clustering.py`, `config_generator.py`, `persistence.py`; `src/srf/mcp/__init__.py`, `server.py`, `tools.py`; `src/srf/prompts/newsletter.py`
- **New files (scripts):** `scripts/parse_newsletter.py`
- **New files (tests):** `tests/unit/test_newsletter_parser.py`, `test_newsletter_clustering.py`, `test_newsletter_config_generator.py`, `test_newsletter_persistence.py`, `test_mcp_tools.py`; `tests/fixtures/newsletters/` (4 fixture files + `_builders.py`)
- **Modified:** `src/srf/prompts/__init__.py`, `scripts/validate_prompts.py`
- Two LLM-backed prompts registered: `newsletter.paper_clustering`, `newsletter.framing_question`
- Unit test suite passes; integration tests (`test_parse_newsletter_cli.py`, `test_mcp_trigger.py`) require live env vars and skip when absent

### Decisions
- **LLM for clustering, not keyword matching** — newsletter author writes tension axes and paper summaries in different vocabulary; semantic mapping via a single structured prompt is the only reliable approach
- **Two LLM calls per newsletter run, not per paper** — clustering is one call mapping all papers to all axes; framing is one call per candidate config; token cost is O(newsletter) not O(papers)
- **`tracker.execute()` for both LLM calls** — PromptLedger makes the provider call and auto-creates the span; `SpanPayload` construction removed from call sites
- **arXiv ID as paper identity key** — all URL variants normalised to bare `NNNN.NNNNN`; non-arXiv URLs preserved verbatim with `source="other"` and a warning
- **Candidate configs are drafts, not live forums** — pipeline stops after `save_candidate_configs()`; no `forum_id` assigned until editorial approval (Epic 8)
- **MCP trigger stops at candidate generation** — enforces the human gate between Epic 3 and Epic 4; Claude Desktop receives config summaries with `status="awaiting_approval"`
- **`call_provider_directly()` stub for `tracker=None` path** — full implementation deferred to Epic 5 Story 5.1; clustering and config generation both reference it but it is not yet wired to a real provider

### Issues & Resolution
- PromptLedger CR-001 (`PL_ChangeRequest_1.md`) raised during this epic: the existing Mode 2 pattern required ~20 lines of boilerplate per call site and did not support `tracker.execute()`. CR-001 requests a unified `execute()` method on `AsyncPromptLedgerClient` — this was adopted as the call pattern for all subsequent epics. CLAUDE.md updated to reflect `tracker.execute()` as the primary call pattern.

### Lessons Learned
- Defining the `tracker.execute()` contract before implementing call sites saved significant refactoring
- Fixture Markdown files should be the minimum valid input per scenario — full newsletter copies are too large and mask parser edge cases

### Next Steps
- [ ] Epic 4: Workspace Management & Paper Extraction (depends on Epic 3 complete — ✓)
- [ ] Wire `call_provider_directly()` in Epic 5 Story 5.1

---

## [2026-03-17] - Epic 1 Complete: Foundation — Scaffold, Config, Logging, Observability

### Summary
- Epic 1, Stories 1.1–1.6 — all GREEN
- **New files (src):** `src/srf/__init__.py`, `py.typed`, `config.py`, `logging.py`, `observability.py`, `spans.py`, `prompts/__init__.py`
- **New files (scripts):** `scripts/validate_prompts.py`
- **New files (tests):** `tests/unit/test_scaffold.py`, `test_config.py`, `test_logging.py`, `test_observability.py`, `test_spans.py`, `test_validate_prompts.py`; `tests/integration/test_observability_integration.py`; `tests/fixtures/conftest.py`
- **New project files:** `pyproject.toml`, `Makefile`, `.env.example`, `.gitignore`
- All required environment variables documented in `.env.example`
- `ruff check src/ tests/` exits 0

### Decisions
- **Provider-agnostic LLM config** — `SRF_LLM_PROVIDER` / `SRF_LLM_MODEL` / `SRF_LLM_API_KEY` are the only LLM-related required vars; no provider SDK imported unconditionally; provider clients instantiated at startup based on `SRF_LLM_PROVIDER`
- **PromptLedger Mode 2, not Mode 1** — SRF calls the configured LLM provider and logs spans after the fact; Mode 1 was rejected because SRF requires full control of message construction and streaming
- **`tracker=None` injection over module-level singleton** — every function that calls PromptLedger accepts `tracker: AsyncPromptLedgerClient | None` as a parameter; makes unit testing trivially free of network calls
- **Span IDs through workflow state, not `contextvars`** — Railway sleep/wake cycles do not preserve `contextvars` across invocations; all `trace_id` and `parent_span_id` values stored in the state dict
- **`structlog` over stdlib `logging`** — JSON-lines natively, per-coroutine context binding, no thread-local issues; `print()` banned in production paths and enforced by an AST-scanning test in `test_logging.py`
- **`ConfigurationError` at startup for missing vars** — fail loudly at boot rather than silently at runtime; `SRF_LOG_LEVEL` defaults to `INFO`, `SRF_WORKSPACE_ROOT` defaults to `/data/workspace`
- **PromptLedger requires both vars or neither** — partial config (`PROMPTLEDGER_API_URL` set without `PROMPTLEDGER_API_KEY`) raises `ConfigurationError`

### Issues & Resolution
- None — Epic 1 is self-contained with no external dependencies

### Lessons Learned
- AST-scanning test for `print()` calls (`test_logging.py`) catches production logging violations at test time rather than code review
- `structlog.testing.capture_logs()` makes logging unit tests trivially fast with no I/O

### Next Steps
- [ ] Epic 3: Newsletter Parsing & Forum Config Generation (depends on Epic 1 — ✓)
