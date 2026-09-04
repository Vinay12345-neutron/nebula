#!/usr/bin/env python3
"""
Master Execution Script for Phase 6: EXP-03 (RQ3 / Hypothesis H3).
Authentic Model Routing & Co-Activation Analysis on Qwen3-30B-A3B.
"""

import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from experiments.run_exp03_rq3_sweep import run_exp03_sweep
from analysis.analyze_exp03 import analyze_exp03
from analysis.plot_exp03 import plot_exp03


def main():
    print("\n" + "="*70)
    print("  PROJECT TIERMOE: PHASE 6 - EXP-03 (RQ3 / HYPOTHESIS H3)")
    print("  Authentic Qwen3-30B-A3B Model Routing & Co-Activation Evaluation")
    print("="*70 + "\n")

    gsm8k_trace = "data/traces/qwen3_gsm8k_trace.parquet"
    sharegpt_trace = "data/traces/qwen3_sharegpt_trace.parquet"

    if not os.path.exists(gsm8k_trace) or not os.path.exists(sharegpt_trace):
        print(f"[!] Warning: Authentic trace files not detected in data/traces/")
        print(f"    Please run the profiling harness first:")
        print(f"    python3 experiments/profile_qwen3_traces.py --num-prompts 64\n")
        sys.exit(1)

    t0 = time.time()

    # Step 1: Run benchmark sweep on authentic traces
    run_dir = run_exp03_sweep("configs/experiments/exp03_rq3_real_traces.yaml")

    # Step 2: Statistical analysis
    analysis_results = analyze_exp03(run_dir)

    # Step 3: Generate figures
    plot_exp03(run_dir, output_dir="figures")

    total_time = time.time() - t0
    print("\n" + "="*70)
    print(f"  EXP-03 COMPLETE in {total_time:.2f}s")
    print(f"  Run Directory: {run_dir}")
    print(f"  H3 Status:     {analysis_results['h3_status']}")
    print("="*70 + "\n")


if __name__ == "__main__":
    main()
