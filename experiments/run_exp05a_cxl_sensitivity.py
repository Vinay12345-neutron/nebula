#!/usr/bin/env python3
"""
Experiment 05A Runner: CXL Bandwidth & Latency Sensitivity Sweep (Phase 8: RQ4 / H4).
Evaluates TierMoE-Batch-Aware-Greedy vs. Static LFU and Single-Request baselines
across a controlled 3x3 grid of CXL bandwidths (16, 32, 64 GB/s) and CXL latencies (150, 300, 600 ns)
on authentic Qwen3-30B-A3B ShareGPT routing traces.
"""

import argparse
import hashlib
import json
import os
import sys
import time
from typing import Any, Dict, List
import numpy as np
import pandas as pd
import yaml

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.evaluation.runner import ALGORITHM_MAP
from src.simulator.cxl_model import CXLMemoryTierSimulator
from src.workload.generator import ConcurrentWorkloadGenerator
from src.workload.trace_schema import RoutingTrace


def run_exp05a_sweep(config_path: str = "configs/experiments/exp05a_rq4_cxl_sensitivity.yaml") -> str:
    print("===========================================================================")
    print("  PROJECT TIERMOE: PHASE 8 - EXP-05A (CXL SENSITIVITY SWEEP)")
    print("  Evaluating CXL Bandwidth (16, 32, 64 GB/s) & Latency (150, 300, 600 ns)")
    print(f"  Config: {config_path}")
    print("===========================================================================")

    with open(config_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    wl_cfg = cfg.get("workload", {})
    trace_path = wl_cfg.get("trace_file", "data/traces/qwen3_sharegpt_trace.parquet")
    batch_sizes = wl_cfg.get("batch_sizes", [8, 16, 32])
    mem_ratios = cfg.get("memory", {}).get("fast_memory_ratios", [0.25])
    algo_keys = cfg.get("algorithms", ["baseline_2_static_lfu", "baseline_3_single_request", "tiermoe_batch_aware_greedy"])
    results_base = cfg.get("outputs", {}).get("results_dir", "results/exp05a_rq4_cxl_sensitivity")

    cxl_cfg = cfg.get("cxl_simulation", {})
    bandwidths = cxl_cfg.get("bandwidths_gbps", [16.0, 32.0, 64.0])
    latencies = cxl_cfg.get("latencies_ns", [150.0, 300.0, 600.0])
    baseline_bw = cxl_cfg.get("baseline_bandwidth_gbps", 32.0)
    baseline_lat = cxl_cfg.get("baseline_latency_ns", 300.0)

    if not os.path.exists(trace_path):
        raise FileNotFoundError(f"Trace file not found: {trace_path}. Please run profiling first.")

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    run_hash = hashlib.md5(f"EXP-05A_{timestamp}".encode()).hexdigest()[:8]
    run_dir = os.path.join(results_base, f"run_{timestamp}_{run_hash}")
    os.makedirs(run_dir, exist_ok=True)

    # Save copy of configuration for reproducibility
    with open(os.path.join(run_dir, "config_snapshot.yaml"), "w", encoding="utf-8") as f:
        yaml.dump(cfg, f, default_flow_style=False)

    print(f"\n[Loading Authentic Trace: {trace_path}]")
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
    all_summaries: List[Dict[str, Any]] = []

    total_conditions = len(batch_sizes) * len(mem_ratios) * len(algo_keys) * len(bandwidths) * len(latencies)
    print(f"\n[Executing Sensitivity Sweep: {total_conditions} conditions]")
    print(f"  * Batch Sizes: {batch_sizes}")
    print(f"  * Fast Memory Ratios: {mem_ratios}")
    print(f"  * Algorithms: {algo_keys}")
    print(f"  * CXL Bandwidths: {bandwidths} GB/s")
    print(f"  * CXL Latencies: {latencies} ns")

    completed_count = 0

    for batch_size in batch_sizes:
        t_b0 = time.time()
        batch_events = list(workload_gen.generate_batches(batch_size=batch_size))
        avg_working_set = float(np.mean([len(be.expert_frequency) for be in batch_events])) if batch_events else 0.0

        for ratio in mem_ratios:
            fast_cap = max(1, int(128 * ratio))
            pressure_ratio = avg_working_set / fast_cap if fast_cap > 0 else 0.0
            regime = "no-pressure" if pressure_ratio <= 1.0 else ("capacity-pressure" if pressure_ratio < 1.5 else "severe-pressure")

            # Compute placement decisions once per algorithm (policy decisions are bandwidth/latency invariant)
            algo_decisions = {}
            algo_solvers = {}

            for algo_key in algo_keys:
                if algo_key not in ALGORITHM_MAP:
                    print(f"  [!] Skipping unknown algorithm: {algo_key}")
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

                algo_decisions[algo_key] = decisions
                algo_solvers[algo_key] = solver

            # Evaluate identical decisions across the 3x3 CXL parameter grid
            for bw in bandwidths:
                for lat in latencies:
                    simulator = CXLMemoryTierSimulator(
                        latency_penalty_ns=lat,
                        bandwidth_gbps=bw,
                        expert_size_bytes=268435456  # 256 MB per expert
                    )

                    for algo_key in algo_keys:
                        if algo_key not in algo_decisions:
                            continue

                        decisions = algo_decisions[algo_key]
                        solver = algo_solvers[algo_key]

                        summary = simulator.simulate_run(
                            algorithm_name=solver.name,
                            decisions=decisions
                        )

                        # Count total transfers and promotions
                        total_promotions = sum(len(d.promotions) for d in decisions)
                        total_unique_missing = sum(len(d.unique_missing_experts) for d in decisions)
                        total_transfers = total_promotions + total_unique_missing

                        summary_dict = summary.to_dict()
                        summary_dict.update({
                            "algo_key": algo_key,
                            "batch_size": batch_size,
                            "fast_memory_ratio": ratio,
                            "fast_capacity_experts": fast_cap,
                            "avg_working_set_experts": avg_working_set,
                            "capacity_pressure_ratio": pressure_ratio,
                            "pressure_regime": regime,
                            "is_capacity_constrained": bool(avg_working_set > fast_cap),
                            "cxl_bandwidth_gbps": bw,
                            "cxl_latency_ns": lat,
                            "is_baseline_config": bool(bw == baseline_bw and lat == baseline_lat),
                            "is_bandwidth_sweep_condition": bool(lat == baseline_lat),
                            "is_latency_sweep_condition": bool(bw == baseline_bw),
                            "total_promotions_count": total_promotions,
                            "total_unique_missing_count": total_unique_missing,
                            "total_transfers_count": total_transfers,
                            "modeled_cxl_transfer_time_s": summary.total_modeled_cxl_transfer_time_ms / 1e3
                        })
                        all_summaries.append(summary_dict)
                        completed_count += 1

        dt_b = time.time() - t_b0
        print(f"  [B={batch_size:2d}] Processed {len(algo_keys) * len(bandwidths) * len(latencies)} conditions in {dt_b:.2f}s (Working Set: {avg_working_set:.1f} experts)")

    summary_df = pd.DataFrame(all_summaries)
    summary_df.to_parquet(os.path.join(run_dir, "summary_metrics.parquet"), index=False)
    summary_df.to_json(os.path.join(run_dir, "summary_metrics.json"), orient="records", indent=2)

    print(f"\n[Execution Completed Successfully: {completed_count}/{total_conditions} conditions]")
    print(f"  Results saved to: {run_dir}")
    print("===========================================================================\n")
    return run_dir


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run TierMoE Phase 8 EXP-05A CXL sensitivity sweep.")
    parser.add_argument("--config", default="configs/experiments/exp05a_rq4_cxl_sensitivity.yaml")
    args = parser.parse_args()

    run_dir = run_exp05a_sweep(args.config)
