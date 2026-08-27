# Current Research State: Nebula-MoE

**Project:** Concurrent Batch-Aware Memory Tiering for MoE Inference on CXL-Expanded Systems  
**Context:** Astera Labs Nebula 2026  
**Last Updated:** Workspace Initialization  

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
- **Baseline Taxonomy:** Baseline 0 (HBM-only), Baseline 1 (Naive overflow), Baseline 2 (Static LFU), Baseline 3 (Activation-aware / MoE-Infinity / ProMoE), Baseline 4 (Closest published CXL-MoE).

---

## 2. Implemented Software
- None yet. (Workspace foundation initialized).

---

## 3. Empirical Evidence
- None yet. (No experiments have been executed).

---

## 4. Assumptions
- Hardware platform: Dual NVIDIA RTX A6000 GPUs (48GB GDDR6 each) for inference and trace extraction.
- CXL tier will be modeled via calibrated simulation (not physical CXL hardware).
- Candidate evaluation models: Open-source MoEs (e.g., Qwen MoE architectures).

---

## 5. Planned Work (Next Steps)
- [ ] Select initial MoE model checkpoint for A6000 profiling.
- [ ] Implement MoE forward router profiler hooks to capture routing traces.
- [ ] Build concurrent workload generator.
- [ ] Implement placement baseline algorithms (B0–B2).
- [ ] Build CXL memory tiering simulator.
