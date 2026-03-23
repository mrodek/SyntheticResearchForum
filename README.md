# Synthetic Research Forum

**An intellectual execution engine that makes AI agents argue about science.**

SRF takes a research newsletter, extracts papers from arXiv, assembles a cast of AI debaters, and runs a structured multi-agent forum — producing a transcript, synthesis, and evaluation artifact. Every run is deterministic, reproducible, and fully observable.

---

## What It Does

Each week a newsletter arrives containing research papers on competing ideas. SRF:

1. **Parses the newsletter** — extracts papers, identifies intellectual tensions, generates candidate forum configs
2. **Waits for editorial approval** — a human gates which forum gets run
3. **Fetches the papers** — pulls PDFs from arXiv, extracts full text
4. **Prepares the agents** — each AI agent reads its assigned paper and forms a position, arguments, and anticipated objections before the debate begins
5. **Runs the debate** — a structured multi-phase discussion with a Moderator, up to three Paper Agents (each defending a paper), and a Challenger
6. **Synthesizes** — produces structured agreements, tensions, and unresolved questions
7. **Evaluates** — scores agent contributions and synthesis quality
8. **Publishes** — outputs a canonical JSON artifact, a speaker-attributed transcript, and a screenplay-format Markdown file

The result is a rigorous, grounded epistemic discussion — not a summary, not a chatbot conversation.

---

## Agent Roles

| Agent | Role |
|---|---|
| **Moderator** | Frames the debate, enforces rigor, drives convergence |
| **Paper Agent × N** | Defends an assigned paper — argues from its methods, results, and limitations |
| **Challenger** | Applies structured skeptical pressure — surfaces hidden assumptions, forces cross-paper comparisons |
| **Guardrail** | Silent real-time evaluator — fires on fabricated evidence, grounding violations, evasion, tone drift |
| **Synthesis** | Produces structured post-debate analysis — no new claims permitted |
| **Evaluator** | Scores agent contributions; outputs provisional scorecard for editorial adjustment |

---

## Architecture

```
Newsletter (Markdown)
    │
    ▼
┌──────────────────────────────────────────────────────────────┐
│  Lobster Workflow Engine  (15-phase lifecycle)               │
│                                                              │
│  Phase 1–3:   Newsletter Parsing → Candidate Config          │
│  Phase 4:     Editorial Approval Gate  ◄── human gate        │
│  Phase 5:     Workspace Generation                           │
│  Phase 6:     Paper Extraction (arXiv → PDF → text)         │
│  Phase 7:     Agent Preparation (parallel, with retries)     │
│  Phase 8–12:  Debate (Opening → Position → Challenge →       │
│               Discussion → Closing)                          │
│  Phase 13:    Synthesis + Evaluation                         │
│  Phase 14:    Editorial Review Gate  ◄── human gate          │
│  Phase 15:    Publication                                     │
└──────────────────────────────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────────────────────────────┐
│  OpenClaw Gateway  (Node.js agent runtime)                   │
│  · Debate loop orchestration                                 │
│  · MCP tool transport                                        │
│  · Guardrail enforcement                                     │
│  · Transcript append-only writes                             │
└──────────────────────────────────────────────────────────────┘
    │
    ├──► PromptLedger (prompt registry · trace lineage · cost telemetry)
    └──► /data/workspace/forum/{forum_id}/ (persistent volume)
              preparation/  transcripts/  synthesis/  logs/
```

**Deployment:** Single Railway service. Survives sleep/wake cycles. All state lives on the persistent volume.

**LLM provider:** Runtime configuration — `SRF_LLM_PROVIDER` / `SRF_LLM_MODEL` / `SRF_LLM_API_KEY`. Works with Anthropic, OpenAI, or any provider. Switching providers is an environment variable change, not a code change.

---

## Key Design Principles

- **Deterministic** — every forum run is reproducible from its config + prompt versions + memory snapshot
- **Preparation-driven** — agents read and form positions before the first turn; cold debates are explicitly forbidden
- **Append-only transcript** — turns are never modified; guardrail alerts attach as metadata without altering the record
- **Editorially gated** — no forum runs without human approval; no memory is written without editorial review
- **Provider-agnostic** — no provider SDK is hardcoded; the entire LLM integration is a runtime config
- **Full observability** — every LLM call produces a PromptLedger span; token cost and trace lineage are recorded for every run

---

## Stack

| Component | Technology |
|---|---|
| Agent runtime | OpenClaw Gateway (Node.js) |
| Workflow orchestration | Lobster |
| Deployment substrate | Railway |
| LLM observability | PromptLedger (Mode 2 — Code-Based Tracking) |
| Application language | Python 3.11+ |
| PDF extraction | pdfplumber |
| Structured logging | structlog (JSON lines) |
| Testing | pytest + TDD (all production code is test-first) |

---

## Project Status

| Epic | Description | Status |
|---|---|---|
| 1 | Foundation — scaffold, config, logging, observability | ✅ Complete |
| 1.1 | Runtime infrastructure — OpenClaw, Lobster, Railway | ✅ Complete |
| 3 | Newsletter parsing & forum config generation | ✅ Complete |
| 4 | Workspace management & paper extraction | ✅ Complete |
| 5 | Agent preparation phase | ✅ Complete |
| 6B | Debate engine — OpenClaw native (skill + bridge) | ✅ Complete |
| 7 | Synthesis, evaluation & post-debate processing | 🔲 Next |
| 8 | Editorial review, policy proposals & publication | 🔲 Planned |
| 11 | PromptLedger proxy — per-turn debate telemetry | 🔲 Planned |
| 9 | Observability, cost reporting & reliability | 🔲 Planned |
| 2 | Agent memory (role-scoped, editorially gated) | 🔲 After first complete run |

**Current test suite:** 210 unit tests, 5 skipped (Windows chmod + missing optional deps), 0 failures.

---

## Deployment

SRF runs on Railway using a two-repo model:

| Repo | Role |
|---|---|
| `mrodek/clawdbot-railway-template` | Railway service source — builds and runs the OpenClaw Gateway |
| `mrodek/SyntheticResearchForum` | SRF codebase — cloned to `/data/srf` on the persistent volume at startup |

### How it works

The OpenClaw template's wrapper runs `/data/workspace/bootstrap.sh` on every startup. This script:
1. Clones (or pulls) the SRF repo to `/data/srf`
2. Installs SRF Python dependencies into a persistent venv at `/data/venv`
3. Copies OpenClaw skills to `/data/workspace/skills/`

All state lives on the Railway volume at `/data` and survives redeploys.

### First-time setup

See `Requirements/Railway/RAILWAY_SETUP_GUIDE.md` for the full step-by-step guide. Summary:

1. Fork `vignesh07/clawdbot-railway-template` → connect fork to Railway service
2. Add volume at `/data`, enable HTTP Proxy on port `8080`
3. Set required environment variables (see `.env.example`)
4. Run `/setup` wizard at `https://<service>.up.railway.app/setup`
5. Create `/data/workspace/bootstrap.sh` via the OpenClaw Chat exec tool
6. Redeploy → verify `/data/srf` and `/data/venv` exist
7. Run `srf_init.py` to confirm the service is ready

### Running the pipeline

All pipeline interactions happen via the OpenClaw Chat (`/openclaw`). The pipeline has two entry points: a human-triggered newsletter parse, and the full automated Lobster workflow.

#### Step 1 — Initialise the service

On first startup (or after a redeploy), confirm the service is ready:

```bash
# Via OpenClaw exec tool:
/data/venv/bin/python /data/srf/scripts/srf_init.py
```

This validates the environment, initialises the workspace directory structure, and registers all prompts with PromptLedger.

#### Step 2 — Parse a newsletter

Drop a newsletter Markdown file into `/data/srf/.newsletter/` on the volume (via OpenClaw's file tools or exec), then parse it:

```bash
# Via OpenClaw exec tool:
/data/venv/bin/python /data/srf/scripts/parse_newsletter.py \
  --file /data/srf/.newsletter/<newsletter-file>.md \
  --output-dir /data/workspace/newsletters
```

This produces candidate forum configs in `/data/workspace/newsletters/`. One config is selected per newsletter, pending editorial approval.

#### Step 3 — Stage and approve the forum

Use the `review_forum_debate_format` skill in OpenClaw Chat:

```
/review_forum_debate_format
```

The skill presents the candidate config for editorial review. On approval it stages the forum and invokes the Lobster pipeline. On rejection it writes the decision and stops.

#### Step 4 — Lobster pipeline (automated)

Once staged, Lobster executes the remaining phases automatically. Each phase is a Python script invoked by Lobster's exec tool:

| Phase | Script | Output |
|---|---|---|
| Workspace setup | `run_workspace_setup.py` | `/data/workspace/forum/{forum_id}/` directory structure |
| Paper extraction | `run_paper_extraction.py` | Full paper text in `preparation/papers/` |
| Agent preparation | `run_preparation.py` | Per-agent `preparation/{agent_id}/artifact.json` |
| Debate bridge | `run_debate_bridge.py` | Triggers OpenClaw debate skill; polls for `DEBATE_CLOSED` sentinel |
| Synthesis & evaluation | *(Epic 7 — not yet implemented)* | `synthesis.json`, `evaluation.json` |
| Publication | *(Epic 8 — not yet implemented)* | `canonical_artifact.json`, `transcript.md` |

#### Step 5 — Monitor the debate

While the debate is running, the transcript appends to:

```
/data/workspace/forum/{forum_id}/transcripts/transcript.jsonl
```

Read it live via the OpenClaw exec tool:

```bash
tail -f /data/workspace/forum/{forum_id}/transcripts/transcript.jsonl
```

The debate closes when the Moderator writes a `DEBATE_CLOSED` sentinel line. The bridge script validates the transcript and writes its output JSON to Lobster for the next phase.

#### Step 6 — Editorial review (post-debate)

Once synthesis and evaluation are complete (Epic 7), the `approve_editorial_review` skill presents the evaluation scorecard for editorial review before publication.

---

### Environment variables

**OpenClaw Gateway (set via Railway Variables or `/setup` wizard):**

| Variable | Required | Description |
|---|---|---|
| `SETUP_PASSWORD` | Yes | Protects `/setup` and `/openclaw` |
| `PORT` | Yes | Must be `8080` |
| `OPENCLAW_STATE_DIR` | Yes | `/data/.openclaw` |
| `OPENCLAW_WORKSPACE_DIR` | Yes | `/data/workspace` — SRF workspace root |
| `OPENCLAW_GATEWAY_TOKEN` | Recommended | Secures MCP + webhook endpoints |
| `OPENCLAW_GATEWAY_URL` | Yes | Base URL of this service (e.g. `https://<service>.up.railway.app`) |

**SRF Python runtime (set via Railway Variables):**

| Variable | Required | Description |
|---|---|---|
| `SRF_LLM_PROVIDER` | Yes | `anthropic` or `openai` |
| `SRF_LLM_MODEL` | Yes | e.g. `claude-haiku-4-5-20251001` for testing, `claude-sonnet-4-6` for production |
| `SRF_LLM_API_KEY` | Yes | Provider API key |
| `PROMPTLEDGER_API_URL` | Optional | Enables observability (both vars or neither) |
| `PROMPTLEDGER_API_KEY` | Optional | Project-scoped PromptLedger key |

**Debate tuning (optional — all have defaults):**

| Variable | Default | Description |
|---|---|---|
| `SRF_MAX_TOTAL_TURNS` | `30` | Hard cap on total debate turns |
| `SRF_MAX_TURNS_PER_AGENT` | `8` | Max turns any single agent may take |
| `SRF_MAX_ROUNDS` | `4` | Max complete discussion rounds |
| `SRF_DEBATE_POLL_TIMEOUT` | `600` | Seconds to wait for `DEBATE_CLOSED` before failing |
| `SRF_DEBATE_POLL_INTERVAL` | `10` | Seconds between transcript poll attempts |
| `SRF_MAX_PREP_RETRIES` | `3` | Retry attempts for failed agent preparation |
| `SRF_MIN_AGENTS` | `2` | Minimum viable Paper Agents required to run |
| `SRF_MIN_PAPERS` | `2` | Minimum successfully extracted papers required |
| `SRF_ARXIV_DELAY_SECONDS` | `3` | Rate-limit delay between arXiv fetches |

See `.env.example` for the full list.

---

## Repository Layout

```
src/srf/
  config.py          — environment-based configuration, validated at startup
  logging.py         — structlog JSON setup
  observability.py   — PromptLedger tracker construction
  prompts/           — all prompt templates as Python constants
  newsletter/        — newsletter parser, clustering, config generator
  workspace/         — forum workspace initialisation
  extraction/        — arXiv fetcher + PDF text extractor
  llm/               — provider fallback client (tracker=None path only)
  agents/            — roster, preparation, orchestrator

scripts/
  srf_init.py                — startup: validate env, init workspace, register prompts
  parse_newsletter.py        — CLI: parse newsletter → candidate forum configs
  run_workspace_setup.py     — Lobster step: create forum workspace
  run_paper_extraction.py    — Lobster step: fetch + extract papers
  run_preparation.py         — Lobster step: parallel agent preparation
  prepare_debate_context.py  — Lobster step: build debate_context.json from state + artifacts
  run_debate_bridge.py       — Lobster step: trigger OpenClaw debate, poll sentinel, validate
  validate_transcript.py     — validate JSONL transcript; returns TranscriptSummary
  validate_prompts.py        — CI: assert no unregistered prompt changes

workflows/
  srf_forum.yaml     — Lobster workflow definition (15-phase lifecycle)

skills/
  trigger_newsletter_forum/    — skill: parse newsletter + generate forum configs
  review_forum_debate_format/  — skill: editorial approval gate before debate
  approve_editorial_review/    — skill: editorial review gate after synthesis
  run_forum_debate/            — skill: OpenClaw-native multi-agent debate engine
    SKILL.md       — orchestration spec (phases, turn protocol, limits, error handling)
    MODERATOR.md   — Moderator role document
    PAPER_AGENT.md — Paper Agent role document
    CHALLENGER.md  — Challenger role document
    GUARDRAIL.md   — Guardrail evaluator role document

tests/
  unit/              — fast, offline, tracker=None
  integration/       — live provider / service calls (opt-in via env var)
  fixtures/          — shared builders and test data
```

---

## Development

```bash
# Install (requires Python 3.11+)
py -3.11 -m pip install -e ".[dev]"

# Run unit tests
py -3.11 -m pytest tests/unit -v

# Lint
py -3.11 -m ruff check src/ tests/ scripts/

# Integration tests (requires live env vars)
SRF_LLM_PROVIDER=anthropic SRF_LLM_MODEL=claude-haiku-4-5-20251001 \
SRF_LLM_API_KEY=sk-... \
py -3.11 -m pytest tests/integration -v
```

All production code is written test-first. No exceptions.

---

## Outputs

A completed forum run produces:

- **`canonical_artifact.json`** — full structured record: config, agents, transcript, synthesis, scores
- **`transcript.json`** — speaker-attributed turn-by-turn debate record
- **`transcript.md`** — screenplay-format human-readable version (podcast pipeline ready)
- **`synthesis.json`** — structured agreements, tensions, unresolved questions
- **`evaluation.json`** — provisional contribution scores per agent

---

*Built with strict TDD. Every behaviour is tested before it is implemented.*
