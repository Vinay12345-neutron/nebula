#!/usr/bin/env python3
"""
Publication Figure Generator for TierMoE EXP-03 (RQ3 / Hypothesis H3).
Visualizes hit rates, CXL traffic, and expert co-activation structures
derived from authentic Qwen3-30B-A3B forward passes.
"""

import argparse
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def plot_exp03(run_dir: str, output_dir: str = "figures") -> None:
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
        "Nebula-Batch-Aware-CoActivation": "TierMoE-Batch-Aware-CoActivation"
    })

    plt.rcParams.update({
        "font.family": "serif",
        "font.size": 11,
        "axes.labelsize": 12,
        "axes.titlesize": 13,
        "xtick.labelsize": 10,
        "ytick.labelsize": 10,
        "legend.fontsize": 10,
        "figure.titlesize": 14
    })

    datasets = df["dataset"].unique().tolist()
    algos = ["Baseline-0-Fast-Memory-Only", "Baseline-2-Static-Global-Frequency", "TierMoE-Batch-Aware-Greedy", "TierMoE-Batch-Aware-CoActivation"]
    colors = {"Baseline-0-Fast-Memory-Only": "#2ca02c", "Baseline-2-Static-Global-Frequency": "#7f7f7f", "TierMoE-Batch-Aware-Greedy": "#1f77b4", "TierMoE-Batch-Aware-CoActivation": "#9467bd"}
    markers = {"Baseline-0-Fast-Memory-Only": "o", "Baseline-2-Static-Global-Frequency": "s", "TierMoE-Batch-Aware-Greedy": "D", "TierMoE-Batch-Aware-CoActivation": "*"}

    # Figure 1: Hit Rate across batch sizes for GSM8K vs ShareGPT (at alpha_mem = 0.25)
    fig, axes = plt.subplots(1, len(datasets), figsize=(6 * len(datasets), 5), sharey=True)
    if len(datasets) == 1:
        axes = [axes]

    for idx, d_name in enumerate(datasets):
        ax = axes[idx]
        sub = df[(df["dataset"] == d_name) & (df["fast_memory_ratio"] == 0.25)]
        for algo in algos:
            algo_sub = sub[sub["algorithm"] == algo].sort_values("batch_size")
            if not algo_sub.empty:
                ax.plot(
                    algo_sub["batch_size"],
                    algo_sub["overall_hit_rate"] * 100.0,
                    label=algo.replace("Baseline-", "B").replace("TierMoE-", ""),
                    color=colors.get(algo, "black"),
                    marker=markers.get(algo, "o"),
                    linewidth=2.0,
                    markersize=7
                )
        ax.set_title(f"Qwen3-30B-A3B: {d_name.upper()} (α = 0.25)")
        ax.set_xlabel("Concurrent Batch Size (B)")
        ax.set_xticks([4, 8, 16, 32])
        ax.grid(True, linestyle="--", alpha=0.5)
        if idx == 0:
            ax.set_ylabel("Fast Memory Hit Rate (%)")
            ax.legend(frameon=True, loc="lower left")

    plt.tight_layout()
    fig1_path = os.path.join(output_dir, "exp03_hit_rate_qwen3.png")
    plt.savefig(fig1_path, dpi=300)
    plt.close()
    print(f"  * Generated Figure: {fig1_path}")

    # Figure 2: CXL Traffic across batch sizes
    fig, axes = plt.subplots(1, len(datasets), figsize=(6 * len(datasets), 5), sharey=True)
    if len(datasets) == 1:
        axes = [axes]

    for idx, d_name in enumerate(datasets):
        ax = axes[idx]
        sub = df[(df["dataset"] == d_name) & (df["fast_memory_ratio"] == 0.25)]
        for algo in algos:
            algo_sub = sub[sub["algorithm"] == algo].sort_values("batch_size")
            if not algo_sub.empty:
                ax.plot(
                    algo_sub["batch_size"],
                    algo_sub["cxl_traffic_mb"] / 1024.0,  # GB
                    label=algo.replace("Baseline-", "B").replace("TierMoE-", ""),
                    color=colors.get(algo, "black"),
                    marker=markers.get(algo, "o"),
                    linewidth=2.0,
                    markersize=7
                )
        ax.set_title(f"CXL Traffic: {d_name.upper()} (α = 0.25)")
        ax.set_xlabel("Concurrent Batch Size (B)")
        ax.set_xticks([4, 8, 16, 32])
        ax.grid(True, linestyle="--", alpha=0.5)
        if idx == 0:
            ax.set_ylabel("Total CXL Traffic (GB)")
            ax.legend(frameon=True, loc="upper left")

    plt.tight_layout()
    fig2_path = os.path.join(output_dir, "exp03_cxl_traffic_qwen3.png")
    plt.savefig(fig2_path, dpi=300)
    plt.close()
    print(f"  * Generated Figure: {fig2_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Plot TierMoE EXP-03 figures.")
    parser.add_argument("--run-dir", required=True, help="Path to run directory.")
    args = parser.parse_args()

    plot_exp03(args.run_dir)
