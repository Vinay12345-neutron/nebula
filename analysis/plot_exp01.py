#!/usr/bin/env python3
"""
Publication-Grade Plotting Module for Corrected EXP-01 (TierMoE).
Renders multi-seed averaged comparative Pareto curves, hit rate scaling, and CXL traffic distributions.
"""

import argparse
import os
import sys
from typing import List, Optional
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def generate_plots(run_dir: str, output_dir: str = "figures/exp01_rq1_batch_aware") -> List[str]:
    print(f"\n[Rendering Publication Figures from {run_dir}]")
    os.makedirs(output_dir, exist_ok=True)

    summary_file = os.path.join(run_dir, "summary_metrics.parquet")
    if not os.path.exists(summary_file):
        summary_file = os.path.join(run_dir, "summary_metrics.json")
        df = pd.read_json(summary_file)
    else:
        df = pd.read_parquet(summary_file)

    seeds = df["seed"].unique().tolist() if "seed" in df.columns else [42]
    num_seeds = len(seeds)

    # Standardize algorithm names for backward compatibility
    df["algorithm"] = df["algorithm"].replace({
        "Nebula-Batch-Aware-Greedy": "TierMoE-Batch-Aware-Greedy",
        "Nebula-Batch-Aware-CoActivation": "TierMoE-Batch-Aware-CoActivation"
    })

    # Average across seeds
    grouped = df.groupby(["algorithm", "batch_size", "fast_memory_ratio"]).agg(
        overall_hit_rate=("overall_hit_rate", "mean"),
        hit_rate_sem=("overall_hit_rate", lambda x: x.std() / np.sqrt(len(x)) if len(x) > 1 else 0.0),
        cxl_traffic_mb=("cxl_traffic_mb", "mean"),
        traffic_sem=("cxl_traffic_mb", lambda x: x.std() / np.sqrt(len(x)) if len(x) > 1 else 0.0),
        avg_solver_time_us=("avg_solver_time_us", "mean")
    ).reset_index()

    # Styling settings
    plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")
    plt.rcParams.update({
        "font.size": 11,
        "font.family": "sans-serif",
        "axes.labelsize": 12,
        "axes.titlesize": 13,
        "xtick.labelsize": 10,
        "ytick.labelsize": 10,
        "legend.fontsize": 10,
        "figure.titlesize": 14,
        "lines.linewidth": 2.0,
        "lines.markersize": 7,
    })

    algo_colors = {
        "Baseline-0-HBM-Only": "#2ca02c",              # Green
        "Baseline-1-Naive-Overflow": "#7f7f7f",        # Gray
        "Baseline-2-Static-LFU": "#ff7f0e",            # Orange
        "Baseline-3-Single-Request": "#d62728",        # Red
        "TierMoE-Batch-Aware-Greedy": "#1f77b4",       # Blue
        "TierMoE-Batch-Aware-CoActivation": "#9467bd", # Purple
    }

    algo_markers = {
        "Baseline-0-HBM-Only": "o",
        "Baseline-1-Naive-Overflow": "v",
        "Baseline-2-Static-LFU": "s",
        "Baseline-3-Single-Request": "^",
        "TierMoE-Batch-Aware-Greedy": "D",
        "TierMoE-Batch-Aware-CoActivation": "*",
    }

    generated_files = []

    # -------------------------------------------------------------
    # Figure 1: Hit Rate vs. Fast Memory Capacity Ratio (at B=32)
    # -------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(7, 4.5), dpi=300)
    target_b = 32 if 32 in grouped["batch_size"].values else grouped["batch_size"].max()
    df_b = grouped[grouped["batch_size"] == target_b]

    for algo in df_b["algorithm"].unique():
        sub = df_b[df_b["algorithm"] == algo].sort_values("fast_memory_ratio")
        ax.errorbar(
            sub["fast_memory_ratio"] * 100.0,
            sub["overall_hit_rate"] * 100.0,
            yerr=sub["hit_rate_sem"] * 100.0 if num_seeds > 1 else None,
            label=algo,
            color=algo_colors.get(algo, "#333333"),
            marker=algo_markers.get(algo, "o"),
            capsize=3,
            alpha=0.9
        )

    ax.set_xlabel("Fast Memory Capacity Budget (% of Total Expert Footprint)")
    ax.set_ylabel("Fast-Tier Expert Hit Rate (%)")
    ax.set_title(f"TierMoE Fast-Tier Hit Rate vs. Memory Budget (Batch Size B = {target_b}, {num_seeds} Seeds)")
    ax.set_ylim(0, 105)
    ax.legend(frameon=True, loc="lower right")
    plt.tight_layout()
    fig1_path = os.path.join(output_dir, "fig1_hit_rate_vs_memory_budget.png")
    fig.savefig(fig1_path)
    plt.close(fig)
    generated_files.append(fig1_path)

    # -------------------------------------------------------------
    # Figure 2: CXL Parameter Traffic vs. Batch Size (at 50% Capacity)
    # -------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(7, 4.5), dpi=300)
    df_half = grouped[grouped["fast_memory_ratio"] == 0.5]

    for algo in df_half["algorithm"].unique():
        sub = df_half[df_half["algorithm"] == algo].sort_values("batch_size")
        ax.errorbar(
            sub["batch_size"],
            sub["cxl_traffic_mb"] / 1024.0,  # in GB
            yerr=sub["traffic_sem"] / 1024.0 if num_seeds > 1 else None,
            label=algo,
            color=algo_colors.get(algo, "#333333"),
            marker=algo_markers.get(algo, "o"),
            capsize=3,
            alpha=0.9
        )

    ax.set_xlabel("Concurrent Batch Size (B)")
    ax.set_ylabel("CXL Parameter Traffic (GB)")
    ax.set_title(f"TierMoE CXL Traffic vs. Batch Size (50% Fast-Memory Budget, {num_seeds} Seeds)")
    ax.legend(frameon=True, loc="upper left")
    plt.tight_layout()
    fig2_path = os.path.join(output_dir, "fig2_cxl_traffic_vs_batch_size.png")
    fig.savefig(fig2_path)
    plt.close(fig)
    generated_files.append(fig2_path)

    # -------------------------------------------------------------
    # Figure 3: Solver Execution Overhead Distribution
    # -------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(7, 4.5), dpi=300)
    solver_df = grouped.groupby("algorithm")["avg_solver_time_us"].mean().reset_index()

    bars = ax.bar(
        range(len(solver_df)),
        solver_df["avg_solver_time_us"],
        color=[algo_colors.get(a, "#333333") for a in solver_df["algorithm"]],
        alpha=0.85,
        edgecolor="black"
    )
    ax.set_xticks(range(len(solver_df)))
    ax.set_xticklabels(solver_df["algorithm"], rotation=25, ha="right")
    ax.set_ylabel("Average Solver Execution Time (μs / Step)")
    ax.set_title("Placement Solver Computational Overhead")
    ax.set_yscale("log")
    plt.tight_layout()
    fig3_path = os.path.join(output_dir, "fig3_solver_overhead_tradeoff.png")
    fig.savefig(fig3_path)
    plt.close(fig)
    generated_files.append(fig3_path)

    # -------------------------------------------------------------
    # Figure 4: Pareto Frontier: Hit Rate vs. CXL Traffic
    # -------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(7, 4.5), dpi=300)
    agg_df = grouped.groupby("algorithm").agg(
        hit_rate=("overall_hit_rate", "mean"),
        traffic_gb=("cxl_traffic_mb", lambda x: x.mean() / 1024.0)
    ).reset_index()

    for _, row in agg_df.iterrows():
        algo = row["algorithm"]
        ax.scatter(
            row["traffic_gb"],
            row["hit_rate"] * 100.0,
            color=algo_colors.get(algo, "#333333"),
            marker=algo_markers.get(algo, "o"),
            s=120,
            label=algo,
            zorder=5
        )
        ax.annotate(
            algo.replace("Baseline-", "B-").replace("TierMoE-", "").replace("Nebula-", ""),
            (row["traffic_gb"], row["hit_rate"] * 100.0),
            textcoords="offset points",
            xytext=(5, 5),
            fontsize=9
        )

    ax.set_xlabel("Mean CXL Parameter Traffic (GB) [Lower is Better]")
    ax.set_ylabel("Mean Fast-Tier Hit Rate (%) [Higher is Better]")
    ax.set_title(f"TierMoE Algorithm Pareto Frontier ({num_seeds} Seeds Averaged)")
    ax.set_ylim(0, 105)
    plt.tight_layout()
    fig4_path = os.path.join(output_dir, "fig4_algorithm_pareto_curve.png")
    fig.savefig(fig4_path)
    plt.close(fig)
    generated_files.append(fig4_path)

    for p in generated_files:
        print(f"  * Generated: {p}")

    return generated_files


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate publication plots for TierMoE EXP-01.")
    parser.add_argument("--run-dir", required=True, help="Path to experiment run directory.")
    parser.add_argument("--output-dir", default="figures/exp01_rq1_batch_aware", help="Output figures directory.")
    args = parser.parse_args()

    generate_plots(args.run_dir, args.output_dir)
