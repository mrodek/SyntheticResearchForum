# SRF Progress

## Epic Delivery Sequence

| Epic | Title | Status | Depends On |
|---|---|---|---|
| 1 | Foundation | Complete | — |
| 1.1 | Runtime Infrastructure — Gateway, Lobster, OpenClaw & Railway | Complete | All 5 stories GREEN |
| 3 | Newsletter Parsing & Config Generation | Complete | Epic 1 |
| 4 | Workspace Management & Paper Extraction | Complete | Epics 1, 3 |
| 5 | Agent Preparation Phase | Complete | |
| 6 | Debate Engine: Core Discussion Loop | Not Started | Epics 1, 5 — epic defined |
| 7 | Synthesis, Evaluation & Post-Debate Processing | Not Started | Epics 1, 6 |
| 8 | Editorial Review, Policy Proposals & Publication | Not Started | Epics 1, 7 |
| 9 | Observability, Cost Reporting & Operational Reliability | Not Started | Epics 1, 6, 7 (drift story also needs Epic 2) |
| 2 | Agent Memory | Not Started | Epics 1, 5, 6, 7 — begins after first complete forum run |
| 10 | Prompt Governance & Longitudinal Quality Tracking | Not Started | Epics 1, 2, 7, 8 |

> **Note:** Epic 2 is sequenced after Epics 1–8. The system runs correctly without memory on the first forum run — all injection points return empty blocks gracefully. Epic 2 begins once the first complete run has established the upstream contracts it depends on.

---

## Active Sprint — Epic 6: Debate Engine

| Story | Title | Status | Notes |
|---|---|---|---|
| 1.1.5 | CI Pipeline (GitHub Actions) | Not Started | `.github/workflows/ci.yml` never created — story was incorrectly marked Complete |
| 6.x | Debate Engine: Core Discussion Loop | Not Started | Depends on Epic 5 complete — ✓ |

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
