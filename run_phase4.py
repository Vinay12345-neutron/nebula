#!/usr/bin/env python3
"""
Phase 4 Master Orchestration Script.
Executes the EXP-01 experiment sweep, runs statistical analysis, and generates publication plots for TierMoE.
"""

import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from experiments.run_exp01_rq1_sweep import run_experiment
from analysis.analyze_exp01 import analyze_run
from analysis.plot_exp01 import generate_plots


def main():
    print("==================================================================")
    print("      PROJECT TIERMOE: PHASE 4 EXPERIMENTAL PIPELINE")
    print("==================================================================")

    # 1. Execute EXP-01 Matrix Sweep
    config_file = "configs/experiments/exp01_rq1_sweep.yaml"
    run_dir = run_experiment(config_file)

    # 2. Run Statistical Analysis & Hypothesis Evaluation
    analysis_results = analyze_run(run_dir)

    # 3. Generate Publication-Quality Figures
    figures = generate_plots(run_dir, output_dir="figures/exp01_rq1_batch_aware")

    print("\n==================================================================")
    print("      PHASE 4 EXECUTION & ANALYSIS COMPLETED SUCCESSFULLY")
    print("==================================================================")
    print(f"Run Artifacts Directory: {run_dir}")
    print(f"Figures Output:          figures/exp01_rq1_batch_aware/")
    for fig_path in figures:
        print(f"  - {fig_path}")
    print("==================================================================\n")


if __name__ == "__main__":
    main()
