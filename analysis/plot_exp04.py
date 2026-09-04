#!/usr/bin/env python3
"""
Publication Figure Generator for Phase 7: EXP-04 (Broader Published Baselines).
Generates comparative figures across all 6 algorithms:
- Baseline 0: HBM-Only
- Baseline 2: Static LFU
- Baseline 3: Single-Request
- Baseline 4: Predictive (MoE-Infinity / ProMoE)
- Baseline 5: CXL-LRU Tiering (CXL-MoE)
- Proposed: TierMoE-Batch-Aware-Greedy
"""

import argparse
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def plot_exp04(run_dir: str, output_dir: str = "figures") -> None:
    os.makedirs(output_dir, exist_ok=True)
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

    plt.rcParams.update({
        "font.family": "serif",
        "font.size": 11,
        "axes.labelsize": 12,
        "axes.titlesize": 13,
        "xtick.labelsize": 10,
        "ytick.labelsize": 10,
        "legend.fontsize": 9,
        "figure.titlesize": 14
    })

    algos_ordered = [
        "Baseline-0-HBM-Only",
        "Baseline-2-Static-LFU",
        "Baseline-3-Single-Request",
        "Baseline-4-Predictive-Activation-Aware",
        "Baseline-5-CXL-LRU-Tiering",
        "TierMoE-Batch-Aware-Greedy"
    ]

    labels_map = {
        "Baseline-0-HBM-Only": "B0: HBM-Only (Upper Bound)",
        "Baseline-2-Static-LFU": "B2: Static LFU",
        "Baseline-3-Single-Request": "B3: Single-Request Control",
        "Baseline-4-Predictive-Activation-Aware": "B4: Predictive (MoE-Infinity)",
        "Baseline-5-CXL-LRU-Tiering": "B5: CXL-LRU Tiering (CXL-MoE)",
        "TierMoE-Batch-Aware-Greedy": "TierMoE (Batch-Aware Greedy)"
    }

    colors = {
        "Baseline-0-HBM-Only": "#2ca02c",
        "Baseline-2-Static-LFU": "#7f7f7f",
        "Baseline-3-Single-Request": "#ff7f0e",
        "Baseline-4-Predictive-Activation-Aware": "#8c564b",
        "Baseline-5-CXL-LRU-Tiering": "#e377c2",
        "TierMoE-Batch-Aware-Greedy": "#1f77b4"
    }

    markers = {
        "Baseline-0-HBM-Only": "o",
        "Baseline-2-Static-LFU": "s",
        "Baseline-3-Single-Request": "^",
        "Baseline-4-Predictive-Activation-Aware": "v",
        "Baseline-5-CXL-LRU-Tiering": "P",
        "TierMoE-Batch-Aware-Greedy": "D"
    }

    sub = df[df["fast_memory_ratio"] == 0.25]

    # Figure 1: Comparative Hit Rate vs Batch Size
    fig, ax = plt.subplots(figsize=(8, 5.5))
    for algo in algos_ordered:
        a_sub = sub[sub["algorithm"] == algo].sort_values("batch_size")
        if not a_sub.empty:
            ax.plot(
                a_sub["batch_size"],
                a_sub["overall_hit_rate"] * 100.0,
                label=labels_map.get(algo, algo),
                color=colors.get(algo, "black"),
                marker=markers.get(algo, "o"),
                linewidth=2.2 if "TierMoE" in algo else 1.8,
                markersize=8 if "TierMoE" in algo else 6
            )
    ax.set_title("Qwen3-30B ShareGPT: Hit Rate vs. Published Baselines (α = 0.25)")
    ax.set_xlabel("Concurrent Batch Size (B)")
    ax.set_ylabel("Fast-Tier Hit Rate (%)")
    ax.set_xticks([4, 8, 16, 32])
    ax.grid(True, linestyle="--", alpha=0.5)
    ax.legend(frameon=True, loc="lower left")
    plt.tight_layout()

    fig1_path = os.path.join(output_dir, "exp04_comparative_hit_rate.png")
    plt.savefig(fig1_path, dpi=300)
    plt.close()
    print(f"  * Generated Figure: {fig1_path}")

    # Figure 2: Total CXL Traffic (GB)
    fig, ax = plt.subplots(figsize=(8, 5.5))
    for algo in algos_ordered:
        a_sub = sub[sub["algorithm"] == algo].sort_values("batch_size")
        if not a_sub.empty:
            ax.plot(
                a_sub["batch_size"],
                a_sub["cxl_traffic_mb"] / 1024.0,
                label=labels_map.get(algo, algo),
                color=colors.get(algo, "black"),
                marker=markers.get(algo, "o"),
                linewidth=2.2 if "TierMoE" in algo else 1.8,
                markersize=8 if "TierMoE" in algo else 6
            )
    ax.set_title("Qwen3-30B ShareGPT: CXL Parameter Traffic (α = 0.25)")
    ax.set_xlabel("Concurrent Batch Size (B)")
    ax.set_ylabel("Total CXL Traffic (GB)")
    ax.set_xticks([4, 8, 16, 32])
    ax.grid(True, linestyle="--", alpha=0.5)
    ax.legend(frameon=True, loc="upper left")
    plt.tight_layout()

    fig2_path = os.path.join(output_dir, "exp04_comparative_cxl_traffic.png")
    plt.savefig(fig2_path, dpi=300)
    plt.close()
    print(f"  * Generated Figure: {fig2_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Plot Phase 7 EXP-04 figures.")
    parser.add_argument("--run-dir", required=True, help="Path to run directory.")
    args = parser.parse_args()

    plot_exp04(args.run_dir)
