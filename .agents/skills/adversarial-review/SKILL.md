---
name: adversarial-review
description: >-
  Auditing and falsification skill for the Adversarial Reviewer Agent.
  Stress-tests empirical findings, verifies conservation laws (traffic accounting),
  delineates memory pressure boundaries, checks for confounders, and runs inferential statistical tests.
---

# Adversarial Review Skill

Use this procedure when auditing experimental runs, validating hypotheses, or challenging claims before they become accepted scientific conclusions.

## Adversarial Audit Protocol

### 1. Conservation Laws & Traffic Accounting Verification
- **Byte Conservation:** Verify that reported CXL demand traffic strictly satisfies:
  $$\text{Demand Traffic (Bytes)} = N_{\text{unique\_missing\_experts}} \times \text{expert\_size\_bytes}$$
- **Promotion Isolation:** Verify that newly promoted experts are accounted under promotion traffic and produce **0 bytes** of demand-miss traffic (no double-counting).
- **Eviction Writeback Check:** Verify that clean read-only MoE weight evictions produce **0 writeback bytes**.

### 2. Memory Pressure & Working Set Boundary Analysis
- Compute the empirical working set size $W_{\text{active}}$ (distinct demanded experts per step).
- Delineate conditions by **Pressure Ratio** ($\text{PR} = W_{\text{active}} / C$):
  - $\text{PR} \le 1.0$: **No-Pressure** (Working set fits in fast memory; policies are expected to perform identically).
  - $1.0 < \text{PR} < 1.5$: **Capacity-Pressure** (Legitimate test of placement policy).
  - $\text{PR} \ge 1.5$: **Severe-Pressure** (High contention/saturation).
- Reject any claim that attributes policy superiority to unconstrained / no-pressure conditions.

### 3. Baseline Equivalence & Fairness Audit
- Verify that baselines are implemented fairly and compared under identical traces and seeds.
- Ensure Single-Request placement (Baseline 3) is strictly described as an RQ1-specific control, not confused with published predictive methods (Baseline 4).

### 4. Inferential Statistical Significance Testing
- Verify whether observed improvements are statistically significant across paired random seeds using a **two-tailed Paired Student's $t$-test** or **Wilcoxon Signed-Rank Test**.
- Reject heuristic threshold claims unless backed by sample variance, standard error of the mean (SEM), and formal $p$-values ($p < 0.05$).

### 5. Adversarial Audit Report Output
Produce an adversarial audit artifact documenting:
- Any identified accounting bugs or anomalies.
- True effect sizes isolated strictly to capacity-constrained regimes.
- Statistical significance verdict ($t$-statistic, $p$-value).
- Formal recommendation: **PASS**, **CONDITIONAL PASS (Regime-Restricted)**, or **FAIL / REJECT CLAIM**.
