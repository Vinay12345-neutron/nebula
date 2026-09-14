# TierMoE Interactive Research Demonstration

This directory contains the interactive demonstration and dashboard for the **TierMoE** research project:
> **TierMoE: Batch-Aware Expert Placement for Memory-Tiered MoE Inference**

The demonstration presents the complete, audited scientific story across the entire experimental suite:
**EXP-01 → EXP-02 → EXP-03 → EXP-04 → EXP-05A → EXP-05B**.

---

## 1. What the Demonstration Does

The dashboard allows reviewers and researchers to interactively inspect and explore the empirical findings of TierMoE without needing to re-run days of expensive GPU traces or cycle-level simulations.

### Key Interactive Features
- **🏠 Overview & Architecture:** Interactive presentation of the memory-tiering problem, TierMoE's batch-aware scoring formulation, and scientific verdicts across all 6 Research Questions (RQ1–RQ6).
- **📊 EXP-01 (Concurrency Opportunity):** Interactive sweeps across batch sizes ($B \in [1, 32]$) and memory ratios ($\alpha_{\text{mem}} \in [0.25, 1.00]$), demonstrating that batch-aware placement yields $+3.79$ to $+8.68\text{ pp}$ hit rate gains under capacity pressure ($W > C$).
- **🔀 EXP-02 (Routing Divergence):** Analysis of inter-sequence Jaccard overlap $\bar{J}$ and divergence $D = 1 - \bar{J}$, showing monotonic advantage gains at controlled batch size ($B=16$), while explaining the confounding effect of working-set expansion in pooled correlation ($r=0.292, p=0.272$).
- **🧠 EXP-03 (Authentic Qwen3 Traces & Co-Activation):** Evaluation across **461,184 authentic routing events** on `Qwen3-30B-A3B` across ShareGPT and GSM8K. Shows that pairwise co-activation tracking does not provide statistically significant gains ($p=0.259$) while imposing a $12.5\times$ higher solver overhead ($642\,\mu\text{s}$ vs. $51\,\mu\text{s}$).
- **⚔️ EXP-04 (Broader Published Baselines):** Comparative analysis against representative published heuristics (Predictive sequence lookahead and reactive CXL-LRU tiering), showing how TierMoE prevents severe intra-batch cache thrashing.
- **⚡ EXP-05A (CXL Interconnect Sensitivity):** Sensitivity sweeps across link bandwidths (16–64 GB/s) and read latencies (150–600 ns), proving that link bandwidth is the first-order bottleneck ($4.00\times$ scaling).
- **🔬 EXP-05B (CXLMemSim Queue Characterization):** Discrete-event queue characterization showing $1/N$ power-law relative error convergence ($S = 1.0014$ at 256 MiB) and invariant single queue startup overhead ($T_0 \approx 11.44\,\mu\text{s}$) across $K$ concurrent transfers.
- **🗺️ Complete Research Storyline:** Step-by-step narrative summarizing the entire research progression.
- **🔮 "What-If?" Scenario Explorer:** Exact lookups of evaluated experimental configurations with explicit fallback warnings if an un-evaluated combination is requested.
- **📦 Reproducibility & Paper Download:** System specifications, execution instructions, and direct download of `docs/TierMoE_Final_Research_Paper.pdf`.

---

## 2. Dependencies & Installation

The dashboard uses minimal, standard Python libraries:
```bash
pip install streamlit plotly pandas numpy pyarrow
```

---

## 3. How to Launch

From the root of the repository:
```bash
streamlit run demo/app.py
```

Or if using a specific Python virtual environment:
```bash
source /home/k8s-admin/Vinay/sglang/.venv/bin/activate
streamlit run demo/app.py
```

The application will open in your browser at `http://localhost:8501`.

---

## 4. Data Lineage & Experiment Mapping

The dashboard reads existing verified summary and telemetry files directly without modifying or inventing data:

| Experiment | Source Path | Description |
| :--- | :--- | :--- |
| **EXP-01** | `results/exp01_rq1_batch_aware/run_20260828_165000_0cb56a92/` | Concurrency sweeps ($B \in [1, 32]$, $\alpha_{\text{mem}} \in [0.25, 1.00]$, seeds 42, 100, 2026) |
| **EXP-02** | `results/exp02_rq2_divergence/run_20260903_101446_f881a689/` | Routing divergence & Zipf skew sweeps ($\alpha \in [0.8, 1.4]$) |
| **EXP-03** | `results/exp03_rq3_coactivation/run_20260903_133121_147be335/` | 461,184 authentic Qwen3-30B-A3B routing decisions (ShareGPT & GSM8K) |
| **EXP-04** | `results/exp04_broader_baselines/run_20260903_135522_578e421e/` | 24-row comparative evaluation matrix against 5 baseline heuristics |
| **EXP-05A** | `results/exp05a_rq4_cxl_sensitivity/run_20260913_090806_4451055b/` | 81-condition CXL interconnect sensitivity grid (BW: 16–64 GB/s, Lat: 150–600 ns) |
| **EXP-05B** | `results/exp05b_rq4_cxlmemsim_validation/run_20260913_100413_48596d6b/` | Upstream CXLMemSim microbenchmarks & stream scaling validation |
| **Calibration** | `calibration/results/calibration_stage_a_summary.json` | CXLMemSim Stage-A queue calibration telemetry |

---

## 5. What is Measured vs. Modeled

To maintain strict scientific integrity, the demonstration clearly differentiates:
- **Measured Empirical Results:**
  - Layer-by-layer router decisions profiled directly from `Qwen3-30B-A3B` on NVIDIA RTX A6000 hardware.
  - Solver execution times profiled natively on AMD EPYC 7763.
- **Modeled Interconnect Dynamics:**
  - CXL parameter transfer times calculated using the first-order bulk link model $T_{\text{link}} \approx V / \text{BW}$.
- **Simulated Queue Characterization:**
  - Upstream `CXLMemSim` cycle-level queue simulations establishing credit-based queue serialization, the $1/N$ power-law stall factor, and startup overhead ($T_0 \approx 11.44\,\mu\text{s}$).

### Methodological Disclaimers
1. **No Physical CXL Hardware:** Evaluated on dual RTX A6000 GPUs; physical CXL 2.0/3.0 Type-3 hardware was not physically available.
2. **No Full-Scale Native Simulation:** CXLMemSim was used to characterize queue scaling laws and startup costs; it was not run natively for all 75,546 macro-level expert transfers.
3. **Conceptual Baselines:** Baselines B4 (Predictive lookahead) and B5 (CXL-LRU) are representative trace-driven reproductions of published principles, not proprietary vendor implementations.
4. **Hypothesis H3:** Pairwise expert co-activation tracking is designated **"NOT SUPPORTED"** due to lack of statistically significant hit-rate improvement and high solver latency overhead.
