---
name: experiment-planner
description: >-
  Use this skill when designing, formulating, or configuring a new experiment matrix
  for Nebula-MoE research. Ensures experiments adhere to the reproducibility contract,
  define clear baseline comparisons, and establish testable parameter sweeps.
---

# Experiment Planner Skill

Use this procedure when the user initiates the planning of a new experiment.

## Planning Protocol

1. **Link to Specification:**
   - Identify the target Hypothesis (H1–H5) and Research Question (RQ1–RQ6) from `CURRENT_STATE.md`.
2. **Define Parameter Matrix:**
   - Workload variables: Batch size $B$, sequence length, request concurrency, expert overlap degree.
   - Memory variables: Fast-memory budget ratio $C_{\text{expert}} / \text{Total Expert Memory}$.
   - CXL variables: Modeled bandwidth (GB/s), modeled latency penalty (ns).
   - Execution type: Deterministic (1 run with justification) vs. Stochastic (multiple random seeds).
3. **Select Baselines:**
   - Define which baselines (B0–B4) will be evaluated alongside the proposed policy.
4. **Draft Configuration Schema:**
   - Structure a proposed YAML file for `configs/<experiment_name>.yaml`.
5. **Awaiting User Review:**
   - Present the experiment design and parameter matrix to the user for explicit approval before running.
