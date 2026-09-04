---
name: literature-synthesis
description: >-
  Literature search and contextualization skill for the Literature Agent.
  Audits prior published work, extracts external baseline specifications (B4/B5),
  identifies research gaps, and prevents ungrounded novelty claims.
---

# Literature Synthesis Skill

Use this procedure when analyzing published papers, extracting baseline algorithms, or situating TierMoE findings in the broader systems literature.

## Literature Synthesis Protocol

### 1. Paper Analysis & Gap Identification
- Review relevant systems literature in `papers/` across:
  - MoE memory offloading and expert prefetching (e.g., MoE-Infinity, ProMoE, FMoE, DeepSpeed-MoE).
  - CXL-attached heterogeneous memory tiering and hardware-assisted pooling.
  - Multi-tenant LLM serving dynamics and cross-request interference.
- Isolate the precise research gap: existing systems optimize single-sequence prefetching or static caching; TierMoE investigates **online concurrent batch-aware demand aggregation**.

### 2. External Baseline Specifications (B4 & B5)
- **Baseline 4 (Predictive / Activation-Aware):** Extract the exact mathematical formulation and activation thresholding logic of predictive prefetchers (e.g. sequence-level gating lookahead).
- **Baseline 5 (Published CXL-MoE Architecture):** Extract the specific interconnect modeling, page migration heuristics, or hardware offload assumptions of published CXL-MoE systems.
- Document implementation constraints and reproduction fidelity requirements.

### 3. Claim Scoping & Guardrails
- **Zero Premature Claims:** Strictly ensure TierMoE is NOT claimed to outperform published baselines (B4/B5) until those baselines have been faithfully implemented and benchmarked under identical conditions.
- **Delineate Comparison Sets:** Clearly demarcate RQ1-specific controls (B0–B3) from broader literature baselines (B4–B5).

### 4. Output Artifact
Produce a structured literature summary documenting:
- Target paper citations and key mechanisms.
- Exact algorithmic differences vs. TierMoE batch-aware policies.
- Proposed specification for incorporating B4/B5 into future comparative sweeps.
