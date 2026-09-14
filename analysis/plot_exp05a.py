#!/usr/bin/env python3
"""
Publication Figure Generator for Phase 8: EXP-05A (CXL Sensitivity Sweep).
Generates publication-quality figures:
- Figure 1: CXL Bandwidth vs. Modeled CXL Transfer Time (fixed Latency = 300 ns, B = 32)
- Figure 2: CXL Latency vs. Modeled CXL Transfer Time (fixed Bandwidth = 32 GB/s, B = 32)
- Figure 3: TierMoE Transfer Time Reduction across Batch Sizes and Bandwidths
"""

import argparse
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def plot_exp05a(run_dir: str, output_dir: str = "figures") -> None:
    os.makedirs(output_dir, exist_ok=True)
    summary_file = os.path.join(run_dir, "summary_metrics.parquet")
    if not os.path.exists(summary_file):
        summary_file = os.path.join(run_dir, "summary_metrics.json")
        df = pd.read_json(summary_file)
    else:
        df = pd.read_parquet(summary_file)

    # Standardize algorithm names
    df["algorithm"] = df["algorithm"].replace({
        "Nebula-Batch-Aware-Greedy": "TierMoE-Batch-Aware-Greedy"
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

    algos_ordered = [
        "Baseline-2-Static-LFU",
        "Baseline-3-Single-Request",
        "TierMoE-Batch-Aware-Greedy"
    ]

    labels_map = {
        "Baseline-2-Static-LFU": "Static LFU (B2)",
        "Baseline-3-Single-Request": "Single-Request Control (B3)",
        "TierMoE-Batch-Aware-Greedy": "TierMoE (Batch-Aware Greedy)"
    }

    colors = {
        "Baseline-2-Static-LFU": "#7f7f7f",
        "Baseline-3-Single-Request": "#ff7f0e",
        "TierMoE-Batch-Aware-Greedy": "#1f77b4"
    }

    markers = {
        "Baseline-2-Static-LFU": "s",
        "Baseline-3-Single-Request": "^",
        "TierMoE-Batch-Aware-Greedy": "D"
    }

    # =========================================================================
    # FIGURE 1: CXL Bandwidth vs. Modeled Transfer Time (Fixed B=32, Latency=300ns)
    # =========================================================================
    sub_bw = df[(df["batch_size"] == 32) & (df["cxl_latency_ns"] == 300.0)]
    fig, ax = plt.subplots(figsize=(7.5, 5))

    for algo in algos_ordered:
        a_sub = sub_bw[sub_bw["algorithm"] == algo].sort_values("cxl_bandwidth_gbps")
        if not a_sub.empty:
            ax.plot(
                a_sub["cxl_bandwidth_gbps"],
                a_sub["modeled_cxl_transfer_time_s"],
                label=labels_map.get(algo, algo),
                color=colors.get(algo, "black"),
                marker=markers.get(algo, "o"),
                linewidth=2.4 if "TierMoE" in algo else 1.8,
                markersize=8 if "TierMoE" in algo else 6
            )

    ax.set_title("Modeled CXL Transfer Time vs. Bandwidth\n(Qwen3-30B ShareGPT, B=32, C=32, Latency=300ns)")
    ax.set_xlabel("CXL Link Bandwidth (GB/s)")
    ax.set_ylabel("Modeled CXL Parameter Transfer Time (s)")
    ax.set_xticks([16, 32, 64])
    ax.grid(True, linestyle="--", alpha=0.5)
    ax.legend(frameon=True, loc="upper right")
    plt.tight_layout()

    fig1_path = os.path.join(output_dir, "exp05a_cxl_bandwidth_sensitivity.png")
    plt.savefig(fig1_path, dpi=300)
    plt.close()
    print(f"  * Generated Figure 1: {fig1_path}")

    # =========================================================================
    # FIGURE 2: CXL Latency vs. Modeled Transfer Time (Fixed B=32, Bandwidth=32GB/s)
    # =========================================================================
    sub_lat = df[(df["batch_size"] == 32) & (df["cxl_bandwidth_gbps"] == 32.0)]
    fig, ax = plt.subplots(figsize=(7.5, 5))

    for algo in algos_ordered:
        a_sub = sub_lat[sub_lat["algorithm"] == algo].sort_values("cxl_latency_ns")
        if not a_sub.empty:
            ax.plot(
                a_sub["cxl_latency_ns"],
                a_sub["modeled_cxl_transfer_time_s"],
                label=labels_map.get(algo, algo),
                color=colors.get(algo, "black"),
                marker=markers.get(algo, "o"),
                linewidth=2.4 if "TierMoE" in algo else 1.8,
                markersize=8 if "TierMoE" in algo else 6
            )

    ax.set_title("Modeled CXL Transfer Time vs. Latency Penalty\n(Qwen3-30B ShareGPT, B=32, C=32, Bandwidth=32GB/s)")
    ax.set_xlabel("CXL Round-Trip Latency Overhead (ns)")
    ax.set_ylabel("Modeled CXL Parameter Transfer Time (s)")
    ax.set_xticks([150, 300, 600])
    ax.grid(True, linestyle="--", alpha=0.5)
    ax.legend(frameon=True, loc="upper left")
    plt.tight_layout()

    fig2_path = os.path.join(output_dir, "exp05a_cxl_latency_sensitivity.png")
    plt.savefig(fig2_path, dpi=300)
    plt.close()
    print(f"  * Generated Figure 2: {fig2_path}")

    # =========================================================================
    # FIGURE 3: Transfer Time Reduction & Advantage Across Configurations
    # =========================================================================
    # Compare TierMoE transfer time reduction vs Single-Request across all batch sizes & bandwidths (Latency=300ns)
    fig, ax = plt.subplots(figsize=(8.5, 5.2))
    batch_sizes = [8, 16, 32]
    bandwidths = [16.0, 32.0, 64.0]
    bar_width = 0.25
    x = np.arange(len(batch_sizes))

    for i, bw in enumerate(bandwidths):
        reductions = []
        for b in batch_sizes:
            base_time = df[
                (df["batch_size"] == b) & 
                (df["cxl_bandwidth_gbps"] == bw) & 
                (df["cxl_latency_ns"] == 300.0) & 
                (df["algorithm"] == "Baseline-3-Single-Request")
            ]["modeled_cxl_transfer_time_s"].values[0]

            tm_time = df[
                (df["batch_size"] == b) & 
                (df["cxl_bandwidth_gbps"] == bw) & 
                (df["cxl_latency_ns"] == 300.0) & 
                (df["algorithm"] == "TierMoE-Batch-Aware-Greedy")
            ]["modeled_cxl_transfer_time_s"].values[0]

            red_pct = (base_time - tm_time) / base_time * 100.0
            reductions.append(red_pct)

        offsets = x + (i - 1) * bar_width
        bars = ax.bar(offsets, reductions, width=bar_width, label=f"BW = {int(bw)} GB/s", alpha=0.85)
        for bar in bars:
            yval = bar.get_height()
            ax.text(
                bar.get_x() + bar.get_width() / 2.0,
                yval + 0.3,
                f"{yval:.1f}%",
                ha="center",
                va="bottom",
                fontsize=8.5
            )

    ax.set_title("TierMoE Transfer Time Reduction vs. Single-Request Control\n(Trace: Qwen3-30B ShareGPT, Latency = 300ns)")
    ax.set_xlabel("Concurrent Batch Size (B)")
    ax.set_ylabel("Modeled Parameter-Transfer Time Reduction (%)")
    ax.set_xticks(x)
    ax.set_xticklabels([f"B = {b}" for b in batch_sizes])
    ax.set_ylim(0, max(ax.get_ylim()[1], 1.0) * 1.25)
    ax.grid(True, linestyle="--", axis="y", alpha=0.5)
    ax.legend(frameon=True, loc="upper right")
    plt.tight_layout()

    fig3_path = os.path.join(output_dir, "exp05a_transfer_time_reduction.png")
    plt.savefig(fig3_path, dpi=300)
    plt.close()
    print(f"  * Generated Figure 3: {fig3_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Plot TierMoE EXP-05A figures.")
    parser.add_argument("run_dir", help="Path to EXP-05A run directory.")
    parser.add_argument("--output_dir", default="figures", help="Output directory for plots.")
    args = parser.parse_args()

    plot_exp05a(args.run_dir, args.output_dir)
