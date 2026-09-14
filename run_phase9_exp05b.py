#!/usr/bin/env python3
"""
Master Execution Script for Phase 9: EXP-05B.
Detailed CXLMemSim Memory-System Validation.
Evaluates TierMoE-Batch-Aware-Greedy vs. Baseline-3-Single-Request across
exactly 10 controlled conditions on authentic Qwen3-30B-A3B ShareGPT routing traces
under the CXLMemSim memory-system model.
"""

import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from experiments.run_exp05b_cxlmemsim_validation import run_exp05b_experiment
from analysis.analyze_exp05b import analyze_exp05b
from analysis.plot_exp05b import plot_exp05b


def main():
    print("\n" + "="*75)
    print("  PROJECT TIERMOE: PHASE 9 - EXP-05B (DETAILED CXLMemSim VALIDATION)")
    print("  Evaluating Single-Request vs. TierMoE Across 10 Controlled Conditions")
    print("="*75 + "\n")

    trace_file = "data/traces/qwen3_sharegpt_trace.parquet"
    if not os.path.exists(trace_file):
        print(f"[!] Error: Authentic trace not found: {trace_file}")
        sys.exit(1)

    t0 = time.time()

    # Step 1: Run CXLMemSim detailed validation across exactly 10 conditions
    config_file = "configs/experiments/exp05b_rq4_cxlmemsim_validation.yaml"
    run_dir = run_exp05b_experiment(config_file)

    # Step 2: Run paired analysis and EXP-05A cross-check
    analysis_results = analyze_exp05b(run_dir)

    # Step 3: Generate publication-quality figures
    plot_exp05b(run_dir, output_dir="figures")

    total_time = time.time() - t0
    print("\n" + "="*75)
    print(f"  PHASE 9 EXP-05B COMPLETE in {total_time:.2f}s")
    print(f"  Run Directory: {run_dir}")
    print("="*75 + "\n")


if __name__ == "__main__":
    main()
