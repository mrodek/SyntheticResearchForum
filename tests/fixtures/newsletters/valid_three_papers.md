## Issue #5 — Multi-Agent Systems Under Stress

This week's field notes cover three papers that stress-test multi-agent coordination.

## This Week's Signal

Multi-agent systems face compounding failure modes when optimisation pressure meets alignment constraints. This week we examine three papers that map these failure modes from different angles.

## Primary Signals

### The Coordination Collapse Problem

**URL:** https://arxiv.org/abs/2401.12345v2
**Technical summary:** This paper models coordination failure in multi-agent systems as a phase transition. Under sufficient optimisation pressure, agents abandon cooperative equilibria.
**Why it matters:** Establishes a formal bound on when coordination collapse is inevitable.

### Efficiency Gradients and Safety Margins

**URL:** https://arxiv.org/abs/2402.67890
**Technical summary:** An empirical study of 47 multi-agent benchmarks showing inverse correlation between efficiency gains and safety margin preservation.
**Why it matters:** Provides the first large-scale empirical evidence connecting optimisation pressure to safety degradation.

### Centralised Control Under Adversarial Conditions

**URL:** https://arxiv.org/abs/2403.11111
**Technical summary:** Examines how centralised control architectures degrade when one agent is adversarially perturbed. Introduces a resilience metric.
**Why it matters:** Bridges theoretical coordination models and practical deployment resilience.

## Pattern Watch

- Efficiency vs alignment: optimisation pressure degrades safety margins across deployment contexts
- Centralised vs distributed control: failure propagation patterns differ fundamentally by architecture
- Formal bounds vs empirical measurement: theoretical guarantees diverge from observed behaviour

## Supporting Evidence

- Studies of ant colony algorithms show similar phase transitions under resource pressure
- Human team coordination research documents analogous collapse patterns in high-stress scenarios
- Formal verification literature establishes baseline impossibility results for fully distributed safety
- Recent LLM agent benchmarks reproduce the efficiency-safety inverse correlation at scale
- Historical analysis of algorithmic trading failures shows centralised control fragility under adversarial conditions
