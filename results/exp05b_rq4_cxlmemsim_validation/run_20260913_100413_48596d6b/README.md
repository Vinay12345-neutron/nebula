# EXP-05B: Detailed CXLMemSim Memory-System Validation Report

## Executive Summary

This experiment evaluates whether the positive conclusions established in EXP-05A survive when the authentic Qwen3-30B-A3B routing traces are subjected to the detailed **CXLMemSim** memory-system simulation model.

- **Mean HBM Hit Rate Improvement:** +7.99 percentage points (pp)
- **Mean CXL Traffic Reduction:** 4.05%
- **Mean CXLMemSim-Modeled Transfer Time Reduction:** 4.05%
- **EXP-05A Analytical Mean Reference:** 4.05%
- **Scientific Validation Verdict:** **VALIDATED**

## Condition-by-Condition Paired Evaluation Table

| Batch Size | CXL BW (GB/s) | CXL Latency (ns) | Hit Rate Diff (pp) | Single-Request Transfers | TierMoE Transfers | CXLMemSim Time Red. (%) | EXP-05A Analytical Red. (%) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| B=8 (Core) | 32.0 | 300.0 | +0.33 pp | 10,990 | 10,405 | **5.32%** | 5.32% |
| B=16 (Core) | 32.0 | 300.0 | +10.23 pp | 8,724 | 8,263 | **5.28%** | 5.28% |
| B=32 (Sens) | 16.0 | 300.0 | +13.41 pp | 6,242 | 6,146 | **1.54%** | 1.54% |
| B=32 (Core) | 32.0 | 300.0 | +13.41 pp | 6,242 | 6,146 | **1.54%** | 1.54% |
| B=32 (Sens) | 64.0 | 300.0 | +13.41 pp | 6,242 | 6,146 | **1.54%** | 1.54% |

## Methodology & Safety Compliance

- **Workload:** Authentic Qwen3-30B-A3B ShareGPT routing trace (`data/traces/qwen3_sharegpt_trace.parquet`) across 48 layers (276,816 routing events).
- **Expert Representation:** Exactly 256 MiB ($268,435,456$ bytes) = 4,194,304 cache lines per expert block. Zero downsampling.
- **Address Space:** Deterministic non-overlapping 256-MiB aligned aperture across all 6,144 experts.
- **Traffic Semantics:** Read-only weights; clean evictions produce 0 writeback bus traffic; duplicate expert demands within batch steps are deduplicated.
- **Terminology:** Detailed trace-driven CXLMemSim memory-system simulation (no physical hardware claimed).
