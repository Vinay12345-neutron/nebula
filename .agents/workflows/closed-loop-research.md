---
description: Closed-loop multi-agent research orchestration workflow for TierMoE.
---

# Workflow: Closed-Loop Multi-Agent Research

Step-by-step procedure for executing an end-to-end research cycle across the 5 specialized agent personas.

## Execution Sequence

### Step 1: Research Lead — Problem Formulation
- Inspect current research state in `CURRENT_STATE.md`.
- Formulate target Research Question (RQ) and testable Hypothesis (H).
- Define independent variables, fixed parameters, and success criteria.

### Step 2: Literature & Systems Grounding
- **Literature Agent:** Check prior art in `papers/`, define baseline control expectations (B0–B3) and future comparative baselines (B4–B5).
- **Systems / Profiler Agent:** Verify PyTorch routing hook instrumentation, CUDA memory footprints, and CXL simulator constraints.

### Step 3: Experiment Planning & Execution
- **Experiment Planner:** Draft declarative configuration in `configs/experiments/<exp>.yaml`.
- **Experiment Runner:** Execute deterministic multi-seed sweep (`src/evaluation/runner.py`) generating immutable parquet records in `results/`.
- **Analysis:** Aggregate multi-seed distributions ($\text{Mean} \pm \text{SEM}$) and render publication figures.

### Step 4: Adversarial Review & Falsification
- **Adversarial Reviewer:** Audit traffic conservation ($\text{traffic} == N_{\text{unique}} \times W_e$), check promotion isolation, delineate memory pressure boundaries ($W_{\text{active}} > C$), and calculate inferential $p$-values.

### Step 5: Research Lead Synthesis
- Review adversarial audit verdict.
- Synthesize empirical effect sizes strictly within validated regimes.
- Draft proposed next experiment (e.g. EXP-02).

### Step 6: Human Approval Gate
- Present the synthesis report, adversarial audit, and next experiment proposal to the human user for review.
- Await approval before updating accepted findings or initiating the next loop.
