# The Research Gap - Field Notes

**Issue #3 : Agent Evaluation and the Measurement Problem**

---

## This Week's Signal

Five papers this week, arriving independently, converge on the same problem: the evaluation infrastructure for agentic systems is lagging behind deployment. The work on stochasticity in deep research agents, calibrated stress-testing of workflow metrics, and the homogenisation risk in model marketplaces all point to the same structural gap — we are building systems faster than we can reliably assess them. This is not a temporary inconvenience; it is an architectural risk that compounds as agents are granted more autonomy and longer task horizons. This issue also introduces a new Field Focus section on AI in the workplace — where two new empirical papers complicate the standard story of capability-driven adoption in ways worth understanding.

---

## Primary Signals

### 1. WorkflowPerturb: Calibrated Stress Tests for Evaluating Multi-Agent Workflow Metrics
**[arXiv:2602.17990](https://arxiv.org/abs/2602.17990v1)**

**Technical summary:** WorkflowPerturb constructs a controlled benchmark by applying three perturbation types — Missing Steps, Compressed Steps, and Description Changes — at varying severity levels across 4,973 golden workflows, producing 44,757 perturbed variants. The framework evaluates whether existing workflow metrics respond proportionally to degradation severity, using expected score trajectories and residuals as calibration signals. The result is a systematic way to audit whether a metric is actually sensitive to the things it claims to measure.

**Why it matters:** Most teams deploying multi-agent pipelines are using LLM-as-a-judge metrics without any principled understanding of how those metrics behave under failure conditions. WorkflowPerturb exposes a specific and underappreciated risk: a metric that looks reasonable on passing workflows may be nearly blind to partial failures. Before trusting any workflow evaluation score in production, you need to know its sensitivity profile. This paper gives you a method to find out.

---

### 2. Evaluating Stochasticity in Deep Research Agents
**[arXiv:2602.23271](https://arxiv.org/abs/2602.23271)**

**Technical summary:** The authors formalise Deep Research Agents as information acquisition Markov Decision Processes and identify three distinct sources of output variance: information acquisition (what the agent retrieves), information compression (how it summarises), and inference (how it reasons over compressed context). Ensemble-based query generation and structured output formatting reduce measured stochasticity by 22% without degrading research quality. The MDP framing is useful because it makes the variance sources tractable rather than treating non-determinism as an undifferentiated nuisance.

**Why it matters:** Variance in agentic outputs is not just a UX problem — it is an evaluation problem. If the same agent produces meaningfully different outputs on the same task across runs, then single-pass benchmark scores are unreliable. This paper provides both a diagnostic taxonomy and concrete mitigation strategies. Teams running research agents in production should be measuring run-to-run variance as a first-class metric, not an afterthought.

---

### 3. Impacts of Aggregation on Model Diversity and Consumer Utility
**[arXiv:2602.23293](https://arxiv.org/abs/2602.23293)**

**Technical summary:** The paper demonstrates formally that standard winrate metrics — the dominant evaluation currency in model marketplaces — create producer incentives toward homogenisation rather than specialisation. A proposed alternative, weighted winrate, rewards higher-quality answers and provably shifts incentives toward differentiation. The theoretical results are validated on empirical benchmark datasets.

**Why it matters:** This is a market-design paper with direct implications for anyone building on top of model APIs or running internal model selection processes. If your evaluation metric rewards average performance across a broad population, you will systematically select against models that are excellent on your specific use case. The mechanism described here also has implications for how AI platforms should structure leaderboards if they want to surface genuinely useful diversity rather than converging on a single dominant generalist.

---

### 4. ReqElicitGym: An Evaluation Environment for Interview Competence in Conversational Requirements Elicitation
**[arXiv:2602.18306](https://arxiv.org/abs/2602.18306v1)**

**Technical summary:** ReqElicitGym introduces 101 website requirements elicitation scenarios spanning 10 application types, an oracle user simulator, and a task evaluator to benchmark LLMs on their ability to conduct structured discovery conversations. Across seven models tested, current LLMs elicit fewer than half of users' implicit requirements (best IRE = 0.32), and their effective elicitation questions often emerge in later turns of the dialogue. Interaction and content requirements are moderately elicitable, but style-related requirements are consistently near zero across all models and settings. The framework enables reproducible, quantitative comparison without requiring human evaluators for each run.

**Why it matters:** Requirements elicitation is one of the highest-leverage tasks in software engineering — and one of the most interpersonally complex. The finding that current models recover less than half of implicit requirements is a direct constraint on how much autonomous software engineering work can be safely delegated. For teams building AI coding assistants or autonomous engineering agents, this benchmark surfaces a concrete capability ceiling that is not visible from standard code generation benchmarks.

---

### 5. Operational Agency: A Permeable Legal Fiction for Tracing Culpability in AI Systems
**[arXiv:2602.17932](https://arxiv.org/abs/2602.17932)**

**Technical summary:** The paper introduces Operational Agency (OA) as a legal fiction — not a claim about consciousness or intent — for attributing culpability in AI-related harms. The Operational Agency Graph (OAG) maps causal responsibility across developers, deployers, and users using observable system characteristics (goal-directedness, predictive processing, safety architecture) as proxies for legal concepts like intent and standard of care. Five case studies span tort, civil rights, constitutional law, and antitrust.

**Why it matters:** As agentic systems take consequential actions in the world, the question of who is responsible for failures is no longer theoretical. The OA framework is notable for being practically operable — it does not require resolving philosophical questions about AI consciousness, and it preserves human accountability throughout. Architects deploying autonomous agents in regulated domains should be mapping their systems against something like this framework now, before regulators or courts impose a less workable one.

---

## Supporting Evidence

- **VLA-Perf** ([arXiv:2602.18397](https://arxiv.org/abs/2602.18397v1)): First systematic inference performance study for Vision-Language-Action models across on-device, edge, and cloud deployments — 15 concrete takeaways for teams designing real-time robot systems.
- **OmniGAIA** ([arXiv:2602.22897](https://arxiv.org/abs/2602.22897v1)): Benchmark and foundation agent for omni-modal tasks (video, audio, image) with multi-turn tool use; hindsight-guided tree exploration is a notable training contribution.
- **CXReasonAgent** ([arXiv:2602.23276](https://arxiv.org/abs/2602.23276)): Evidence-grounded diagnostic agent for chest X-rays with a 1,946-dialogue benchmark; demonstrates that tool-augmented reasoning outperforms raw vision-language models on clinical faithfulness.
- **AI-Wrapped** ([arXiv:2602.18415](https://arxiv.org/abs/2602.18415v1)): Naturalistic LLM usage study across 82 users and 48,495 conversations — surfaces participant hesitancy around data sharing as a structural obstacle to alignment research infrastructure.
- **ChatQDA / Qualitative Coding** ([arXiv:2602.18352](https://arxiv.org/abs/2602.18352v1)): On-device LLM framework for sensitive qualitative research data; users exhibited "conditional trust" — accepting surface extraction but questioning interpretive depth, even with local deployment.
- **Generated Reality** ([arXiv:2602.18422](https://arxiv.org/abs/2602.18422v1)): Human-centric XR world model conditioned on head and hand pose; diffusion transformer distilled into a causal interactive system with measurable improvements in perceived control.
- **BEV Segmentation Self-Supervised Pretraining** ([arXiv:2602.18066](https://arxiv.org/abs/2602.18066v1)): +2.5pp mIoU over fully supervised baseline using 50% of annotated data and two-thirds of training time — a practical data-efficiency result for autonomous driving teams.
- **SLMs for Leader-Follower Interaction** ([arXiv:2602.23312](https://arxiv.org/abs/2602.23312)): Qwen2.5-0.5B achieves 86.66% accuracy at 22.2ms latency for role classification in human-robot interaction — a useful edge deployment reference point.
- **Asta Interaction Dataset** ([arXiv:2602.23335](https://arxiv.org/abs/2602.23335)): 200,000+ queries from AI research tool users show increasing query complexity with experience — users converge on treating the system as a collaborative partner rather than a search engine.

---

## Pattern Watch

**Evaluation infrastructure is the current bottleneck, not model capability.** Five papers this week — WorkflowPerturb, ReqElicitGym, the stochasticity study, the aggregation/winrate paper, and OmniGAIA — are all fundamentally about the inadequacy of existing evaluation methods rather than proposing new model architectures. The field appears to be in a phase where capability has outrun measurement, and the research community is catching up. For practitioners, this means that benchmark scores on agentic tasks should be treated with more scepticism than usual, and that investing in internal evaluation infrastructure is likely to have higher returns than chasing the next model release.

**Trust is emerging as a first-class design variable.** The ChatQDA study's finding of "conditional trust," the AI-Wrapped study's participant hesitancy around data sharing, and the Asta dataset's observation of users treating AI as a collaborative partner all point to a consistent pattern: users are developing nuanced, context-dependent trust models for AI systems, not binary accept/reject stances. This has direct implications for how AI-assisted tools should surface uncertainty, explain their reasoning, and communicate the boundaries of their competence. Systems that ignore this dynamic will face adoption ceilings that are not visible in capability benchmarks.

---

## Articles & Commentary

- **"Agents Are Easy. Operating Them Isn't."** — LAI #116 ([link](https://pub.towardsai.net/lai-116-agents-are-easy-operating-them-isnt-be78313c579a)) makes the same argument as this week's research cluster from a practitioner angle: inference economics, function-calling at scale, and the operational gap between demo and production.
- **"The wow demo trap is killing LLM projects"** ([link](https://pub.towardsai.net/the-wow-demo-trap-is-killing-llm-projects-heres-the-exit-de0c8c676430)) is a blunt framing of the measurement and trust problems surfaced by the ChatQDA and AI-Wrapped papers — the failure mode is real and well-documented.
- **METR's Joel Becker on Time Horizon Evals** ([Latent Space](https://www.latent.space/p/metr)) is worth reading alongside the stochasticity paper — METR's exponential time horizon framing is a complementary approach to the MDP formalisation of research agent variance.
- **"The End of SWE-Bench Verified"** ([Latent Space](https://www.latent.space/p/swe-bench-dead)) connects directly to the ReqElicitGym findings — the field is actively retiring benchmarks that no longer discriminate between frontier systems, and the requirements elicitation gap may be the next frontier eval target.
- **Goodfire AI on Mechanistic Interpretability** ([Latent Space](https://www.latent.space/p/goodfire)) is relevant context for the OA framework paper — if culpability attribution requires observable system characteristics, interpretability tooling becomes part of the legal and governance stack, not just a research curiosity.

---

## Field Focus: AI in the Workplace

The research community is beginning to catch up with a question practitioners have been wrestling with for two years: what actually determines whether employees adopt and use AI tools? Two new papers provide some of the most rigorous answers yet — and they complicate the standard story of capability-driven adoption considerably.

**The psychological safety bottleneck.** A study of 2,257 employees at a global consulting firm ([arXiv:2602.23279](https://arxiv.org/abs/2602.23279)) finds that psychological safety reliably predicts whether employees adopt AI tools at all — but has no effect on how frequently or how long they use AI once they've crossed the adoption threshold. The implication is sharp: organisations focused solely on training and tool access are solving the wrong problem. The first barrier is social and cultural, not technical. Employees who don't feel safe to experiment, fail, and ask questions won't adopt AI tools regardless of how capable those tools are. Critically, the relationship held consistently across experience levels, seniority, and geography — no moderation effects emerged — suggesting this is a structural property of AI adoption, not a quirk of this particular firm or industry.

**Work design shapes depth of use, not just adoption.** The companion paper ([arXiv:2602.23278](https://arxiv.org/abs/2602.23278)) examines what predicts depth of AI use — frequency and duration — rather than initial adoption. Skill variety and autonomy in job design are the strongest positive predictors: employees with more varied, self-directed work use AI more deeply and more often. Perceived workload expansion was also positively associated with use depth, while status threat showed a negative association. The practical implication cuts against a common assumption: AI tools don't get used most by the employees who need them most. They get used most by employees who already have interesting, autonomous work — and who can see where AI makes that work better rather than threatening it.

**What the practitioner data says.** These findings land against a backdrop of significant real-world adoption data. Gallup's Q4 2025 survey found that frequent AI use among U.S. workers has risen to 26%, with leaders reporting substantially higher use than individual contributors — 69% vs 40%. That leadership gap is consistent with the work design findings: leaders have more autonomy and skill variety, so they adopt more deeply. Meanwhile, BCG's global survey identifies a "silicon ceiling" for frontline workers, with only half regularly using AI tools, even as job security concerns grow alongside enthusiasm. Morgan Stanley's analysis adds a harder edge: companies in AI-exposed sectors reported an 11.5% average productivity increase, alongside a 4% net reduction in jobs — with cuts concentrated in larger corporations and entry-level roles.

**The gap this research opens.** What's largely missing from both the academic papers and the practitioner surveys is longitudinal evidence on what happens to psychological safety and work design *after* organisations make significant AI investments. Both papers are cross-sectional — they capture a moment, not a trajectory. As AI tools reshape job roles and skill requirements, the conditions that enabled adoption may themselves be altered. That's the next research frontier: not whether employees adopt AI, but whether the organisational conditions for healthy adoption are self-sustaining or self-eroding over time.

---

## Closing Note

The papers this week collectively make a case that the field's evaluation debt is becoming a production risk, not just an academic concern. When workflow metrics can't detect partial failures, when research agents produce materially different outputs across runs, and when standard leaderboard metrics actively discourage specialisation, the scores teams are using to make deployment decisions are less reliable than they appear. The measurement problem is solvable — this week's work shows several tractable paths — but it requires treating evaluation infrastructure with the same engineering rigour as the systems being evaluated. Meanwhile, the Field Focus section this week is a reminder that the harder measurement problems may not be technical at all: understanding why employees adopt AI tools, and whether the conditions for healthy adoption persist over time, remains largely unresolved.

*— The Research Gap is published weekly. Feedback and corrections welcome.*