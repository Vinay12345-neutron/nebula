#!/usr/bin/env python3
"""
Statistical Analysis Module for EXP-03 (RQ3 / Hypothesis H3).
Evaluates TierMoE Co-Activation vs Greedy (frequency-only) and Static LFU on
authentic Qwen3-30B-A3B traces across GSM8K and ShareGPT workloads.
"""

import argparse
import json
import os
import sys
from typing import Any, Dict, List
import numpy as np
import pandas as pd
from scipy import stats


def analyze_exp03(run_dir: str) -> Dict[str, Any]:
    print(f"\n[Running Statistical Analysis on EXP-03: {run_dir}]")

    summary_file = os.path.join(run_dir, "summary_metrics.parquet")
    if not os.path.exists(summary_file):
        summary_file = os.path.join(run_dir, "summary_metrics.json")
        df = pd.read_json(summary_file)
    else:
        df = pd.read_parquet(summary_file)

    # Standardize names
    df["algorithm"] = df["algorithm"].replace({
        "Nebula-Batch-Aware-Greedy": "TierMoE-Batch-Aware-Greedy",
        "Nebula-Batch-Aware-CoActivation": "TierMoE-Batch-Aware-CoActivation"
    })

    datasets = df["dataset"].unique().tolist()
    print(f"  * Evaluated Datasets: {datasets}")

    findings: List[str] = []
    h3_status = "INCONCLUSIVE"

    # Restrict to capacity-constrained conditions
    constrained = df[df["is_capacity_constrained"] == True].copy()
    findings.append(f"Total capacity-constrained conditions evaluated: {len(constrained)} settings.")

    # Pivot table: CoActivation vs Greedy vs LFU
    piv_hit = constrained.pivot_table(
        index=["dataset", "batch_size", "fast_memory_ratio"],
        columns="algorithm",
        values="overall_hit_rate"
    )
    piv_traf = constrained.pivot_table(
        index=["dataset", "batch_size", "fast_memory_ratio"],
        columns="algorithm",
        values="cxl_traffic_mb"
    )

    coact_col = "TierMoE-Batch-Aware-CoActivation"
    greedy_col = "TierMoE-Batch-Aware-Greedy"
    lfu_col = "Baseline-2-Static-LFU"

    if coact_col in piv_hit.columns and greedy_col in piv_hit.columns:
        hit_diff_coact_vs_greedy = (piv_hit[coact_col] - piv_hit[greedy_col]) * 100.0
        traf_red_coact_vs_greedy = (piv_traf[greedy_col] - piv_traf[coact_col]) / piv_traf[greedy_col] * 100.0

        hit_diff_coact_vs_lfu = (piv_hit[coact_col] - piv_hit[lfu_col]) * 100.0
        traf_red_coact_vs_lfu = (piv_traf[lfu_col] - piv_traf[coact_col]) / piv_traf[lfu_col] * 100.0

        avg_hit_gain_vs_greedy = float(hit_diff_coact_vs_greedy.mean())
        avg_traf_red_vs_greedy = float(traf_red_coact_vs_greedy.mean())

        avg_hit_gain_vs_lfu = float(hit_diff_coact_vs_lfu.mean())
        avg_traf_red_vs_lfu = float(traf_red_coact_vs_lfu.mean())

        findings.append(f"CoActivation vs Static LFU: +{avg_hit_gain_vs_lfu:.2f}% hit rate gain, {avg_traf_red_vs_lfu:.2f}% CXL traffic reduction.")
        findings.append(f"CoActivation vs Greedy (Pure Frequency): {avg_hit_gain_vs_greedy:+.2f}% hit rate difference, {avg_traf_red_vs_greedy:+.2f}% CXL traffic reduction.")

        # Paired t-test between CoActivation and Greedy
        t_stat, p_val = stats.ttest_rel(piv_hit[coact_col], piv_hit[greedy_col])
        findings.append(f"Paired t-test (CoActivation vs Greedy Hit Rate): t = {t_stat:.3f}, p = {p_val:.4f}.")

        if avg_hit_gain_vs_greedy > 0.5 and p_val < 0.05:
            h3_status = "SUPPORTED"
            findings.append("Hypothesis H3 SUPPORTED: Exploiting temporal expert co-activation provides statistically significant gains over pure frequency-based greedy placement under authentic workloads.")
        elif avg_hit_gain_vs_greedy >= -0.2:
            h3_status = "PARTIALLY SUPPORTED / PARITY"
            findings.append("Hypothesis H3 PARITY: Co-activation matches pure frequency placement under online decoding, but does not provide statistically significant separation over the batch-aware greedy heuristic.")
        else:
            h3_status = "NOT SUPPORTED"
            findings.append("Hypothesis H3 NOT SUPPORTED: Co-activation does not outperform pure frequency greedy placement.")

    print(f"\n--- Hypothesis H3 Formal Assessment: [{h3_status}] ---")
    for f in findings:
        print(f"  * {f}")

    results_payload = {
        "run_dir": run_dir,
        "datasets": datasets,
        "h3_status": h3_status,
        "findings": findings,
        "constrained_pivot_hit": piv_hit.reset_index().to_dict(orient="records") if not piv_hit.empty else [],
        "constrained_pivot_traf": piv_traf.reset_index().to_dict(orient="records") if not piv_traf.empty else []
    }

    out_json = os.path.join(run_dir, "analysis_summary.json")
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(results_payload, f, indent=2)

    print(f"\nAnalysis written to: {out_json}")
    return results_payload


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Analyze TierMoE EXP-03 results.")
    parser.add_argument("--run-dir", required=True, help="Path to run directory.")
    args = parser.parse_args()

    analyze_exp03(args.run_dir)
