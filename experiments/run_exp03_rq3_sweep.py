#!/usr/bin/env python3
"""
Experiment 03 Runner: Authentic Model Routing & Co-Activation Sweep (RQ3 / Hypothesis H3).
Evaluates TierMoE Co-Activation vs Greedy and Static LFU on real Qwen3-30B router traces
across GSM8K and ShareGPT workloads.
"""

import argparse
import hashlib
import json
import os
import sys
import time
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd
import yaml

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.evaluation.runner import ALGORITHM_MAP
from src.simulator.cxl_model import CXLMemoryTierSimulator
from src.workload.generator import ConcurrentWorkloadGenerator
from src.workload.trace_schema import RoutingTrace


def run_exp03_sweep(config_path: str = "configs/experiments/exp03_rq3_real_traces.yaml") -> str:
    print("================================================================")
    print("  Project TierMoE: Running Experiment EXP-03 (RQ3 / H3)")
    print(f"  Config: {config_path}")
    print("================================================================")

    with open(config_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    exp_cfg = cfg.get("experiment", {})
    wl_cfg = cfg.get("workload", {})
    trace_files = wl_cfg.get("trace_files", {})
    batch_sizes = wl_cfg.get("batch_sizes", [4, 8, 16, 32])
    mem_ratios = cfg.get("memory", {}).get("fast_memory_ratios", [0.25, 0.50])
    algo_keys = cfg.get("algorithms", ["baseline_0_hbm_only", "baseline_2_static_lfu", "tiermoe_batch_aware_greedy", "tiermoe_batch_aware_coactivation"])
    cxl_cfg = cfg.get("cxl_config", "configs/cxl/cxl_defaults.yaml")
    results_base = cfg.get("outputs", {}).get("results_dir", "results/exp03_rq3_coactivation")

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    run_hash = hashlib.md5(f"EXP-03_{timestamp}".encode()).hexdigest()[:8]
    run_dir = os.path.join(results_base, f"run_{timestamp}_{run_hash}")
    os.makedirs(run_dir, exist_ok=True)

    simulator = CXLMemoryTierSimulator(
        latency_penalty_ns=300.0,
        bandwidth_gbps=32.0,
        expert_size_bytes=268435456  # 256 MB
    )

    all_summaries: List[Dict[str, Any]] = []

    for dataset_name, trace_path in trace_files.items():
        if not os.path.exists(trace_path):
            raise FileNotFoundError(f"Trace file not found: {trace_path}. Please run profiling first.")

        print(f"\n[Loading Authentic Trace: {dataset_name.upper()} from {trace_path}]")
        df_trace = pd.read_parquet(trace_path)
        trace = RoutingTrace.from_dataframe(
            df=df_trace,
            model_name="Qwen/Qwen3-30B-A3B-Instruct-2507",
            num_experts=128,
            top_k=8,
            num_layers=48
        )
        print(f"  Loaded {len(trace.events)} routing events across {trace.num_layers} layers.")

        workload_gen = ConcurrentWorkloadGenerator(trace)

        for batch_size in batch_sizes:
            t_b0 = time.time()
            batch_events = list(workload_gen.generate_batches(batch_size=batch_size))
            avg_working_set = float(np.mean([len(be.expert_frequency) for be in batch_events])) if batch_events else 0.0

            for ratio in mem_ratios:
                fast_cap = max(1, int(128 * ratio))
                pressure_ratio = avg_working_set / fast_cap if fast_cap > 0 else 0.0
                regime = "no-pressure" if pressure_ratio <= 1.0 else ("capacity-pressure" if pressure_ratio < 1.5 else "severe-pressure")

                for algo_key in algo_keys:
                    if algo_key not in ALGORITHM_MAP:
                        continue

                    solver_cls = ALGORITHM_MAP[algo_key]
                    solver = solver_cls(num_experts=128)
                    solver.reset()

                    current_fast_tier = None
                    decisions = []

                    for b_ev in batch_events:
                        dec = solver.solve(
                            batch_event=b_ev,
                            fast_capacity=fast_cap,
                            current_fast_tier=current_fast_tier
                        )
                        decisions.append(dec)
                        current_fast_tier = dec.fast_resident_experts

                    summary = simulator.simulate_run(
                        algorithm_name=solver.name,
                        decisions=decisions
                    )

                    summary_dict = summary.to_dict()
                    summary_dict.update({
                        "dataset": dataset_name,
                        "batch_size": batch_size,
                        "fast_memory_ratio": ratio,
                        "fast_capacity_experts": fast_cap,
                        "avg_working_set_experts": avg_working_set,
                        "capacity_pressure_ratio": pressure_ratio,
                        "pressure_regime": regime,
                        "is_capacity_constrained": bool(avg_working_set > fast_cap)
                    })
                    all_summaries.append(summary_dict)

            dt_b = time.time() - t_b0
            print(f"    [{dataset_name} | B={batch_size:2d}] Processed in {dt_b:.2f}s (Working Set: {avg_working_set:.1f} experts)")

    # Save summary metrics
    summary_df = pd.DataFrame(all_summaries)
    summary_df.to_parquet(os.path.join(run_dir, "summary_metrics.parquet"), index=False)
    summary_df.to_json(os.path.join(run_dir, "summary_metrics.json"), orient="records", indent=2)

    print(f"\n[Execution Completed Successfully]")
    print(f"  Results saved to: {run_dir}")
    print("================================================================\n")
    return run_dir


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run TierMoE EXP-03 sweep.")
    parser.add_argument("--config", default="configs/experiments/exp03_rq3_real_traces.yaml")
    args = parser.parse_args()

    run_dir = run_exp03_sweep(args.config)
    print(f"RUN_DIR={run_dir}")
