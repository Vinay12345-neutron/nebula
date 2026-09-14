#!/usr/bin/env python3
"""
Unit and Verification Tests for EXP-05B Stage A: CXLMemSim Calibration.
Verifies the exact numerical implementation of CXLMemSim equations against
known hand-calculated points, monotonicity properties, link saturation thresholds,
and asymptotic overhead convergence.
"""

import sys
import os
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from calibration.calibrate_stage_a import (
    CXLMemSimConfig,
    calculate_mlc_bandwidth_penalty,
    calculate_pipeline_latency,
    calculate_stream_latency,
    run_cxlmemsim_stream_evaluation,
    run_analytical_model,
    EXPERT_SIZE_BYTES,
    CACHE_LINE_SIZE
)


class TestStageACalibration(unittest.TestCase):
    """Test suite for CXLMemSim Stage A calibration harness."""

    def test_analytical_baseline_32gbps_300ns(self):
        """Verify analytical baseline for 256 MiB at 32 GB/s and 300 ns."""
        res = run_analytical_model(bandwidth_gbps=32.0, latency_ns=300.0)
        expected_tx_ms = (268435456 / (32.0 * 1e9)) * 1e3  # 8.388608 ms
        expected_lat_ms = 300.0 / 1e6                       # 0.000300 ms
        self.assertAlmostEqual(res["transmission_time_ms"], expected_tx_ms, places=6)
        self.assertAlmostEqual(res["latency_overhead_ms"], expected_lat_ms, places=6)
        self.assertAlmostEqual(res["total_time_ms"], expected_tx_ms + expected_lat_ms, places=6)

    def test_bandwidth_monotonicity(self):
        """Verify simulated time decreases monotonically as bandwidth increases."""
        cfg_16 = CXLMemSimConfig(read_bw_gbps=16.0, read_latency_ns=300.0)
        cfg_32 = CXLMemSimConfig(read_bw_gbps=32.0, read_latency_ns=300.0)
        cfg_64 = CXLMemSimConfig(read_bw_gbps=64.0, read_latency_ns=300.0)

        sz = 4 * 1024 * 1024
        t_16 = run_cxlmemsim_stream_evaluation(sz, cfg_16)["scaled_simulated_time_ms"]
        t_32 = run_cxlmemsim_stream_evaluation(sz, cfg_32)["scaled_simulated_time_ms"]
        t_64 = run_cxlmemsim_stream_evaluation(sz, cfg_64)["scaled_simulated_time_ms"]

        self.assertGreater(t_16, t_32)
        self.assertGreater(t_32, t_64)

    def test_latency_monotonicity(self):
        """Verify simulated time increases monotonically as link latency increases."""
        cfg_150 = CXLMemSimConfig(read_bw_gbps=32.0, read_latency_ns=150.0)
        cfg_300 = CXLMemSimConfig(read_bw_gbps=32.0, read_latency_ns=300.0)
        cfg_600 = CXLMemSimConfig(read_bw_gbps=32.0, read_latency_ns=600.0)

        sz = 4 * 1024 * 1024
        t_150 = run_cxlmemsim_stream_evaluation(sz, cfg_150)["scaled_simulated_time_ms"]
        t_300 = run_cxlmemsim_stream_evaluation(sz, cfg_300)["scaled_simulated_time_ms"]
        t_600 = run_cxlmemsim_stream_evaluation(sz, cfg_600)["scaled_simulated_time_ms"]

        self.assertLess(t_150, t_300)
        self.assertLess(t_300, t_600)

    def test_link_utilization_saturation(self):
        """
        Criterion 1: Link-Utilization Saturation.
        Verify that stream sizes >= 4MB exceed CXLMemSim's 100 us accounting window
        and achieve steady-state link saturation (>= 99.0%).
        """
        cfg = CXLMemSimConfig(read_bw_gbps=32.0, read_latency_ns=300.0)
        res_4mb = run_cxlmemsim_stream_evaluation(4 * 1024 * 1024, cfg)
        res_16mb = run_cxlmemsim_stream_evaluation(16 * 1024 * 1024, cfg)
        res_64mb = run_cxlmemsim_stream_evaluation(64 * 1024 * 1024, cfg)
        res_256mb = run_cxlmemsim_stream_evaluation(256 * 1024 * 1024, cfg)

        self.assertGreaterEqual(res_4mb["link_utilization"], 0.99)
        self.assertGreaterEqual(res_16mb["link_utilization"], 0.99)
        self.assertGreaterEqual(res_64mb["link_utilization"], 0.99)
        self.assertGreaterEqual(res_256mb["link_utilization"], 0.99)

    def test_monotonic_overhead_convergence(self):
        """
        Criterion 2: Monotonic Asymptotic Overhead Convergence.
        Verify that the scaled transfer time overhead decreases strictly monotonically
        as representative stream size increases, proving asymptotic convergence.
        """
        cfg = CXLMemSimConfig(read_bw_gbps=32.0, read_latency_ns=300.0)
        t_ana = run_analytical_model(bandwidth_gbps=32.0, latency_ns=300.0)["total_time_ms"]

        sizes = [64 * 1024, 1024 * 1024, 4 * 1024 * 1024, 16 * 1024 * 1024, 64 * 1024 * 1024, 256 * 1024 * 1024]
        errors = []
        for sz in sizes:
            res = run_cxlmemsim_stream_evaluation(sz, cfg)
            err = (res["scaled_simulated_time_ms"] - t_ana) / t_ana * 100.0
            errors.append(err)

        # Verify strict monotonic decrease of scaling overhead
        for i in range(len(errors) - 1):
            self.assertGreater(errors[i], errors[i + 1],
                               f"Overhead at size {sizes[i]} ({errors[i]:.4f}%) must exceed size {sizes[i+1]} ({errors[i+1]:.4f}%)")

    def test_full_256mb_cxlmemsim_agreement(self):
        """
        Criterion 3: Full 256-MiB Direct Agreement.
        Verify that direct CXLMemSim evaluation of the full 256-MiB expert block
        (4,194,304 transactions) matches TierMoE's analytical baseline within 0.01%.
        """
        cfg = CXLMemSimConfig(read_bw_gbps=32.0, read_latency_ns=300.0)
        t_ana = run_analytical_model(bandwidth_gbps=32.0, latency_ns=300.0)["total_time_ms"]
        res_256mb = run_cxlmemsim_stream_evaluation(256 * 1024 * 1024, cfg)

        diff_pct = abs(res_256mb["scaled_simulated_time_ms"] - t_ana) / t_ana * 100.0
        # Agreement must be within 0.01% (measured delta is +0.00318%)
        self.assertLess(diff_pct, 0.01)


if __name__ == "__main__":
    unittest.main()
