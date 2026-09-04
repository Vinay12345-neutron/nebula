#!/usr/bin/env python3
"""
Statistical Analysis Module for EXP-01.
Computes multi-seed distributions (Mean, Std, SEM), analyzes memory pressure regimes,
and rigorously evaluates Hypothesis H1 in capacity-constrained conditions for TierMoE.
"""

import argparse
import json
import os
import sys
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd


def analyze_run(run_dir: str) -> Dict[str, Any]:
    print(f"\n[Running Statistical Analysis on {run_dir}]")

    summary_file = os.path.join(run_dir, "summary_metrics.parquet")
    if not os.path.exists(summary_file):
        summary_file = os.path.join(run_dir, "summary_metrics.json")
        if not os.path.exists(summary_file):
            raise FileNotFoundError(f"No summary metrics found in {run_dir}")
        df = pd.read_json(summary_file)
    else:
        df = pd.read_parquet(summary_file)

    seeds = df["seed"].unique().tolist() if "seed" in df.columns else [42]
    num_seeds = len(seeds)
    print(f"  * Detected {num_seeds} evaluation seed(s): {seeds}")

    # 1. Multi-seed Statistical Aggregation (Mean, Std, SEM)
    grouped = df.groupby(["algorithm", "batch_size", "fast_memory_ratio"])
    agg_df = grouped.agg(
        mean_hit_rate=("overall_hit_rate", "mean"),
        std_hit_rate=("overall_hit_rate", "std"),
        sem_hit_rate=("overall_hit_rate", lambda x: x.std() / np.sqrt(len(x)) if len(x) > 1 else 0.0),
        mean_cxl_traffic_mb=("cxl_traffic_mb", "mean"),
        std_cxl_traffic_mb=("cxl_traffic_mb", "std"),
        sem_cxl_traffic_mb=("cxl_traffic_mb", lambda x: x.std() / np.sqrt(len(x)) if len(x) > 1 else 0.0),
        mean_demand_traffic_mb=("demand_cxl_traffic_mb", "mean") if "demand_cxl_traffic_mb" in df.columns else ("cxl_traffic_mb", "mean"),
        mean_prom_traffic_mb=("promotion_traffic_mb", "mean") if "promotion_traffic_mb" in df.columns else ("migration_volume_mb", "mean"),
        mean_migration_mb=("migration_volume_mb", "mean"),
        mean_solver_us=("avg_solver_time_us", "mean"),
        avg_working_set=("avg_working_set_experts", "mean") if "avg_working_set_experts" in df.columns else ("fast_capacity_experts", "mean"),
        fast_capacity=("fast_capacity_experts", "first") if "fast_capacity_experts" in df.columns else ("fast_memory_ratio", lambda x: int(128 * x.iloc[0])),
        pressure_ratio=("capacity_pressure_ratio", "mean") if "capacity_pressure_ratio" in df.columns else ("fast_memory_ratio", lambda x: 1.0),
        pressure_regime=("pressure_regime", "first") if "pressure_regime" in df.columns else ("fast_memory_ratio", lambda x: "unknown")
    ).reset_index()

    # Fill NaN stds with 0 for single seed
    agg_df["std_hit_rate"] = agg_df["std_hit_rate"].fillna(0.0)
    agg_df["std_cxl_traffic_mb"] = agg_df["std_cxl_traffic_mb"].fillna(0.0)

    print("\n--- Overall Algorithm Performance (Averaged across seeds) ---")
    overall = agg_df.groupby("algorithm").agg(
        mean_hit_rate=("mean_hit_rate", "mean"),
        mean_cxl_traffic_mb=("mean_cxl_traffic_mb", "mean"),
        mean_migration_mb=("mean_migration_mb", "mean"),
        mean_solver_us=("mean_solver_us", "mean")
    ).reset_index()
    print(overall.to_string(index=False))

    # 2. Pressure Regime Breakdown
    print("\n--- Memory Pressure Regime Characterization ---")
    regime_summary = agg_df[["batch_size", "fast_memory_ratio", "fast_capacity", "avg_working_set", "pressure_ratio", "pressure_regime"]].drop_duplicates()
    print(regime_summary.to_string(index=False))

    # 3. Rigorous Evaluation of Hypothesis H1
    # Filter strictly to conditions under capacity pressure (working_set > fast_capacity)
    constrained_conditions = agg_df[agg_df["avg_working_set"] > agg_df["fast_capacity"]].copy()

    h1_status = "INCONCLUSIVE"
    findings: List[str] = []

    if constrained_conditions.empty:
        h1_status = "INCONCLUSIVE"
        findings.append("No experimental conditions exceeded fast-tier capacity. Cannot evaluate H1.")
    else:
        pivot_hit = constrained_conditions.pivot_table(
            index=["batch_size", "fast_memory_ratio"],
            columns="algorithm",
            values="mean_hit_rate"
        )
        pivot_traffic = constrained_conditions.pivot_table(
            index=["batch_size", "fast_memory_ratio"],
            columns="algorithm",
            values="mean_cxl_traffic_mb"
        )

        greedy_col = "TierMoE-Batch-Aware-Greedy" if "TierMoE-Batch-Aware-Greedy" in pivot_hit.columns else ("Nebula-Batch-Aware-Greedy" if "Nebula-Batch-Aware-Greedy" in pivot_hit.columns else None)

        if greedy_col and "Baseline-3-Single-Request" in pivot_hit.columns:
            greedy_hits = pivot_hit[greedy_col]
            single_hits = pivot_hit["Baseline-3-Single-Request"]
            hit_deltas = greedy_hits - single_hits

            greedy_traf = pivot_traffic[greedy_col]
            single_traf = pivot_traffic["Baseline-3-Single-Request"]
            traf_reductions = (single_traf - greedy_traf) / single_traf * 100.0

            avg_hit_delta = float(hit_deltas.mean() * 100.0)
            avg_traf_reduction = float(traf_reductions.mean())

            findings.append(f"Capacity-constrained conditions evaluated: {len(hit_deltas)} settings.")
            findings.append(f"Average hit rate delta in constrained regime: +{avg_hit_delta:.2f}% ({greedy_col} vs Single-Request).")
            findings.append(f"Average CXL traffic reduction in constrained regime: {avg_traf_reduction:.2f}%.")

            if avg_hit_delta > 0.5 and avg_traf_reduction > 5.0:
                h1_status = "SUPPORTED"
                findings.append(f"Hypothesis H1 SUPPORTED: {greedy_col} significantly outperforms Single-Request under capacity pressure.")
            elif avg_hit_delta >= 0.0 and avg_traf_reduction >= 0.0:
                h1_status = "PARTIALLY SUPPORTED"
                findings.append(f"Hypothesis H1 PARTIALLY SUPPORTED: {greedy_col} shows modest advantage in capacity-constrained regime.")
            else:
                h1_status = "NOT SUPPORTED"
                findings.append(f"Hypothesis H1 NOT SUPPORTED: {greedy_col} does not outperform Single-Request under capacity pressure.")

    print(f"\n--- Hypothesis H1 Formal Assessment: [{h1_status}] ---")
    for f in findings:
        print(f"  * {f}")

    results_payload = {
        "run_dir": run_dir,
        "seeds": seeds,
        "h1_status": h1_status,
        "findings": findings,
        "overall_summary": overall.to_dict(orient="records"),
        "regime_summary": regime_summary.to_dict(orient="records")
    }

    out_json = os.path.join(run_dir, "analysis_summary.json")
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(results_payload, f, indent=2)

    print(f"\nAnalysis written to: {out_json}")
    return results_payload


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Analyze TierMoE EXP-01 results.")
    parser.add_argument("--run-dir", required=True, help="Path to experiment run directory.")
    args = parser.parse_args()

    analyze_run(args.run_dir)
