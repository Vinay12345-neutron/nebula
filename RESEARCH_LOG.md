# TierMoE Research Log

A chronological record of research activities, experiments, and milestones.

---

## [Phase 1] - Research Workspace Setup
- **Date:** 2026-08-27
- **Activity:** Initialized the Antigravity research workspace foundation for Project TierMoE.
- **Details:**
  - Established workspace rules (`01_scientific_integrity.md`, `02_simulation_transparency.md`, `03_code_and_config_modularity.md`, `04_reproducibility_contract.md`).
  - Created directory scaffolding (`configs/`, `experiments/`, `results/`, `analysis/`, `figures/`, `papers/`, `docs/`).
  - Created `CURRENT_STATE.md` to track specification, implemented software, empirical evidence, and planned work.
  - Defined initial Skills (`experiment-planner`, `research-analysis`, `gpu-profiling`) and Workflows (`plan-experiment`, `analyze-experiment`).

---

## [Phase 2] - Agent System Validation & Planning Protocol
- **Date:** 2026-08-28
- **Activity:** Validated the agentic research planning workflow and human approval boundaries.
- **Details:**
  - Tested `plan-experiment` workflow and `experiment-planner` skill on Hypothesis H1 / RQ1.
  - Formulated parameter sweeps ($B \in [1, 32]$, $\alpha \in [0.25, 1.0]$), baseline comparisons (B0–B3 vs. Batch-Aware), and explicit overhead accounting without code execution.
  - Validated adherence to scientific integrity rules and simulation transparency constraints.
  - Confirmed human approval gates: agent proposes $\rightarrow$ human reviews $\rightarrow$ wait for approval.

---

## [Phase 3] - TierMoE Experimental Infrastructure Implementation
- **Date:** 2026-08-28
- **Activity:** Built the complete modular engineering foundation for MoE inference profiling and CXL memory tiering simulation.
- **Details:**
  - Model configurations: Initialized `configs/models/qwen3_30b_a3b.yaml` targeting `Qwen/Qwen3-30B-A3B-Instruct-2507` (128 experts, top-8).
  - Profiler (`src/profiler/`): Implemented non-intrusive PyTorch forward router hooks (`router_hook.py`) and GPU memory footprint tracker (`memory_tracker.py`).
  - Workload & Trace (`src/workload/`): Implemented standardized `RoutingTrace` / `BatchRoutingEvent` schemas with Parquet/JSONL export, plus synthetic Zipfian generator (`generator.py`).
  - Placement Solvers (`src/placement/`): Implemented Baselines 0–3 (`HBMOnlySolver`, `NaiveOverflowSolver`, `StaticLFUSolver`, `SingleRequestSolver`) and TierMoE proposed solvers (`BatchAwareGreedySolver`, `BatchAwareCoActivationSolver`).
  - CXL Tier Simulator (`src/simulator/`): Implemented discrete-event CXL tiering simulator (`cxl_model.py`) modeling latency penalties, bandwidth saturation, migration queues, and deduplicated cross-tier traffic.
  - Evaluation Harness (`src/evaluation/`): Implemented end-to-end benchmark runner (`runner.py`) writing immutable run directories with full metadata (`config.yaml`, `meta.json`, `seed.txt`).
  - Unit & Integration Test Suite (`tests/`): Implemented and verified 21 unit/integration tests (`run_tests.py` passing 100%).

---

## [Phase 4] - Corrected Multi-Seed EXP-01 Experiment & Scientific Audit
- **Date:** 2026-08-28
- **Activity:** Executed the complete 432-condition multi-seed EXP-01 benchmark sweep across seeds `[42, 100, 2026]`, statistical analysis, and publication plotting pipeline.
- **Run Directory:** `results/exp01_rq1_batch_aware/run_20260828_165000_0cb56a92`
- **Key Empirical Results:**
  - Evaluated 432 benchmark conditions across batch sizes $B \in [1, 32]$ and memory budget ratios $\alpha \in [0.25, 1.00]$ across 3 independent deterministic seeds.
  - Evaluated capacity-constrained conditions: `TierMoE-Batch-Aware-Greedy` achieved a **+3.79% mean hit rate improvement** (up to **+8.85%** under severe pressure) and **16.94% CXL traffic reduction** (up to **23.58%**) over Single-Request placement.
  - `TierMoE-Batch-Aware-CoActivation` with EMA temporal decay achieved **86.11% hit rate**, outperforming Static LFU (75.27%) by **+10.84%**.
  - Solver overhead was measured at **$49.88\,\mu\text{s}$/step** on average.
  - **Hypothesis H1:** Empirically **SUPPORTED in Capacity-Constrained Regime**.
  - Generated 4 multi-seed publication-grade figures in `figures/exp01_rq1_batch_aware/`.
- **Next Milestone:** Phase 5 - Closed-Loop Multi-Agent Research System & EXP-02.

---

## [Phase 5] - EXP-02 Request Divergence, Jaccard Overlap & Memory Contention
- **Date:** 2026-09-03
- **Activity:** Designed and executed a 384-condition sweep measuring inter-request divergence via online pairwise Jaccard overlap ($\bar{J}$) across Zipf skews $\alpha \in [0.8, 1.4]$ and batch sizes $B \in [4, 32]$ across 3 seeds (`42`, `100`, `2026`).
- **Run Directory:** `results/exp02_rq2_divergence/run_20260903_101446_f881a689`
- **Key Empirical Results:**
  - Online Jaccard overlap tracked from $\bar{J} = 0.087$ (diffuse/divergent) to $\bar{J} = 0.253$ (concentrated).
  - Under capacity-constrained settings ($N=16$), `TierMoE-Batch-Aware-Greedy` achieved **$+4.21\%$ mean hit rate gain** and **$14.74\%$ CXL traffic reduction** over Single-Request placement.
  - Under fixed batch size ($B=16$), TierMoE's advantage monotonically expanded from $+1.99\%$ to $+9.45\%$ as divergence increased.
  - **Hypothesis H2:** **PARTIALLY SUPPORTED (Condition-Dependent / Fixed-Operating Point Scaling)**.

---

## [Phase 6] - EXP-03 Authentic Model Routing Profiling & Co-Activation Falsification
- **Date:** 2026-09-03
- **Activity:** Profiled authentic token routing on physical dual NVIDIA RTX A6000 GPUs using `Qwen/Qwen3-30B-A3B-Instruct-2507` across GSM8K and ShareGPT, capturing 461,184 physical routing decisions. Replayed traces through discrete CXL simulator.
- **Run Directory:** `results/exp03_rq3_coactivation/run_20260903_133121_147be335`
- **Key Empirical Results:**
  - Working set divergence: GSM8K (math reasoning) activated only 10.5–15.0 experts (no capacity pressure), whereas ShareGPT (conversational) activated up to 73.2 experts (severe capacity pressure).
  - TierMoE Greedy outperformed Static LFU by **$+41.18\%$ hit rate** ($37.04\%$ vs $92.51\%$).
  - Evaluated `TierMoE-CoActivation` vs. `TierMoE-Greedy`: CoActivation achieved $-1.25\%$ lower hit rate ($p=0.259$).
  - **Hypothesis H3:** **FALSIFIED / NOT SUPPORTED**. Pairwise co-activation matrix tracking introduces historical inertia; pure instantaneous batch frequency with residency hysteresis is faster ($51\,\mu\text{s}$ vs $750\,\mu\text{s}$) and superior.

---

## [Phase 7] - EXP-04 Broader Baseline Reproduction & Comparative Evaluation
- **Date:** 2026-09-03
- **Activity:** Implemented and benchmarked against external published baseline paradigms:
  - Baseline 4: Predictive / Activation-Aware Lookahead (*MoE-Infinity* / *ProMoE* conceptual approximation)
  - Baseline 5: CXL-MoE Demand-LRU Hardware Tiering (*CXL-MoE* conceptual approximation)
- **Run Directory:** `results/exp04_broader_baselines/run_20260903_135522_578e421e`
- **Key Empirical Results:**
  - `TierMoE-Batch-Aware-Greedy` achieved **$+6.99\%$ higher hit rate** over predictive lookahead ($t=13.58, p=0.00086$) by eliminating multi-tenant prediction collisions.
  - `TierMoE-Batch-Aware-Greedy` achieved **$+16.61\%$ to $+32.27\%$ higher hit rate** over CXL-LRU tiering ($t=2.57, p=0.082$) by eliminating catastrophic intra-batch cache thrashing.

---

## [Phase 8] - Final Evaluation, Artifact Freezing & Synthesis
- **Date:** 2026-09-03
- **Activity:** Final project synthesis, baseline fidelity classification audit, transparent methodological statement grounding, and preparation of final comprehensive research report and deliverables.
- **Milestone Status:** Research roadmap completed. All code, empirical datasets, tests (23/23 passing), and figures verified.

---

## [Phase 8 Extension] - EXP-05A CXL Bandwidth & Latency Sensitivity Sweep
- **Date:** 2026-09-13
- **Activity:** Designed and executed a controlled 81-condition sweep evaluating sensitivity to CXL bandwidth ($16, 32, 64\text{ GB/s}$) and round-trip latency overhead ($150, 300, 600\text{ ns}$) using authentic `Qwen3-30B` ShareGPT traces. Verified causal invariance of placement decisions to interconnect speed.
- **Run Directory:** `results/exp05a_rq4_cxl_sensitivity/run_20260913_090806_4451055b`
- **Key Empirical Results:**
  - Bandwidth is the dominant first-order physical bottleneck ($4.00\times$ transfer time scaling across 16–64 GB/s).
  - Round-trip latency overhead has a negligible effect ($< 0.005\%$) due to the coarse granularity of bulk 256MB expert parameter transfers.
  - `TierMoE-Batch-Aware-Greedy` outperforms `Single-Request` control across all configurations ($+7.99\text{ pp}$ hit rate, $4.05\%$ traffic reduction, $4.05\%$ modeled parameter-transfer time reduction, $p < 10^{-6}$), saving up to $6.39\text{s}$ per run at 16 GB/s.
  - Compared to `Static LFU`, TierMoE achieves $+46.51\text{ pp}$ hit rate gain, but incurs $+11.30\%$ modeled parameter-transfer time (+7.56s) because Static LFU avoids promotion traffic by permanently freezing its GPU resident cache.
  - **Hypothesis H4:** **PARTIALLY SUPPORTED (Bandwidth Dominates; Latency Negligible; Outperforms Single-Request)**.


