#!/usr/bin/env python3
"""
Experiment 05B Runner: Detailed CXLMemSim Memory-System Validation.
Evaluates TierMoE-Batch-Aware-Greedy vs. Baseline-3-Single-Request across
exactly 10 controlled conditions on authentic Qwen3-30B-A3B ShareGPT routing traces
using the CXLMemSim memory-system simulation adapter.
"""

import argparse
import hashlib
import json
import os
import sys
import time
from typing import Any, Dict, List, Tuple
import numpy as np
import pandas as pd
import yaml

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.evaluation.runner import ALGORITHM_MAP
from src.simulator.cxlmemsim_adapter import CXLMemSimTierSimulator, EXPERT_SIZE_BYTES, CACHE_LINE_SIZE, LINES_PER_EXPERT
from src.workload.generator import ConcurrentWorkloadGenerator
from src.workload.trace_schema import RoutingTrace


def run_exp05b_experiment(config_path: str = "configs/experiments/exp05b_rq4_cxlmemsim_validation.yaml") -> str:
    print("===========================================================================")
    print("  PROJECT TIERMOE: EXP-05B — DETAILED CXLMemSim VALIDATION")
    print("  Evaluating Single-Request vs. TierMoE-Batch-Aware-Greedy")
    print(f"  Config: {config_path}")
    print("===========================================================================")

    with open(config_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    wl_cfg = cfg.get("workload", {})
    trace_path = wl_cfg.get("trace_file", "data/traces/qwen3_sharegpt_trace.parquet")
    batch_sizes = wl_cfg.get("batch_sizes", [8, 16, 32])
    fast_cap = cfg.get("memory", {}).get("fast_capacity_experts", 32)
    algo_keys = cfg.get("algorithms", ["baseline_3_single_request", "tiermoe_batch_aware_greedy"])
    results_base = cfg.get("outputs", {}).get("results_dir", "results/exp05b_rq4_cxlmemsim_validation")
    eval_conditions = cfg.get("evaluation_conditions", [])

    if not os.path.exists(trace_path):
        raise FileNotFoundError(f"Trace file not found: {trace_path}.")

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    run_hash = hashlib.md5(f"EXP-05B_{timestamp}".encode()).hexdigest()[:8]
    run_dir = os.path.join(results_base, f"run_{timestamp}_{run_hash}")
    os.makedirs(run_dir, exist_ok=True)
    os.makedirs(os.path.join(run_dir, "figures"), exist_ok=True)

    with open(os.path.join(run_dir, "config_snapshot.yaml"), "w", encoding="utf-8") as f:
        yaml.dump(cfg, f, default_flow_style=False)

    print(f"\n[1. Loading Authentic Routing Trace: {trace_path}]")
    df_trace = pd.read_parquet(trace_path)
    trace = RoutingTrace.from_dataframe(
        df=df_trace,
        model_name="Qwen/Qwen3-30B-A3B-Instruct-2507",
        num_experts=128,
        top_k=8,
        num_layers=48
    )
    print(f"  Loaded {len(trace.events):,d} authentic routing events across {trace.num_layers} layers.")

    workload_gen = ConcurrentWorkloadGenerator(trace)

    print(f"\n[2. Precomputing Placement Decisions for B in {batch_sizes} at C={fast_cap}]")
    # Store decisions per (batch_size, algo_key)
    decisions_cache: Dict[Tuple[int, str], List[Any]] = {}
    solvers_cache: Dict[str, Any] = {}
    working_set_cache: Dict[int, float] = {}

    for batch_size in batch_sizes:
        batch_events = list(workload_gen.generate_batches(batch_size=batch_size))
        avg_ws = float(np.mean([len(be.expert_frequency) for be in batch_events])) if batch_events else 0.0
        working_set_cache[batch_size] = avg_ws
        print(f"  * Batch Size {batch_size:2d}: {len(batch_events)} steps (Avg Working Set: {avg_ws:.1f} experts)")

        for algo_key in algo_keys:
            solver_cls = ALGORITHM_MAP[algo_key]
            solver = solver_cls(num_experts=128)
            solver.reset()
            solvers_cache[algo_key] = solver

            current_fast_tier = None
            decs = []
            for b_ev in batch_events:
                dec = solver.solve(
                    batch_event=b_ev,
                    fast_capacity=fast_cap,
                    current_fast_tier=current_fast_tier
                )
                decs.append(dec)
                current_fast_tier = dec.fast_resident_experts
            decisions_cache[(batch_size, algo_key)] = decs

    print(f"\n[3. Executing CXLMemSim Simulation Across Exactly 10 Conditions]")
    all_results: List[Dict[str, Any]] = []
    condition_idx = 0

    for cond in eval_conditions:
        b = cond["batch_size"]
        bw = cond["bandwidth_gbps"]
        lat = cond["latency_ns"]
        is_core = cond["is_core"]

        simulator = CXLMemSimTierSimulator(
            bandwidth_gbps=bw,
            latency_penalty_ns=lat,
            expert_size_bytes=EXPERT_SIZE_BYTES
        )

        for algo_key in algo_keys:
            condition_idx += 1
            decs = decisions_cache[(b, algo_key)]
            solver = solvers_cache[algo_key]

            t_sim0 = time.perf_counter()
            summary = simulator.simulate_run(algorithm_name=solver.name, decisions=decs)
            sim_time_sec = time.perf_counter() - t_sim0

            res_dict = summary.to_dict()
            total_cxl_bytes = summary.total_cxl_traffic_mb * 1024 * 1024
            total_cachelines = summary.total_transfers_count * LINES_PER_EXPERT

            delta_cxlmemsim_vs_ana_ms = summary.total_cxlmemsim_transfer_time_ms - summary.total_analytical_transfer_time_ms
            delta_cxlmemsim_vs_ana_pct = (delta_cxlmemsim_vs_ana_ms / summary.total_analytical_transfer_time_ms * 100.0) if summary.total_analytical_transfer_time_ms > 0 else 0.0

            res_dict.update({
                "condition_id": condition_idx,
                "algo_key": algo_key,
                "batch_size": b,
                "fast_capacity_experts": fast_cap,
                "fast_memory_ratio": 0.25,
                "avg_working_set_experts": working_set_cache[b],
                "cxl_bandwidth_gbps": bw,
                "cxl_latency_ns": lat,
                "is_core_condition": is_core,
                "total_cxl_bytes": total_cxl_bytes,
                "total_cachelines_simulated": total_cachelines,
                "cxlmemsim_transfer_time_s": summary.total_cxlmemsim_transfer_time_ms / 1e3,
                "analytical_transfer_time_s": summary.total_analytical_transfer_time_ms / 1e3,
                "delta_cxlmemsim_vs_ana_ms": delta_cxlmemsim_vs_ana_ms,
                "delta_cxlmemsim_vs_ana_pct": delta_cxlmemsim_vs_ana_pct,
                "simulation_runtime_seconds": sim_time_sec
            })
            all_results.append(res_dict)

            print(f"  [{condition_idx:2d}/10] B={b:2d} | BW={bw:4.1f} GB/s | Lat={lat:5.1f} ns | {solver.name:<25} | "
                  f"HitRate={summary.overall_hit_rate*100:5.2f}% | Transfers={summary.total_transfers_count:5,d} | "
                  f"CXLMemSim={summary.total_cxlmemsim_transfer_time_ms/1e3:8.3f}s | Ana={summary.total_analytical_transfer_time_ms/1e3:8.3f}s | "
                  f"SimTime={sim_time_sec:.3f}s")

    # Save summary files
    df_results = pd.DataFrame(all_results)
    parquet_path = os.path.join(run_dir, "summary_metrics.parquet")
    json_path = os.path.join(run_dir, "summary_metrics.json")
    df_results.to_parquet(parquet_path, index=False)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2)

    print(f"\n[+] Raw results written to:")
    print(f"    * {parquet_path}")
    print(f"    * {json_path}")

    return run_dir


if __name__ == "__main__":
    run_exp05b_experiment()
