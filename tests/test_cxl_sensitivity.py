"""
Unit Tests for Phase 8: EXP-05A CXL Bandwidth & Latency Sensitivity Modeling.
Verifies:
1. Baseline 32 GB/s + 300 ns parameter transfer cost accuracy.
2. Monotonicity of transfer time with CXL bandwidth (higher bandwidth strictly decreases transfer time).
3. Monotonicity of transfer time with CXL latency (higher latency strictly increases transfer time).
4. Strict causal invariance: CXL hardware bandwidth and latency parameters do not alter placement decisions,
   hit counts, miss counts, or traffic byte volume.
5. Deduplication semantics: multiple tokens requesting the same missing expert incur a single 256MB bulk transfer.
"""

import unittest
from src.placement.base import PlacementDecision
from src.simulator.cxl_model import CXLMemoryTierSimulator


class TestCXLSensitivity(unittest.TestCase):

    def setUp(self):
        self.expert_size = 256 * 1024 * 1024  # 256 MB (268,435,456 bytes)

    def test_baseline_32gbps_300ns_transfer_time(self):
        """
        Verify transfer time calculation for a single 256MB expert transfer at baseline 32 GB/s and 300 ns.
        Expected:
        - Latency overhead: 300 ns = 0.0003 ms
        - Transmission time: 268,435,456 bytes / (32 * 10^6 bytes/ms) = 8.388608 ms
        - Total modeled transfer time = 8.388908 ms
        """
        sim = CXLMemoryTierSimulator(
            latency_penalty_ns=300.0,
            bandwidth_gbps=32.0,
            expert_size_bytes=self.expert_size
        )
        dec = PlacementDecision(
            step_idx=0,
            layer_idx=0,
            fast_resident_experts={0, 1},
            cxl_resident_experts={2},
            promotions={1},               # 1 promotion (256 MB)
            evictions=set(),
            unique_demanded_experts={1},
            unique_missing_experts=set(),
            hits=1,
            misses=0,
            solver_time_us=5.0
        )
        res = sim.simulate_step(dec)
        expected_transmission_ms = self.expert_size / (32.0 * 1e6)
        expected_latency_ms = 300.0 / 1e6
        expected_total_ms = expected_transmission_ms + expected_latency_ms

        self.assertAlmostEqual(res.modeled_cxl_transfer_time_ms, expected_total_ms, places=5)
        self.assertEqual(res.total_cxl_traffic_bytes, self.expert_size)

    def test_bandwidth_monotonicity(self):
        """
        Verify that modeled transfer time decreases monotonically as CXL bandwidth increases
        (16 GB/s -> 32 GB/s -> 64 GB/s) while total traffic bytes remain identical.
        """
        dec = PlacementDecision(
            step_idx=0,
            layer_idx=0,
            fast_resident_experts={0},
            cxl_resident_experts={1, 2},
            promotions={0},
            evictions=set(),
            unique_demanded_experts={0, 1},
            unique_missing_experts={1},   # 1 missing, 1 promotion = 2 transfers (512 MB)
            hits=1,
            misses=1,
            solver_time_us=10.0
        )

        sim_16 = CXLMemoryTierSimulator(latency_penalty_ns=300.0, bandwidth_gbps=16.0, expert_size_bytes=self.expert_size)
        sim_32 = CXLMemoryTierSimulator(latency_penalty_ns=300.0, bandwidth_gbps=32.0, expert_size_bytes=self.expert_size)
        sim_64 = CXLMemoryTierSimulator(latency_penalty_ns=300.0, bandwidth_gbps=64.0, expert_size_bytes=self.expert_size)

        res_16 = sim_16.simulate_step(dec)
        res_32 = sim_32.simulate_step(dec)
        res_64 = sim_64.simulate_step(dec)

        # Traffic bytes must be identical
        self.assertEqual(res_16.total_cxl_traffic_bytes, res_32.total_cxl_traffic_bytes)
        self.assertEqual(res_32.total_cxl_traffic_bytes, res_64.total_cxl_traffic_bytes)
        self.assertEqual(res_16.total_cxl_traffic_bytes, 2 * self.expert_size)

        # Transfer time must strictly decrease as bandwidth increases
        self.assertGreater(res_16.modeled_cxl_transfer_time_ms, res_32.modeled_cxl_transfer_time_ms)
        self.assertGreater(res_32.modeled_cxl_transfer_time_ms, res_64.modeled_cxl_transfer_time_ms)

        # Approximate 2x speedup per doubling of bandwidth
        ratio_16_to_32 = res_16.modeled_cxl_transfer_time_ms / res_32.modeled_cxl_transfer_time_ms
        ratio_32_to_64 = res_32.modeled_cxl_transfer_time_ms / res_64.modeled_cxl_transfer_time_ms
        self.assertAlmostEqual(ratio_16_to_32, 2.0, delta=0.01)
        self.assertAlmostEqual(ratio_32_to_64, 2.0, delta=0.01)

    def test_latency_monotonicity(self):
        """
        Verify that modeled transfer time increases monotonically as CXL latency overhead increases
        (150 ns -> 300 ns -> 600 ns) while total traffic bytes remain identical.
        """
        dec = PlacementDecision(
            step_idx=0,
            layer_idx=0,
            fast_resident_experts={0},
            cxl_resident_experts={1},
            promotions=set(),
            evictions=set(),
            unique_demanded_experts={1},
            unique_missing_experts={1},   # 1 missing expert streamed on demand
            hits=0,
            misses=1,
            solver_time_us=8.0
        )

        sim_150 = CXLMemoryTierSimulator(latency_penalty_ns=150.0, bandwidth_gbps=32.0, expert_size_bytes=self.expert_size)
        sim_300 = CXLMemoryTierSimulator(latency_penalty_ns=300.0, bandwidth_gbps=32.0, expert_size_bytes=self.expert_size)
        sim_600 = CXLMemoryTierSimulator(latency_penalty_ns=600.0, bandwidth_gbps=32.0, expert_size_bytes=self.expert_size)

        res_150 = sim_150.simulate_step(dec)
        res_300 = sim_300.simulate_step(dec)
        res_600 = sim_600.simulate_step(dec)

        # Traffic bytes must be identical
        self.assertEqual(res_150.total_cxl_traffic_bytes, res_300.total_cxl_traffic_bytes)
        self.assertEqual(res_300.total_cxl_traffic_bytes, res_600.total_cxl_traffic_bytes)

        # Transfer time must strictly increase as latency increases
        self.assertLess(res_150.modeled_cxl_transfer_time_ms, res_300.modeled_cxl_transfer_time_ms)
        self.assertLess(res_300.modeled_cxl_transfer_time_ms, res_600.modeled_cxl_transfer_time_ms)

        # Latency differences must precisely match the delta in nanoseconds
        delta_150_300_ms = res_300.modeled_cxl_transfer_time_ms - res_150.modeled_cxl_transfer_time_ms
        delta_300_600_ms = res_600.modeled_cxl_transfer_time_ms - res_300.modeled_cxl_transfer_time_ms
        self.assertAlmostEqual(delta_150_300_ms, 150.0 / 1e6, places=8)
        self.assertAlmostEqual(delta_300_600_ms, 300.0 / 1e6, places=8)

    def test_bulk_transfer_deduplication(self):
        """
        Verify that 8 tokens in the same batch requesting the same missing expert
        generate exactly 1 bulk parameter transfer, not 8 separate transfers.
        """
        dec = PlacementDecision(
            step_idx=0,
            layer_idx=0,
            fast_resident_experts={0},
            cxl_resident_experts={1},
            promotions=set(),
            evictions=set(),
            unique_demanded_experts={1},
            unique_missing_experts={1},   # 1 unique missing expert
            hits=0,
            misses=8,                     # 8 tokens requesting that missing expert
            solver_time_us=5.0
        )
        sim = CXLMemoryTierSimulator(latency_penalty_ns=300.0, bandwidth_gbps=32.0, expert_size_bytes=self.expert_size)
        res = sim.simulate_step(dec)

        # 1 transfer of 256MB
        self.assertEqual(res.demand_cxl_traffic_bytes, self.expert_size)
        self.assertEqual(res.total_cxl_traffic_bytes, self.expert_size)

        expected_time_ms = (self.expert_size / (32.0 * 1e6)) + (300.0 / 1e6)
        self.assertAlmostEqual(res.modeled_cxl_transfer_time_ms, expected_time_ms, places=5)


if __name__ == "__main__":
    unittest.main()
