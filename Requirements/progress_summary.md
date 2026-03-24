# SRF Progress

## Epic Delivery Sequence

| Epic | Title | Status | Depends On |
|---|---|---|---|
| 1 | Foundation | Complete | — |
| 1.1 | Runtime Infrastructure — Gateway, Lobster, OpenClaw & Railway | Complete | All 5 stories GREEN |
| 3 | Newsletter Parsing & Config Generation | Complete | Epic 1 |
| 4 | Workspace Management & Paper Extraction | Complete | Epics 1, 3 |
| 5 | Agent Preparation Phase | Complete | |
| 6 | Debate Engine: Core Discussion Loop | **Skipped** | Superseded by Epic 6B (OpenClaw-native). Decision confirmed 2026-03-22. |
| 7 | Synthesis, Evaluation & Post-Debate Processing | Not Started | Epics 1, 6B |
| 8 | Editorial Review, Policy Proposals & Publication | Not Started | Epics 1, 7 |
| 11 | PromptLedger Proxy Infrastructure | Not Started | Epic 6B complete — prerequisite for Epic 9 turn-level telemetry |
| 9 | Observability, Cost Reporting & Operational Reliability | Not Started | Epics 1, 6B, 7, 11 (drift story also needs Epic 2) |
| 2 | Agent Memory | Not Started | Epics 1, 5, 6B, 7 — begins after first complete forum run |
| 10 | Prompt Governance & Longitudinal Quality Tracking | Not Started | Epics 1, 2, 7, 8 |

> **Note:** Epic 2 is sequenced after Epics 1–8. The system runs correctly without memory on the first forum run — all injection points return empty blocks gracefully. Epic 2 begins once the first complete run has established the upstream contracts it depends on.
>
> **Note:** Epic 6 (Python-first debate engine) was skipped in favour of Epic 6B (OpenClaw-native). As a consequence, per-turn PromptLedger telemetry requires proxy infrastructure (Epic 11) before Epic 9 observability stories are meaningful. Phase-level spans via the bridge script remain available without the proxy.

---

## Active Sprint — Epic 6B: Debate Engine (OpenClaw Native)

| Story | Title | Status | Notes |
|---|---|---|---|
| 1.1.5 | CI Pipeline (GitHub Actions) | Not Started | `.github/workflows/ci.yml` never created — story was incorrectly marked Complete |
| 1.1.6 | update_srf Skill and Script | Superseded | Superseded by 1.1.7 — `update_srf.sh` cannot run as `openclaw` against root-owned `/data/srf`. Retained in repo for reference. |
| 1.1.7 | Entrypoint-owned git clone + simplified bootstrap | In Progress | `entrypoint.sh` SRF block + simplified `bootstrap.sh` — pending apply to template fork |
| 6B.1 | Debate Context Document | GREEN | `scripts/prepare_debate_context.py` — 8 tests passing |
| 6B.2 | Forum Debate Skill Documents | GREEN | SKILL.md + MODERATOR.md + PAPER_AGENT.md + CHALLENGER.md + GUARDRAIL.md — 12 tests passing |
| 6B.3 | Transcript Validator | GREEN | `scripts/validate_transcript.py` — 7 tests passing |
| 6B.4 | Bridge Script & Pipeline Integration | Complete | `scripts/run_debate_bridge.py` + workflow wired — 8 tests passing. BUG-004 fixed. |
| BUG-004 | srf_forum.yaml invalid input ref + relative paths | Complete | 2026-03-22. `$trigger.json` → `$LOBSTER_ARGS_JSON`; absolute paths; SKILL.md argsJson fix. |

---

## Deferred — Epic 2: Agent Memory

Sequencing decision: Epic 2 depends on Epics 5, 6, and 7 for its upstream contracts (agent prompt structures, behavioral signals, evaluation artifact format). It will be fully detailed and sequenced after the first complete forum run.

| Story | Title | Status | Notes |
|---|---|---|---|
| 2.1 | Memory Store Schema and Persistence Layer | Deferred | Begins after Epic 7 evaluation_block format is agreed |
| 2.2 | Memory Candidate Extraction | Deferred | Requires Epic 7 complete |
| 2.3 | Editorial Approval Interface | Deferred | Requires 2.2 |
| 2.4 | Memory Injection at Preparation | Deferred | Requires 2.2; format must align with Epic 5 prompts |
| 2.5 | Execution Metadata and Reproducibility Stamping | Deferred | Requires 2.4 |
| 2.6 | Memory Drift Detection | Deferred | Requires 2.1 |

---

## Completed

| Story | Title | Completed |
|---|---|---|
| 1.1 | Project Scaffold | 2026-03-17 |
| 1.2 | Configuration Module | 2026-03-17 |
| 1.3 | Structured Logging | 2026-03-17 |
| 1.4 | PromptLedger Observability Module | 2026-03-17 |
| 1.5 | Span Logging Utilities | 2026-03-17 |
| 1.6 | CI Prompt Validation Script | 2026-03-17 |
| 3.1 | Newsletter Parser | 2026-03-17 |
| 3.2 | Paper Candidate Clustering | 2026-03-17 |
| 3.3 | Forum Config Generation | 2026-03-17 |
| 3.4 | Candidate Config Persistence & CLI | 2026-03-17 |
| 3.5 | MCP Trigger Tool | 2026-03-17 |
| CR-001 | PromptLedger: tracker.execute() — unified execution client | 2026-03-18 |
| — | Epic 1 & 3 code aligned to tracker.execute() contracts | 2026-03-18 |
| 4.1 | Forum Workspace Initialisation | 2026-03-18 |
| 4.2 | arXiv Paper Fetcher | 2026-03-18 |
| 4.3 | PDF Text Extraction | 2026-03-18 |
| 4.4 | Lobster Step Scripts & Workflow Skeleton | 2026-03-18 |
| 1.1.1 | OpenClaw & Lobster Installation + Base Configuration | 2026-03-18 |
| 1.1.2 | SRF Initialisation Script | 2026-03-18 |
| 5.1 | Provider Fallback Client | 2026-03-19 |
| 5.2 | Agent Roster | 2026-03-19 |
| 5.3 | Paper Agent Preparation | 2026-03-19 |
| 5.4 | Moderator Briefing & Challenger Preparation | 2026-03-19 |
| 5.5 | Parallel Preparation Orchestration & CLI Script | 2026-03-19 |
| 1.1.3 | Forum Staging Script | 2026-03-19 |
| 1.1.4 | OpenClaw Skills (MCP Tools) | 2026-03-19 |

---

## Blocked / Deferred

| Item | Reason | Unblocked by |
|---|---|---|
| Epic 2 full story implementation | Upstream contracts (Epic 5 prompts, Epic 6 signals, Epic 7 artifact format) not yet fixed | Epics 5, 6, 7 complete |
| Epic 10 | Depends on Epic 2 and Epic 8 | Epic 2 complete |
