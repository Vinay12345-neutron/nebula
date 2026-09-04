#!/usr/bin/env python3
"""
Plotting module for TierMoE EXP-02 (RQ2 / Hypothesis H2).
Generates publication-ready figures correlating request divergence, measured Jaccard overlap,
and placement performance under capacity-constrained CXL memory tiering.
"""

import argparse
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def plot_exp02(run_dir: str, output_dir: str = "figures") -> None:
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

    # Group across seeds
    agg = df.groupby(["algorithm", "batch_size", "fast_memory_ratio", "skew_alpha"]).agg({
        "overall_hit_rate": "mean",
        "cxl_traffic_mb": "mean",
        "avg_jaccard_overlap": "mean",
        "avg_request_divergence": "mean",
        "avg_expansion_ratio": "mean",
        "capacity_pressure_ratio": "mean"
    }).reset_index()

    # Style configuration
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

    # -------------------------------------------------------------
    # Figure 1: Hit Rate vs. Zipf Skew for B=16 & B=32 (Capacity-Constrained)
    # -------------------------------------------------------------
    fig, axes = plt.subplots(1, 2, figsize=(12, 5), sharey=True)
    constrained_ratio = 0.25
    algos = ["Baseline-0-Fast-Memory-Only", "Baseline-2-Static-Global-Frequency", "Baseline-3-Single-Request", "TierMoE-Batch-Aware-Greedy"]
    colors = {"Baseline-0-Fast-Memory-Only": "#2ca02c", "Baseline-2-Static-Global-Frequency": "#7f7f7f", "Baseline-3-Single-Request": "#d62728", "TierMoE-Batch-Aware-Greedy": "#1f77b4"}
    markers = {"Baseline-0-Fast-Memory-Only": "o", "Baseline-2-Static-Global-Frequency": "s", "Baseline-3-Single-Request": "^", "TierMoE-Batch-Aware-Greedy": "D"}

    for idx, b_size in enumerate([16, 32]):
        ax = axes[idx]
        sub = agg[(agg["batch_size"] == b_size) & (agg["fast_memory_ratio"] == constrained_ratio)]
        for algo in algos:
            algo_sub = sub[sub["algorithm"] == algo].sort_values("skew_alpha")
            if not algo_sub.empty:
                ax.plot(
                    algo_sub["skew_alpha"],
                    algo_sub["overall_hit_rate"] * 100.0,
                    label=algo.replace("Baseline-", "B").replace("TierMoE-", ""),
                    color=colors.get(algo, "black"),
                    marker=markers.get(algo, "o"),
                    linewidth=2.0,
                    markersize=6
                )
        ax.set_title(f"Batch Size B = {b_size} (Cap Ratio α = {constrained_ratio})")
        ax.set_xlabel("Expert Popularity Skew (Zipf α)")
        ax.grid(True, linestyle="--", alpha=0.5)
        if idx == 0:
            ax.set_ylabel("Fast Memory Hit Rate (%)")
            ax.legend(frameon=True, loc="lower right")

    plt.tight_layout()
    fig1_path = os.path.join(output_dir, "exp02_hit_rate_vs_skew.png")
    plt.savefig(fig1_path, dpi=300)
    plt.close()
    print(f"  * Generated Figure: {fig1_path}")

    # -------------------------------------------------------------
    # Figure 2: Advantage vs. Measured Request Divergence
    # -------------------------------------------------------------
    fig, ax1 = plt.subplots(figsize=(7, 5))
    constrained = agg[agg["capacity_pressure_ratio"] > 1.0]
    piv_hit = constrained.pivot_table(index=["batch_size", "fast_memory_ratio", "skew_alpha"], columns="algorithm", values="overall_hit_rate")
    piv_traf = constrained.pivot_table(index=["batch_size", "fast_memory_ratio", "skew_alpha"], columns="algorithm", values="cxl_traffic_mb")
    piv_div = constrained.pivot_table(index=["batch_size", "fast_memory_ratio", "skew_alpha"], columns="algorithm", values="avg_request_divergence")

    if "TierMoE-Batch-Aware-Greedy" in piv_hit.columns and "Baseline-3-Single-Request" in piv_hit.columns:
        hit_gain = (piv_hit["TierMoE-Batch-Aware-Greedy"] - piv_hit["Baseline-3-Single-Request"]) * 100.0
        traf_red = (piv_traf["Baseline-3-Single-Request"] - piv_traf["TierMoE-Batch-Aware-Greedy"]) / piv_traf["Baseline-3-Single-Request"] * 100.0
        div_vals = piv_div["TierMoE-Batch-Aware-Greedy"]

        ax1.scatter(div_vals, hit_gain, color="#1f77b4", marker="D", s=50, label="Hit Rate Gain (%)")
        m, b = np.polyfit(div_vals, hit_gain, 1)
        x_seq = np.linspace(div_vals.min(), div_vals.max(), 50)
        ax1.plot(x_seq, m * x_seq + b, color="#1f77b4", linestyle="--", alpha=0.8, label=f"Trend (m={m:.1f})")

        ax1.set_xlabel("Measured Request Divergence (1 - Mean Jaccard Overlap)")
        ax1.set_ylabel("TierMoE Hit Rate Gain vs. Single-Request (%)", color="#1f77b4")
        ax1.tick_params(axis="y", labelcolor="#1f77b4")
        ax1.grid(True, linestyle="--", alpha=0.5)

        ax2 = ax1.twinx()
        ax2.scatter(div_vals, traf_red, color="#ff7f0e", marker="s", s=50, label="CXL Traffic Red. (%)")
        m2, b2 = np.polyfit(div_vals, traf_red, 1)
        ax2.plot(x_seq, m2 * x_seq + b2, color="#ff7f0e", linestyle=":", alpha=0.8, label=f"Trend (m={m2:.1f})")
        ax2.set_ylabel("CXL Parameter Traffic Reduction (%)", color="#ff7f0e")
        ax2.tick_params(axis="y", labelcolor="#ff7f0e")

        plt.title("TierMoE Advantage vs. Measured Request Divergence")
        fig2_path = os.path.join(output_dir, "exp02_advantage_vs_divergence.png")
        plt.tight_layout()
        plt.savefig(fig2_path, dpi=300)
        plt.close()
        print(f"  * Generated Figure: {fig2_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Plot TierMoE EXP-02 figures.")
    parser.add_argument("--run-dir", required=True, help="Path to run directory.")
    args = parser.parse_args()

    plot_exp02(args.run_dir)
