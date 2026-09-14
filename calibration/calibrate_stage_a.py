#!/usr/bin/env python3
"""
EXP-05B Stage A: CXLMemSim Memory-System Calibration Harness.

Compares the existing TierMoE analytical CXL transfer model against CXLMemSim
for a single sequential read-only expert parameter block (256 MiB).

Investigates:
1. Transaction representations (from 64-byte cache lines to representative streams).
2. Convergence behavior as representative stream size scales:
   64 KB, 1 MB, 4 MB, 16 MB, 64 MB, 256 MB.
3. Sensitivity across CXL Bandwidth (16, 32, 64 GB/s) and Latency (150, 300, 600 ns).
4. Validation of whether a representative-burst scaling method is scientifically defensible.
"""

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass
from typing import Dict, List, Tuple

# Total logical expert size for Qwen3-30B-A3B
EXPERT_SIZE_BYTES = 268435456  # 256 MiB
CACHE_LINE_SIZE = 64            # 64 bytes per transaction


@dataclass
class CXLMemSimConfig:
    """Mirrors CXLMemSim CXLMemExpander & BandwidthModelConfig from cxlendpoint.h."""
    read_bw_gbps: float = 32.0
    write_bw_gbps: float = 32.0
    read_latency_ns: float = 300.0
    write_latency_ns: float = 300.0
    dram_latency_ns: float = 110.0
    knee_utilization: float = 0.80
    saturation_utilization: float = 0.98
    low_utilization_slope: float = 0.05
    max_penalty_ns: float = 5000.0
    min_window_ns: float = 100000.0  # 100 us accounting window in CXLMemSim


def calculate_mlc_bandwidth_penalty(
    cfg: CXLMemSimConfig,
    access_count: int,
    first_timestamp_ns: float,
    last_timestamp_ns: float,
    read_ratio: float = 1.0
) -> Tuple[float, float, float]:
    """
    Exact implementation of CXLMemSim calculate_mlc_bandwidth_penalty
    from ~/Vinay/CXLMemSim/src/cxlendpoint.cpp lines 52-92.
    Returns: (penalty_ns, observed_gbps, utilization)
    """
    if access_count == 0:
        return 0.0, 0.0, 0.0

    observed_window_ns = max(0.0, last_timestamp_ns - first_timestamp_ns)
    window_ns = max(observed_window_ns, cfg.min_window_ns)
    observed_gbps = (access_count * CACHE_LINE_SIZE) / window_ns
    peak_gbps = cfg.read_bw_gbps if read_ratio >= 0.95 else cfg.mixed_peak_gbps
    utilization = observed_gbps / peak_gbps if peak_gbps > 0 else 0.0

    if utilization <= 0.0:
        return 0.0, observed_gbps, utilization

    transfer_ns_per_cacheline = CACHE_LINE_SIZE / peak_gbps
    base_latency_ns = cfg.read_latency_ns * read_ratio + cfg.write_latency_ns * (1.0 - read_ratio)
    penalty_ns = transfer_ns_per_cacheline * utilization * cfg.low_utilization_slope

    if utilization > cfg.knee_utilization:
        clipped_util = min(utilization, cfg.saturation_utilization)
        knee_span = max(0.001, cfg.saturation_utilization - cfg.knee_utilization)
        knee_progress = (clipped_util - cfg.knee_utilization) / knee_span
        queue_multiplier = (clipped_util / max(0.001, 1.0 - clipped_util)) * (knee_progress ** 2)
        penalty_ns += transfer_ns_per_cacheline * queue_multiplier

    if utilization > cfg.saturation_utilization:
        penalty_ns += base_latency_ns * ((utilization - cfg.saturation_utilization) / max(0.001, 1.0 - cfg.saturation_utilization))

    dynamic_cap = max(cfg.max_penalty_ns, base_latency_ns * 10.0)
    penalty_ns = min(penalty_ns, dynamic_cap)
    return penalty_ns, observed_gbps, utilization


def calculate_pipeline_latency(
    cfg: CXLMemSimConfig,
    is_read: bool = True
) -> float:
    """
    Exact implementation of CXLMemSim calculate_pipeline_latency
    from ~/Vinay/CXLMemSim/src/cxlendpoint.cpp lines 768-794.
    """
    frontend_latency = 10.0
    forward_latency = 15.0
    mem_latency = cfg.read_latency_ns if is_read else cfg.write_latency_ns
    response_latency = 20.0
    # Protocol overhead: 1 flit (66B) for 64B line = 65 data flit bytes * 0.1 ns = 6.5 ns
    protocol_overhead = 6.5
    congestion_delay = 0.0  # single stream, no background queue congestion
    return frontend_latency + forward_latency + mem_latency + response_latency + protocol_overhead + congestion_delay


def calculate_stream_latency(
    cfg: CXLMemSimConfig,
    access_count: int,
    inter_arrival_ns: float
) -> float:
    """
    Exact implementation of CXLMemSim CXLMemExpander::calculate_latency
    from ~/Vinay/CXLMemSim/src/cxlendpoint.cpp lines 112-191.
    Models pipeline overlap benefit between sequential streaming cachelines.
    """
    if access_count == 0:
        return 0.0

    single_req_lat = calculate_pipeline_latency(cfg, is_read=True)

    # In a sequential streaming burst, successive requests arrive spaced by inter_arrival_ns
    if inter_arrival_ns < 100.0:
        overlap_ratio = 1.0 - (inter_arrival_ns / 100.0)
        overlap_benefit = single_req_lat * overlap_ratio * 0.5
        pipelined_req_lat = single_req_lat - overlap_benefit
    else:
        pipelined_req_lat = single_req_lat

    # Add DRAM component
    pipelined_req_lat += cfg.dram_latency_ns * 0.1

    # Low queue state multiplier (request_queue < MAX_QUEUE_SIZE / 4 -> 0.9x)
    pipelined_req_lat *= 0.9

    # First access incurs full non-overlapped latency; remaining (N-1) accesses enjoy pipeline overlap
    total_lat = single_req_lat + (access_count - 1) * pipelined_req_lat
    return total_lat / access_count


def run_cxlmemsim_stream_evaluation(
    stream_size_bytes: int,
    cfg: CXLMemSimConfig
) -> Dict[str, float]:
    """
    Simulates a sequential read-only streaming memory transfer of stream_size_bytes
    using CXLMemSim's exact mathematical model.
    """
    t_start = time.perf_counter()

    access_count = stream_size_bytes // CACHE_LINE_SIZE
    # Inter-arrival spacing at link line rate (64 bytes / peak_bandwidth)
    # e.g., at 32 GB/s, 64 B takes 2.0 ns
    inter_arrival_ns = (CACHE_LINE_SIZE / cfg.read_bw_gbps)

    # Bus transmission span from first to last request emission
    duration_emission_ns = (access_count - 1) * inter_arrival_ns
    first_ts = 0.0
    last_ts = duration_emission_ns

    # Bandwidth penalty
    bw_penalty_ns, observed_gbps, utilization = calculate_mlc_bandwidth_penalty(
        cfg=cfg,
        access_count=access_count,
        first_timestamp_ns=first_ts,
        last_timestamp_ns=last_ts,
        read_ratio=1.0
    )

    # Pipeline latency
    avg_req_latency_ns = calculate_stream_latency(
        cfg=cfg,
        access_count=access_count,
        inter_arrival_ns=inter_arrival_ns
    )

    # Total simulated time for this stream:
    # Transmission duration + tail pipeline completion latency + bandwidth queue penalty
    simulated_stream_time_ns = duration_emission_ns + avg_req_latency_ns + bw_penalty_ns
    simulated_stream_time_ms = simulated_stream_time_ns / 1e6

    # Effective achieved bandwidth for this stream
    effective_bw_gbps = (stream_size_bytes / 1e9) / (simulated_stream_time_ns / 1e9) if simulated_stream_time_ns > 0 else 0.0

    # Scale to full 256 MiB expert block:
    scale_factor = EXPERT_SIZE_BYTES / stream_size_bytes
    scaled_simulated_time_ms = simulated_stream_time_ms * scale_factor

    t_elapsed = time.perf_counter() - t_start

    return {
        "stream_size_bytes": stream_size_bytes,
        "stream_size_mb": stream_size_bytes / (1024 * 1024),
        "access_count": access_count,
        "inter_arrival_ns": inter_arrival_ns,
        "duration_emission_ns": duration_emission_ns,
        "observed_gbps": observed_gbps,
        "link_utilization": utilization,
        "bw_penalty_ns": bw_penalty_ns,
        "avg_req_latency_ns": avg_req_latency_ns,
        "simulated_stream_time_ms": simulated_stream_time_ms,
        "effective_bw_gbps": effective_bw_gbps,
        "scale_factor": scale_factor,
        "scaled_simulated_time_ms": scaled_simulated_time_ms,
        "runtime_seconds": t_elapsed
    }


def run_analytical_model(
    bandwidth_gbps: float,
    latency_ns: float,
    size_bytes: int = EXPERT_SIZE_BYTES
) -> Dict[str, float]:
    """
    Existing TierMoE analytical CXL model from src/simulator/cxl_model.py:
    transfer_latency_overhead_ms = (1 * latency_ns) / 1e6
    transmission_time_ms = size_bytes / (bandwidth_gbps * 1e6)
    modeled_cxl_transfer_time_ms = transfer_latency_overhead_ms + transmission_time_ms
    """
    latency_overhead_ms = latency_ns / 1e6
    transmission_time_ms = (size_bytes / (bandwidth_gbps * 1e9)) * 1e3
    total_time_ms = latency_overhead_ms + transmission_time_ms
    effective_bw_gbps = (size_bytes / 1e9) / (total_time_ms / 1e3)

    return {
        "size_bytes": size_bytes,
        "size_mb": size_bytes / (1024 * 1024),
        "bandwidth_gbps": bandwidth_gbps,
        "latency_ns": latency_ns,
        "latency_overhead_ms": latency_overhead_ms,
        "transmission_time_ms": transmission_time_ms,
        "total_time_ms": total_time_ms,
        "effective_bw_gbps": effective_bw_gbps
    }


def main():
    print("=" * 80)
    print("  PROJECT TIERMOE: EXP-05B STAGE A — CXLMemSim CALIBRATION HARNESS")
    print("  Evaluating Single 256-MiB Sequential Read-Only Expert Parameter Transfer")
    print("=" * 80 + "\n")

    bandwidths = [16.0, 32.0, 64.0]
    latencies = [150.0, 300.0, 600.0]

    stream_sizes = [
        64 * 1024,              # 64 KB  (1,024 lines)
        1 * 1024 * 1024,        # 1 MB   (16,384 lines)
        4 * 1024 * 1024,        # 4 MB   (65,536 lines)
        16 * 1024 * 1024,       # 16 MB  (262,144 lines)
        64 * 1024 * 1024,       # 64 MB  (1,048,576 lines)
        256 * 1024 * 1024,      # 256 MB (4,194,304 lines) - Full Expert Block
    ]

    # 1. Baseline Convergence Test across Stream Sizes (BW=32 GB/s, Lat=300 ns)
    print("[1. Stream Size Convergence Test @ Baseline: BW=32 GB/s, Latency=300 ns]")
    baseline_cfg = CXLMemSimConfig(read_bw_gbps=32.0, read_latency_ns=300.0)
    baseline_analytical = run_analytical_model(bandwidth_gbps=32.0, latency_ns=300.0)

    print(f"  TierMoE Analytical Baseline for 256 MiB:")
    print(f"    * Transmission Time : {baseline_analytical['transmission_time_ms']:.6f} ms")
    print(f"    * Latency Overhead  : {baseline_analytical['latency_overhead_ms']:.6f} ms")
    print(f"    * Total Transfer Time: {baseline_analytical['total_time_ms']:.6f} ms")
    print(f"    * Effective Bandwidth: {baseline_analytical['effective_bw_gbps']:.4f} GB/s\n")

    full_256mb_res = run_cxlmemsim_stream_evaluation(256 * 1024 * 1024, baseline_cfg)
    full_cxlmemsim_ms = full_256mb_res["scaled_simulated_time_ms"]

    stream_results = []
    print(f"{'Stream Size':>11} | {'Tx Count':>10} | {'Link Util':>9} | {'Eff BW':>9} | {'Scaled 256MB (ms)':>17} | {'Delta vs Full':>13} | {'Delta vs Ana':>12} | {'Runtime':>8}")
    print("-" * 110)

    for sz in stream_sizes:
        res = run_cxlmemsim_stream_evaluation(sz, baseline_cfg)
        delta_ana_pct = ((res["scaled_simulated_time_ms"] - baseline_analytical["total_time_ms"]) / baseline_analytical["total_time_ms"]) * 100.0
        delta_full_pct = ((res["scaled_simulated_time_ms"] - full_cxlmemsim_ms) / full_cxlmemsim_ms) * 100.0
        stream_results.append({
            **res,
            "analytical_time_ms": baseline_analytical["total_time_ms"],
            "delta_analytical_pct": delta_ana_pct,
            "delta_full_256mb_pct": delta_full_pct
        })
        sz_str = f"{res['stream_size_mb']:.1f} MB" if res['stream_size_mb'] >= 1.0 else f"{sz//1024} KB"
        eff_bw_str = f"{res['effective_bw_gbps']:.2f} GB/s"
        util_str = f"{res['link_utilization']*100:.1f}%"
        print(f"{sz_str:>11} | {res['access_count']:>10,d} | {util_str:>9} | {eff_bw_str:>9} | {res['scaled_simulated_time_ms']:>17.6f} | {delta_full_pct:>+12.4f}% | {delta_ana_pct:>+11.4f}% | {res['runtime_seconds']:>7.5f}s")

    print("\n" + "=" * 80)
    print("[2. Sensitivity Matrix Across Bandwidths (16, 32, 64 GB/s) & Latencies (150, 300, 600 ns)]")
    print("=" * 80)

    matrix_results = []
    print(f"{'BW (GB/s)':>10} | {'Lat (ns)':>9} | {'Analytical (ms)':>16} | {'Full 256MB (ms)':>16} | {'64MB-Scaled (ms)':>17} | {'16MB-Scaled (ms)':>17} | {'Delta (Full vs Ana)':>20}")
    print("-" * 115)

    for bw in bandwidths:
        for lat in latencies:
            cfg = CXLMemSimConfig(read_bw_gbps=bw, read_latency_ns=lat)
            ana = run_analytical_model(bandwidth_gbps=bw, latency_ns=lat)

            res_full = run_cxlmemsim_stream_evaluation(256 * 1024 * 1024, cfg)
            res_64mb = run_cxlmemsim_stream_evaluation(64 * 1024 * 1024, cfg)
            res_16mb = run_cxlmemsim_stream_evaluation(16 * 1024 * 1024, cfg)

            delta_full_pct = ((res_full["scaled_simulated_time_ms"] - ana["total_time_ms"]) / ana["total_time_ms"]) * 100.0

            matrix_results.append({
                "bandwidth_gbps": bw,
                "latency_ns": lat,
                "analytical_ms": ana["total_time_ms"],
                "cxlmemsim_full_256mb_ms": res_full["scaled_simulated_time_ms"],
                "cxlmemsim_64mb_scaled_ms": res_64mb["scaled_simulated_time_ms"],
                "cxlmemsim_16mb_scaled_ms": res_16mb["scaled_simulated_time_ms"],
                "delta_full_pct": delta_full_pct,
                "utilization": res_full["link_utilization"],
                "bw_penalty_ns": res_full["bw_penalty_ns"]
            })

            print(f"{bw:>10.1f} | {lat:>9.1f} | {ana['total_time_ms']:>16.6f} | {res_full['scaled_simulated_time_ms']:>16.6f} | {res_64mb['scaled_simulated_time_ms']:>17.6f} | {res_16mb['scaled_simulated_time_ms']:>17.6f} | {delta_full_pct:>+19.2f}%")

    # Output results to calibration summary json
    output_dir = "calibration/results"
    os.makedirs(output_dir, exist_ok=True)
    summary_path = os.path.join(output_dir, "calibration_stage_a_summary.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump({
            "convergence_sweep": stream_results,
            "sensitivity_matrix": matrix_results
        }, f, indent=2)

    print(f"\n[+] Calibration Results saved to: {summary_path}")
    print("=" * 80)
    print("  STAGE A CALIBRATION RUN COMPLETE.")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
