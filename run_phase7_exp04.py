#!/usr/bin/env python3
"""
Master Execution Script for Phase 7: EXP-04.
Broader Published Baseline Reproduction & Comparative Evaluation.
Benchmarks TierMoE against:
- Baseline 4: Predictive Activation-Aware (MoE-Infinity / ProMoE)
- Baseline 5: CXL-MoE Demand-LRU Hardware Tiering
alongside Baselines 0, 2, and 3 on authentic Qwen3-30B-A3B serving traces.
"""

import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from experiments.run_exp04_broader_baselines import run_exp04_sweep
from analysis.analyze_exp04 import analyze_exp04
from analysis.plot_exp04 import plot_exp04


def main():
    print("\n" + "="*75)
    print("  PROJECT TIERMOE: PHASE 7 - EXP-04 (BROADER BASELINE EVALUATION)")
    print("  Comparative Evaluation: TierMoE vs. MoE-Infinity/ProMoE & CXL-MoE")
    print("="*75 + "\n")

    trace_file = "data/traces/qwen3_sharegpt_trace.parquet"
    if not os.path.exists(trace_file):
        print(f"[!] Error: Authentic trace not found: {trace_file}")
        sys.exit(1)

    t0 = time.time()

    # Step 1: Run comparative sweep across all 6 algorithms
    run_dir = run_exp04_sweep("configs/experiments/exp04_broader_baselines.yaml")

    # Step 2: Run statistical analysis
    analysis_results = analyze_exp04(run_dir)

    # Step 3: Generate comparative publication figures
    plot_exp04(run_dir, output_dir="figures")

    total_time = time.time() - t0
    print("\n" + "="*75)
    print(f"  PHASE 7 COMPLETE in {total_time:.2f}s")
    print(f"  Run Directory: {run_dir}")
    print("="*75 + "\n")


if __name__ == "__main__":
    main()
