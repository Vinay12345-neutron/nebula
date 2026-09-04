#!/usr/bin/env python3
"""
Master Execution Script for Phase 5: EXP-02 (RQ2 / Hypothesis H2).
Orchestrates the entire EXP-02 pipeline:
1. Multi-seed, multi-skew benchmark execution with online Jaccard overlap tracking
2. Statistical analysis & H2 hypothesis testing
3. Publication figure generation
"""

import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from experiments.run_exp02_rq2_divergence import run_experiment
from analysis.analyze_exp02 import analyze_run
from analysis.plot_exp02 import plot_exp02


def main():
    print("\n" + "="*70)
    print("  PROJECT TIERMOE: PHASE 5 - EXP-02 (RQ2 / HYPOTHESIS H2)")
    print("  Request Divergence, Measured Jaccard Overlap & Memory Contention")
    print("="*70 + "\n")

    config_path = "configs/experiments/exp02_rq2_divergence.yaml"
    t0 = time.time()

    # Step 1: Run the benchmark sweep
    run_dir = run_experiment(config_path)

    # Step 2: Statistical analysis
    analysis_results = analyze_run(run_dir)

    # Step 3: Generate figures
    plot_exp02(run_dir, output_dir="figures")

    total_time = time.time() - t0
    print("\n" + "="*70)
    print(f"  EXP-02 COMPLETE in {total_time:.2f}s")
    print(f"  Run Directory: {run_dir}")
    print(f"  H2 Status:     {analysis_results['h2_status']}")
    print("="*70 + "\n")


if __name__ == "__main__":
    main()
