#!/usr/bin/env python3
"""
Experiment 01 Runner: Batch-Aware MoE Placement Sweep (Hypothesis H1 / RQ1).
Executes baseline and TierMoE placement algorithms across batch sizes, memory budgets, and seeds.
"""

import argparse
import os
import sys
import time

# Ensure project root is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.evaluation.runner import BenchmarkRunner, RunConfig


def run_experiment(config_path: str = "configs/experiments/exp01_rq1_sweep.yaml") -> str:
    print(f"================================================================")
    print(f"  Project TierMoE: Running Experiment EXP-01 (RQ1 / H1)")
    print(f"  Config: {config_path}")
    print(f"================================================================")

    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    config = RunConfig.from_yaml(config_path)

    print(f"\n[Configuration Summary]")
    print(f"  Experiment ID:        {config.experiment_id} ({config.experiment_name})")
    print(f"  Total Experts:        {config.num_experts} (Top-{config.top_k} active)")
    print(f"  Batch Sizes:          {config.batch_sizes}")
    print(f"  Fast Memory Ratios:   {config.fast_memory_ratios}")
    print(f"  Evaluated Algorithms: {len(config.algorithms)} policies")
    print(f"  CXL Modeled Specs:    {config.cxl_latency_ns}ns latency, {config.cxl_bandwidth_gbps} GB/s BW")
    print(f"  Evaluation Seeds:     {config.seeds}")
    print(f"----------------------------------------------------------------")

    t0 = time.time()
    runner = BenchmarkRunner(config)
    run_dir = runner.run()
    elapsed = time.time() - t0

    print(f"\n[Execution Completed Successfully]")
    print(f"  Time Elapsed: {elapsed:.2f} seconds")
    print(f"  Results saved to: {run_dir}")
    print(f"================================================================\n")

    return run_dir


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run TierMoE EXP-01 sweep.")
    parser.add_argument("--config", default="configs/experiments/exp01_rq1_sweep.yaml", help="Path to YAML config.")
    args = parser.parse_args()

    run_dir = run_experiment(args.config)
    print(f"RUN_DIR={run_dir}")
