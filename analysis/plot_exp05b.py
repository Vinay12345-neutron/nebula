"""
Publication-Quality Plotting for EXP-05B: Detailed CXLMemSim Memory-System Validation.
Generates:
Figure 1: CXLMemSim transfer time (Single-Request vs TierMoE) across batch sizes B in {8, 16, 32}.
Figure 2: CXLMemSim transfer time vs bandwidth for B=32 across BW in {16, 32, 64} GB/s.
Figure 3: Transfer-time reduction comparison: EXP-05A Analytical vs EXP-05B CXLMemSim.
"""

import json
import os
import sys
from typing import Dict, List
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def setup_style():
    plt.rcParams.update({
        "font.family": "serif",
        "font.size": 11,
        "axes.labelsize": 12,
        "axes.titlesize": 13,
        "xtick.labelsize": 10,
        "ytick.labelsize": 10,
        "legend.fontsize": 10,
        "figure.titlesize": 14,
        "grid.color": "#e0e0e0",
        "grid.linestyle": "--",
        "grid.linewidth": 0.7,
        "axes.grid": True,
        "figure.dpi": 300
    })


def plot_exp05b(run_dir: str, output_dir: str = "figures") -> List[str]:
    setup_style()
    json_path = os.path.join(run_dir, "summary_metrics.json")
    if not os.path.exists(json_path):
        raise FileNotFoundError(f"Missing summary metrics at {json_path}")

    with open(json_path, "r", encoding="utf-8") as f:
        records = json.load(f)

    df = pd.DataFrame(records)
    saved_figs = []

    # Directories for figure output (both in run_dir/figures and project figures/)
    fig_dirs = [os.path.join(run_dir, "figures"), output_dir]
    for d in fig_dirs:
        os.makedirs(d, exist_ok=True)

    # -------------------------------------------------------------------------
    # Figure 1: Core Batch Scaling (B in 8, 16, 32 at 32 GB/s, 300 ns)
    # -------------------------------------------------------------------------
    core_df = df[(df["cxl_bandwidth_gbps"] == 32.0) & (df["cxl_latency_ns"] == 300.0)]
    batch_sizes = [8, 16, 32]
    single_times = []
    tiermoe_times = []

    for b in batch_sizes:
        s_val = core_df[(core_df["batch_size"] == b) & (core_df["algo_key"] == "baseline_3_single_request")]["cxlmemsim_transfer_time_s"].values[0]
        t_val = core_df[(core_df["batch_size"] == b) & (core_df["algo_key"] == "tiermoe_batch_aware_greedy")]["cxlmemsim_transfer_time_s"].values[0]
        single_times.append(s_val)
        tiermoe_times.append(t_val)

    fig, ax = plt.subplots(figsize=(7, 4.5))
    x = np.arange(len(batch_sizes))
    width = 0.35

    rects1 = ax.bar(x - width/2, single_times, width, label="Baseline-3-Single-Request", color="#4a7bb0", edgecolor="black", linewidth=0.8)
    rects2 = ax.bar(x + width/2, tiermoe_times, width, label="TierMoE-Batch-Aware-Greedy", color="#2a9d8f", edgecolor="black", linewidth=0.8)

    ax.set_ylabel("CXLMemSim Modeled Transfer Time (s)")
    ax.set_xlabel("Batch Size ($B$)")
    ax.set_title("EXP-05B: Modeled CXL Transfer Time vs. Batch Size\n(BW = 32 GB/s, Latency = 300 ns, C = 32 experts)")
    ax.set_xticks(x)
    ax.set_xticklabels([f"B = {b}" for b in batch_sizes])
    ax.legend(frameon=True, facecolor="white", framealpha=0.9)

    for rect in rects1:
        h = rect.get_height()
        ax.annotate(f"{h:.1f}s", xy=(rect.get_x() + rect.get_width()/2, h),
                    xytext=(0, 3), textcoords="offset points", ha="center", va="bottom", fontsize=8)
    for rect in rects2:
        h = rect.get_height()
        ax.annotate(f"{h:.1f}s", xy=(rect.get_x() + rect.get_width()/2, h),
                    xytext=(0, 3), textcoords="offset points", ha="center", va="bottom", fontsize=8, fontweight="bold")

    plt.tight_layout()
    for d in fig_dirs:
        p = os.path.join(d, "exp05b_fig1_cxlmemsim_batch_scaling.png")
        plt.savefig(p)
        saved_figs.append(p)
    plt.close()

    # -------------------------------------------------------------------------
    # Figure 2: Bandwidth Sensitivity (B = 32 at BW in 16, 32, 64 GB/s)
    # -------------------------------------------------------------------------
    b32_df = df[df["batch_size"] == 32]
    bws = [16.0, 32.0, 64.0]
    single_bws = []
    tiermoe_bws = []

    for bw in bws:
        s_val = b32_df[(b32_df["cxl_bandwidth_gbps"] == bw) & (b32_df["algo_key"] == "baseline_3_single_request")]["cxlmemsim_transfer_time_s"].values[0]
        t_val = b32_df[(b32_df["cxl_bandwidth_gbps"] == bw) & (b32_df["algo_key"] == "tiermoe_batch_aware_greedy")]["cxlmemsim_transfer_time_s"].values[0]
        single_bws.append(s_val)
        tiermoe_bws.append(t_val)

    fig, ax = plt.subplots(figsize=(7, 4.5))
    x = np.arange(len(bws))

    rects1 = ax.bar(x - width/2, single_bws, width, label="Baseline-3-Single-Request", color="#e76f51", edgecolor="black", linewidth=0.8)
    rects2 = ax.bar(x + width/2, tiermoe_bws, width, label="TierMoE-Batch-Aware-Greedy", color="#264653", edgecolor="black", linewidth=0.8)

    ax.set_ylabel("CXLMemSim Modeled Transfer Time (s)")
    ax.set_xlabel("CXL Bandwidth (GB/s)")
    ax.set_title("EXP-05B: CXL Bandwidth Sensitivity under Full-System CXLMemSim\n(B = 32, Latency = 300 ns, C = 32 experts)")
    ax.set_xticks(x)
    ax.set_xticklabels([f"{int(bw)} GB/s" for bw in bws])
    ax.legend(frameon=True, facecolor="white", framealpha=0.9)

    for rect in rects1:
        h = rect.get_height()
        ax.annotate(f"{h:.1f}s", xy=(rect.get_x() + rect.get_width()/2, h),
                    xytext=(0, 3), textcoords="offset points", ha="center", va="bottom", fontsize=8)
    for rect in rects2:
        h = rect.get_height()
        ax.annotate(f"{h:.1f}s", xy=(rect.get_x() + rect.get_width()/2, h),
                    xytext=(0, 3), textcoords="offset points", ha="center", va="bottom", fontsize=8, fontweight="bold")

    plt.tight_layout()
    for d in fig_dirs:
        p = os.path.join(d, "exp05b_fig2_cxlmemsim_bandwidth_sensitivity.png")
        plt.savefig(p)
        saved_figs.append(p)
    plt.close()

    # -------------------------------------------------------------------------
    # Figure 3: Comparison of Transfer-Time Reductions (EXP-05A vs EXP-05B)
    # -------------------------------------------------------------------------
    # Reductions: B=8, B=16, B=32 (Core) + B=32(16GB/s), B=32(64GB/s)
    conditions_labels = ["B=8 (32GB/s)", "B=16 (32GB/s)", "B=32 (32GB/s)", "B=32 (16GB/s)", "B=32 (64GB/s)"]
    cxlmemsim_reds = []
    analytical_reds = []

    for b, bw in [(8, 32.0), (16, 32.0), (32, 32.0), (32, 16.0), (32, 64.0)]:
        s_cxl = df[(df["batch_size"] == b) & (df["cxl_bandwidth_gbps"] == bw) & (df["algo_key"] == "baseline_3_single_request")]["cxlmemsim_transfer_time_ms"].values[0]
        t_cxl = df[(df["batch_size"] == b) & (df["cxl_bandwidth_gbps"] == bw) & (df["algo_key"] == "tiermoe_batch_aware_greedy")]["cxlmemsim_transfer_time_ms"].values[0]
        cxl_red = ((s_cxl - t_cxl) / s_cxl) * 100.0
        cxlmemsim_reds.append(cxl_red)

        s_ana = df[(df["batch_size"] == b) & (df["cxl_bandwidth_gbps"] == bw) & (df["algo_key"] == "baseline_3_single_request")]["analytical_transfer_time_ms"].values[0]
        t_ana = df[(df["batch_size"] == b) & (df["cxl_bandwidth_gbps"] == bw) & (df["algo_key"] == "tiermoe_batch_aware_greedy")]["analytical_transfer_time_ms"].values[0]
        ana_red = ((s_ana - t_ana) / s_ana) * 100.0
        analytical_reds.append(ana_red)

    fig, ax = plt.subplots(figsize=(8.5, 4.5))
    x = np.arange(len(conditions_labels))
    width = 0.35

    rects1 = ax.bar(x - width/2, analytical_reds, width, label="EXP-05A: Analytical Model", color="#e9c46a", edgecolor="black", linewidth=0.8)
    rects2 = ax.bar(x + width/2, cxlmemsim_reds, width, label="EXP-05B: CXLMemSim Memory System", color="#2a9d8f", edgecolor="black", linewidth=0.8)

    ax.set_ylabel("TierMoE Transfer-Time Reduction vs. Single-Request (%)")
    ax.set_title("Cross-Model Validation: TierMoE Transfer-Time Reduction\nEXP-05A Analytical vs. EXP-05B CXLMemSim Detailed Simulation")
    ax.set_xticks(x)
    ax.set_xticklabels(conditions_labels, rotation=15)
    ax.legend(frameon=True, facecolor="white", framealpha=0.9)

    for rect in rects1:
        h = rect.get_height()
        ax.annotate(f"{h:.2f}%", xy=(rect.get_x() + rect.get_width()/2, h),
                    xytext=(0, 3), textcoords="offset points", ha="center", va="bottom", fontsize=8)
    for rect in rects2:
        h = rect.get_height()
        ax.annotate(f"{h:.2f}%", xy=(rect.get_x() + rect.get_width()/2, h),
                    xytext=(0, 3), textcoords="offset points", ha="center", va="bottom", fontsize=8, fontweight="bold")

    plt.tight_layout()
    for d in fig_dirs:
        p = os.path.join(d, "exp05b_fig3_cxlmemsim_vs_analytical_reduction.png")
        plt.savefig(p)
        saved_figs.append(p)
    plt.close()

    print(f"\n[+] Publication figures successfully saved to:")
    for p in saved_figs[:3]:
        print(f"    * {p}")

    return saved_figs


if __name__ == "__main__":
    if len(sys.argv) > 1:
        plot_exp05b(sys.argv[1])
    else:
        print("Usage: python3 plot_exp05b.py <run_dir>")
