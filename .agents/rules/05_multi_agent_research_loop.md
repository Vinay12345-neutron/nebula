# Rule 05: Closed-Loop Multi-Agent Research Governance

This rule governs the execution of multi-agent research loops in TierMoE to ensure scientific rigor, immutability of historical data, and strict human oversight.

---

## 1. The Closed-Loop Lifecycle

Research in TierMoE follows a strict 6-stage closed-loop progression:

```text
┌─────────────────────────────────────────────────────────────┐
│ 1. Research Lead: Formulates RQ, Hypotheses & Success Specs │
└──────────────────────────────┬──────────────────────────────┘
                               │ Handoff: Research Plan Artifact
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. Literature Agent: Checks Prior Art & B4/B5 Baseline Spec │
│    + Systems/Profiler: Audits Hardware/Trace Assumptions    │
└──────────────────────────────┬──────────────────────────────┘
                               │ Handoff: Grounding & Audit Report
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. Experiment Runner: Executes Multi-Seed Matrix Sweeps     │
│    + Analysis: Aggregates Metrics (Mean, Std, SEM)          │
└──────────────────────────────┬──────────────────────────────┘
                               │ Handoff: Immutable Run Parquet
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. Adversarial Reviewer: Audits Accounting, Tests Confounders│
│    & Evaluates Statistical Significance (p-values)          │
└──────────────────────────────┬──────────────────────────────┘
                               │ Handoff: Adversarial Audit Artifact
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 5. Research Lead: Synthesizes Verified Findings & Updates RQ│
└──────────────────────────────┬──────────────────────────────┘
                               │ Handoff: Candidate Conclusion
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 6. HUMAN APPROVAL GATE: User reviews & approves conclusion  │
└──────────────────────────────┬──────────────────────────────┘
                               │ Approved
                               ▼
              [Proceed to Next Experiment (e.g. EXP-02)] ↺
```

---

## 2. Artifact Handoff Protocol

Agents must communicate exclusively through explicit, reproducible artifacts. No agent may pass unwritten or ephemeral assumptions to subsequent stages.

| Stage Transition | Source Agent | Consuming Agent | Required Artifact File |
|---|---|---|---|
| **$1 \rightarrow 2$** | Research Lead | Literature & Systems | `configs/experiments/<exp_name>.yaml` + Plan Specification |
| **$2 \rightarrow 3$** | Literature & Systems | Experiment Runner | Systems Grounding Report & Validated Trace Data |
| **$3 \rightarrow 4$** | Experiment & Analysis | Adversarial Reviewer | `results/<exp_name>/run_*/summary_metrics.parquet` + `analysis_summary.json` |
| **$4 \rightarrow 5$** | Adversarial Reviewer | Research Lead | Adversarial Audit Report (Conservation check, $p$-values, regime breakdown) |
| **$5 \rightarrow 6$** | Research Lead | **Human User** | Formal Synthesis Report + Proposed Next Experiment Design |

---

## 3. Mandatory Research Guardrails

1. **Adversarial Gate:** No experimental finding may be classified as "SUPPORTED" or added to `CURRENT_STATE.md` without passing an adversarial audit (conservation check, regime isolation, inferential $p < 0.05$).
2. **Human Approval Gate:** The human user has final authority over accepted conclusions. Agents may propose updates, but cannot modify `CURRENT_STATE.md` scientific conclusions without explicit user approval.
3. **Historical Immutability:** Existing run directories in `results/` are immutable historical records. Agents may never overwrite, delete, or retroactively edit past experiment artifacts.
4. **Zero Novelty Inflation:** TierMoE policies may only be claimed to outperform baselines that have been directly evaluated under identical empirical conditions.
