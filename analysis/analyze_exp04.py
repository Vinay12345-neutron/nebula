#!/usr/bin/env python3
"""
Statistical Analysis Module for Phase 7: EXP-04 (Broader Published Baselines).
Evaluates TierMoE-Batch-Aware-Greedy against:
- Baseline 4: Predictive Activation-Aware (MoE-Infinity / ProMoE style)
- Baseline 5: CXL-MoE Demand-LRU Hardware Tiering
- Baseline 3: Single-Request isolated control
- Baseline 2: Static LFU
"""

import argparse
import json
import os
import sys
from typing import Any, Dict, List
import numpy as np
import pandas as pd
from scipy import stats


def analyze_exp04(run_dir: str) -> Dict[str, Any]:
    print(f"\n[Running Statistical Analysis on Phase 7 EXP-04: {run_dir}]")

    summary_file = os.path.join(run_dir, "summary_metrics.parquet")
    if not os.path.exists(summary_file):
        summary_file = os.path.join(run_dir, "summary_metrics.json")
        df = pd.read_json(summary_file)
    else:
        df = pd.read_parquet(summary_file)

    # Standardize names
    df["algorithm"] = df["algorithm"].replace({
        "Nebula-Batch-Aware-Greedy": "TierMoE-Batch-Aware-Greedy",
        "Baseline-0-Fast-Memory-Only": "Baseline-0-HBM-Only"
    })

    algos = df["algorithm"].unique().tolist()
    print(f"  * Evaluated Algorithms: {algos}")

    constrained = df[df["is_capacity_constrained"] == True].copy()
    findings: List[str] = []
    findings.append(f"Capacity-constrained evaluation rows: {len(constrained)} rows.")

    piv_hit = constrained.pivot_table(
        index=["batch_size", "fast_memory_ratio"],
        columns="algorithm",
        values="overall_hit_rate"
    )
    piv_traf = constrained.pivot_table(
        index=["batch_size", "fast_memory_ratio"],
        columns="algorithm",
        values="cxl_traffic_mb"
    )

    tiermoe_col = "TierMoE-Batch-Aware-Greedy"

    comparisons: Dict[str, Dict[str, float]] = {}

    for b_col, b_name in [
        ("Baseline-2-Static-LFU", "Static LFU"),
        ("Baseline-3-Single-Request", "Single-Request"),
        ("Baseline-4-Predictive-Activation-Aware", "Predictive (MoE-Infinity/ProMoE)"),
        ("Baseline-5-CXL-LRU-Tiering", "CXL-LRU Tiering (CXL-MoE)"),
    ]:
        if b_col in piv_hit.columns and tiermoe_col in piv_hit.columns:
            hit_delta = (piv_hit[tiermoe_col] - piv_hit[b_col]) * 100.0
            traf_red = (piv_traf[b_col] - piv_traf[tiermoe_col]) / piv_traf[b_col] * 100.0

            mean_hit_gain = float(hit_delta.mean())
            mean_traf_red = float(traf_red.mean())

            t_stat, p_val = stats.ttest_rel(piv_hit[tiermoe_col], piv_hit[b_col])

            comparisons[b_name] = {
                "mean_hit_rate_gain_pct": mean_hit_gain,
                "mean_cxl_traffic_reduction_pct": mean_traf_red,
                "t_stat": float(t_stat) if not np.isnan(t_stat) else 0.0,
                "p_val": float(p_val) if not np.isnan(p_val) else 1.0
            }

            findings.append(
                f"TierMoE vs {b_name}: +{mean_hit_gain:.2f}% hit rate gain, "
                f"{mean_traf_red:.2f}% CXL traffic reduction (t={t_stat:.2f}, p={p_val:.4f})."
            )

    print("\n--- Comparative Evaluation Findings ---")
    for f in findings:
        print(f"  * {f}")

    results_payload = {
        "run_dir": run_dir,
        "algorithms": algos,
        "findings": findings,
        "comparisons": comparisons,
        "constrained_pivot_hit": piv_hit.reset_index().to_dict(orient="records") if not piv_hit.empty else [],
        "constrained_pivot_traf": piv_traf.reset_index().to_dict(orient="records") if not piv_traf.empty else []
    }

    out_json = os.path.join(run_dir, "analysis_summary.json")
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(results_payload, f, indent=2)

    print(f"\nAnalysis written to: {out_json}")
    return results_payload


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Analyze Phase 7 EXP-04 results.")
    parser.add_argument("--run-dir", required=True, help="Path to run directory.")
    args = parser.parse_args()

    analyze_exp04(args.run_dir)
