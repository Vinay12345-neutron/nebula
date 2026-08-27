---
name: research-analysis
description: >-
  Use this skill to process raw experiment logs, compute statistical distributions,
  evaluate hypothesis criteria, and generate publication-ready plots.
---

# Research Analysis Skill

Use this procedure when analyzing experimental data from `results/`.

## Analysis Protocol

1. **Ingest Raw Data:**
   - Load raw metrics (`.jsonl` or `.parquet`) from the target run directory in `results/`.
   - Verify presence of configuration and metadata files.
2. **Compute Summary Statistics:**
   - Calculate Mean, Standard Deviation, and Percentiles (P50, P95, P99) for:
     - Fast-tier expert hit rate (%)
     - CXL parameter transfer volume (MB)
     - TTFT and TPOT latency metrics
     - Placement solver runtime overhead
3. **Hypothesis Evaluation:**
   - Evaluate empirical results against the target hypothesis criteria without bias toward positive outcomes.
4. **Figure Generation:**
   - Generate standard plots into `figures/`:
     - Hit rate vs. Fast memory budget curves.
     - Latency vs. Batch size scalability plots.
     - Expert co-activation correlation heatmaps.
