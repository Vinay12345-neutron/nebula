#!/usr/bin/env python3
"""
Master Execution Script for Phase 8: EXP-05A.
CXL Bandwidth & Latency Sensitivity Sweep.
Evaluates TierMoE-Batch-Aware-Greedy vs. Static LFU and Single-Request baselines
across a 3x3 CXL parameter grid (16, 32, 64 GB/s; 150, 300, 600 ns) on authentic Qwen3-30B-A3B traces.
"""

import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from experiments.run_exp05a_cxl_sensitivity import run_exp05a_sweep
from analysis.analyze_exp05a import analyze_exp05a
from analysis.plot_exp05a import plot_exp05a


def main():
    print("\n" + "="*75)
    print("  PROJECT TIERMOE: PHASE 8 - EXP-05A (CXL SENSITIVITY SWEEP)")
    print("  Evaluating CXL Bandwidth (16, 32, 64 GB/s) & Latency (150, 300, 600 ns)")
    print("="*75 + "\n")

    trace_file = "data/traces/qwen3_sharegpt_trace.parquet"
    if not os.path.exists(trace_file):
        print(f"[!] Error: Authentic trace not found: {trace_file}")
        sys.exit(1)

    t0 = time.time()

    # Step 1: Run sensitivity sweep across 81 conditions
    config_file = "configs/experiments/exp05a_rq4_cxl_sensitivity.yaml"
    run_dir = run_exp05a_sweep(config_file)

    # Step 2: Run sensitivity and statistical analysis
    analysis_results = analyze_exp05a(run_dir)

    # Step 3: Generate publication-quality figures
    plot_exp05a(run_dir, output_dir="figures")

    total_time = time.time() - t0
    print("\n" + "="*75)
    print(f"  PHASE 8 EXP-05A COMPLETE in {total_time:.2f}s")
    print(f"  Run Directory: {run_dir}")
    print("="*75 + "\n")


if __name__ == "__main__":
    main()
