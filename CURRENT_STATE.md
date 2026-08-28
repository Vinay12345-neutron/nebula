# Current Research State: Nebula-MoE

**Project:** Concurrent Batch-Aware Memory Tiering for MoE Inference on CXL-Expanded Systems  
**Context:** Astera Labs Nebula 2026  
**Last Updated:** Phase 1 Initialization Completed  

---

## 1. Research Specification (from `README.md`)
- **Primary Research Questions:**
  - **RQ1 (Concurrent Serving):** How does concurrent serving change optimal MoE expert placement across limited fast GPU memory and CXL memory vs. single-sequence placement?
  - **RQ2 (Aggregate Expert Demand):** Can aggregate batch-level expert demand improve fast-tier residency and reduce CXL traffic compared with single-request policies?
  - **RQ3 (Expert Co-Activation):** Does exploiting expert co-activation and request overlap outperform simple frequency (LFU) placement?
- **Secondary Research Questions:** Dynamic KV-cache memory competition (RQ4), workload drift (RQ5), and CXL parameter sensitivity (RQ6).
- **Core Hypotheses:**
  - **H1 (Batch-Aware Placement):** Batch-aware placement achieves higher fast-tier hit rates and lower CXL traffic than static global popularity or per-request placement under concurrent serving.
  - **H2 (Workload Divergence):** The advantage of batch-aware placement widens as request expert-access patterns diverge and fast memory is constrained.
  - **H3 (Co-Activation):** Co-activation information provides additional cross-tier traffic reduction for workloads with correlated expert activation.
  - **H4 (Dynamic KV Budget):** Dynamically adjusting expert memory budgets against KV cache pressure improves inference latency.
  - **H5 (CXL Sensitivity):** Tiering gains depend strongly on CXL bandwidth and latency bounds.
- **Baseline Taxonomy:**
  - *Baseline 0:* Fast-memory-only (upper bound / OOM reference)
  - *Baseline 1:* Naive overflow
  - *Baseline 2:* Static global frequency (LFU)
  - *Baseline 3:* Activation-aware / predictive placement (MoE-Infinity / ProMoE)
  - *Baseline 4:* Closest published CXL-MoE approach

---

## 2. Implemented Software
- None yet. (Workspace foundation initialized; no model hooks, simulators, or solvers built yet).

---

## 3. Empirical Evidence
- None yet. (Zero experiments executed; no simulated or physical benchmarks recorded).

---

## 4. Assumptions
- **Hardware:** Dual NVIDIA RTX A6000 GPUs (48GB GDDR6 each, total 96GB VRAM) for physical inference & routing trace capture.
- **CXL Simulation:** RTX A6000 is not CXL hardware; CXL tier will be modeled via calibrated simulation grounded in published latency/bandwidth numbers.
- **Candidate Models:** Open-source MoEs (e.g., Qwen MoE architectures).

---

## 5. Dual-Track Research & System Roadmap

The project progresses along two simultaneous tracks:
1. **Nebula Research Core:** Models, routing traces, placement algorithms, CXL simulation, empirical benchmarks.
2. **Antigravity Research Infrastructure:** Rules, skills, workflows, subagents, MCPs, and automation.

> **Guiding Principle:** *Don't automate a research process until we've successfully executed that process manually at least once.*

```text
PHASE 1: Research Workspace Foundation  [✅ COMPLETE]
    ↓
PHASE 2: Validate Agent System & Planning  [🟢 CURRENT PHASE]
    ↓
PHASE 3: Build Nebula Experimental Infrastructure  [⏳ PLANNED]
    ↓
PHASE 4: First Real Research Experiment (H1 / RQ1)  [⏳ PLANNED]
    ↓
PHASE 5: Multi-Agent Research Team  [⏳ FUTURE]
    ↓
PHASE 6: MCP & Custom Research API Integration  [⏳ FUTURE]
    ↓
PHASE 7: Hooks & Guarded Experiment Automation  [⏳ FUTURE]
    ↓
PHASE 8: Continuous Semi-Autonomous Research OS  [⏳ FUTURE]
```

---

### Phase Breakdown & Detailed Status

#### Phase 1: Research Workspace Foundation
- **Status:** ✅ **COMPLETE**
- **Goal:** Establish governance rules, directory scaffolding, skill runbooks, and state trackers.
- **Delivered:**
  - `AGENTS.md` and rules in `.agents/rules/` (`01_scientific_integrity.md`, `02_simulation_transparency.md`, `03_code_and_config_modularity.md`, `04_reproducibility_contract.md`).
  - Directory skeleton: `configs/`, `experiments/`, `results/`, `analysis/`, `figures/`, `papers/`, `docs/`.
  - Initial skills (`experiment-planner`, `gpu-profiling`, `research-analysis`) and workflows (`plan-experiment`, `analyze-experiment`).
  - State and log tracking (`CURRENT_STATE.md`, `RESEARCH_LOG.md`).

#### Phase 2: Validate the Agent System
- **Status:** 🟢 **CURRENT PHASE**
- **Goal:** Verify that the agent strictly adheres to scientific rules, design protocols, and human approval boundaries before writing code or running experiments.
- **Key Milestones:**
  - [ ] Test experiment planning workflow (`/plan-experiment`) on RQ1/H1 without running code.
  - [ ] Human review of proposed experimental parameters (batch sizes, divergence metrics, baselines).
  - [ ] Validate analysis workflow protocol and data integrity checks.
  - [ ] Enforce strict human approval boundaries (agent proposes $\rightarrow$ human approves $\rightarrow$ execution).
- **Exit Condition:** Agent consistently designs sound, rule-compliant experiments and waits for explicit approval without inventing results.

#### Phase 3: Build Nebula Experimental Infrastructure
- **Status:** ⏳ **PLANNED**
- **Goal:** Build the engineering foundation from the bottom up.
- **Key Milestones:**
  - [ ] Select initial MoE model checkpoint for A6000 profiling (e.g., Qwen MoE).
  - [ ] Implement read-only PyTorch forward router hooks to extract routing traces.
  - [ ] Standardize trace serialization schema (`metadata.json`, `routing.parquet`).
  - [ ] Build synthetic & trace-driven concurrent workload generator (controlling batch size, overlap, divergence).
  - [ ] Implement baseline placement solvers (B0: HBM-only, B1: Naive overflow, B2: LFU).
  - [ ] Build CXL memory tiering simulator (bandwidth, latency, migration queues).

#### Phase 4: Run First Real Research Experiment
- **Status:** ⏳ **PLANNED**
- **Goal:** Complete the first end-to-end empirical loop on RQ1/H1.
- **Key Milestones:**
  - [ ] Replay identical routing traces across Baseline 2 (LFU), Single-Request Policy, and Batch-Aware Solver.
  - [ ] Measure fast-tier hit rates, CXL parameter traffic, TTFT, TPOT, and solver runtime overhead.
  - [ ] Run statistical analysis and generate initial comparative figures.
  - [ ] Establish the first empirical evidence regarding Hypothesis H1.

#### Phase 5: Multi-Agent Research Team
- **Status:** ⏳ **FUTURE**
- **Goal:** Specialize agent roles once the core pipeline is validated.
- **Structure:**
  - *Research Lead:* High-level orchestration & synthesis.
  - *Literature Agent:* Related work tracking, baseline identification, novelty verification.
  - *Experiment Agent:* Parameter matrices, configuration generation, run tracking.
  - *Systems Agent:* CUDA memory, kernels, GPU profiling, transfer optimization.
  - *Review Agent ("Adversary"):* Critiques experimental designs, checks for confounders, and attempts to disprove hypotheses.

#### Phase 6: MCP / External Tool Integration
- **Status:** ⏳ **FUTURE**
- **Goal:** Connect agents to structured external interfaces via Model Context Protocol.
- **Key Milestones:**
  - [ ] Literature MCP (arXiv / Semantic Scholar metadata extraction).
  - [ ] Results & Trace Database MCP (DuckDB / SQLite low-overhead querying).
  - [ ] `nebula-mcp`: Custom research server exposing state queries, experiment comparisons, and GPU telemetry.

#### Phase 7: Hooks + Autonomous Experiment Pipeline
- **Status:** ⏳ **FUTURE**
- **Goal:** Automate repetitive pre-flight and post-run tasks while maintaining safety.
- **Key Milestones:**
  - [ ] Pre-run hooks: Validate config syntax, verify GPU thermal/memory state, assert clean Git status.
  - [ ] Post-run hooks: Collect environment metadata, assert data completeness, index results.

#### Phase 8: Continuous Semi-Autonomous Research OS
- **Status:** ⏳ **FUTURE**
- **Goal:** Long-term standing research operations with scheduled monitoring, weekly synthesis, and adversarial critiques under human direction.

---

## 6. Immediate Next Steps
1. Execute **Phase 2.1**: Test the `/plan-experiment` workflow for Hypothesis H1 (RQ1) to validate the agent's experimental design capabilities.
2. Review the proposed experimental matrix, baselines, and control variables with the human researcher.
