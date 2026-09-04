"""
Unit tests for CXL Memory Tiering Simulator.
Covers deduplicated traffic accounting, promotion vs demand isolation, and latency calculations.
"""

import unittest
from src.placement.base import PlacementDecision
from src.simulator.cxl_model import CXLMemoryTierSimulator


class TestCXLSimulator(unittest.TestCase):

    def setUp(self):
        self.expert_size = 256 * 1024 * 1024  # 256 MB (268,435,456 bytes)
        self.simulator = CXLMemoryTierSimulator(
            latency_penalty_ns=300.0,
            bandwidth_gbps=32.0,
            expert_size_bytes=self.expert_size
        )

    def test_case_a_multiple_tokens_same_missing_expert(self):
        """Case A: 4 tokens request the same missing expert. Expected demand traffic = 1 * expert_size."""
        dec = PlacementDecision(
            step_idx=0,
            layer_idx=0,
            fast_resident_experts={0, 1},
            cxl_resident_experts={2, 3},
            promotions=set(),
            evictions=set(),
            unique_demanded_experts={2},  # Only expert 2 requested
            unique_missing_experts={2},   # Missing from fast tier
            hits=0,
            misses=4,                     # 4 tokens requested expert 2
            solver_time_us=10.0
        )
        res = self.simulator.simulate_step(dec)
        self.assertEqual(res.demand_cxl_traffic_bytes, 1 * self.expert_size)
        self.assertEqual(res.promotion_traffic_bytes, 0)
        self.assertEqual(res.total_cxl_traffic_bytes, 1 * self.expert_size)
        self.assertAlmostEqual(res.cxl_traffic_mb, 256.0, places=1)

    def test_case_b_multiple_tokens_different_missing_experts(self):
        """Case B: 4 tokens request two different missing experts. Expected demand traffic = 2 * expert_size."""
        dec = PlacementDecision(
            step_idx=0,
            layer_idx=0,
            fast_resident_experts={0, 1},
            cxl_resident_experts={2, 3},
            promotions=set(),
            evictions=set(),
            unique_demanded_experts={2, 3},
            unique_missing_experts={2, 3},
            hits=0,
            misses=4,                     # e.g., 2 tokens for E2, 2 tokens for E3
            solver_time_us=10.0
        )
        res = self.simulator.simulate_step(dec)
        self.assertEqual(res.demand_cxl_traffic_bytes, 2 * self.expert_size)
        self.assertEqual(res.promotion_traffic_bytes, 0)
        self.assertEqual(res.total_cxl_traffic_bytes, 2 * self.expert_size)
        self.assertAlmostEqual(res.cxl_traffic_mb, 512.0, places=1)

    def test_case_c_missing_and_promoted_counted_once(self):
        """Case C: Expert is missing and promoted in the same step. Counted exactly once in promotion traffic."""
        # Expert 2 was demanded and promoted into fast_resident
        dec = PlacementDecision(
            step_idx=0,
            layer_idx=0,
            fast_resident_experts={0, 1, 2},
            cxl_resident_experts={3},
            promotions={2},
            evictions=set(),
            unique_demanded_experts={2},
            unique_missing_experts=set(), # Since E2 was promoted, it is resident for this step
            hits=4,                       # 4 tokens access newly promoted E2
            misses=0,
            solver_time_us=15.0
        )
        res = self.simulator.simulate_step(dec)
        self.assertEqual(res.demand_cxl_traffic_bytes, 0)
        self.assertEqual(res.promotion_traffic_bytes, 1 * self.expert_size)
        self.assertEqual(res.total_cxl_traffic_bytes, 1 * self.expert_size)
        self.assertEqual(res.migration_volume_bytes, 1 * self.expert_size)
        self.assertAlmostEqual(res.cxl_traffic_mb, 256.0, places=1)

    def test_case_d_expert_already_resident(self):
        """Case D: Expert already resident. Expected demand traffic = 0 and promotion traffic = 0."""
        dec = PlacementDecision(
            step_idx=0,
            layer_idx=0,
            fast_resident_experts={0, 1},
            cxl_resident_experts={2, 3},
            promotions=set(),
            evictions=set(),
            unique_demanded_experts={0, 1},
            unique_missing_experts=set(),
            hits=8,
            misses=0,
            solver_time_us=5.0
        )
        res = self.simulator.simulate_step(dec)
        self.assertEqual(res.demand_cxl_traffic_bytes, 0)
        self.assertEqual(res.promotion_traffic_bytes, 0)
        self.assertEqual(res.total_cxl_traffic_bytes, 0)
        self.assertEqual(res.migration_volume_bytes, 0)
        self.assertEqual(res.cxl_traffic_mb, 0.0)

    def test_simulate_run_aggregation(self):
        dec1 = PlacementDecision(
            step_idx=0, layer_idx=0,
            fast_resident_experts={0, 1}, cxl_resident_experts={2, 3},
            promotions={0, 1}, evictions=set(),
            unique_demanded_experts={0, 1}, unique_missing_experts=set(),
            hits=4, misses=0, solver_time_us=50.0
        )
        dec2 = PlacementDecision(
            step_idx=1, layer_idx=0,
            fast_resident_experts={0, 2}, cxl_resident_experts={1, 3},
            promotions={2}, evictions={1},
            unique_demanded_experts={0, 3}, unique_missing_experts={3},
            hits=3, misses=1, solver_time_us=60.0
        )

        summary = self.simulator.simulate_run(
            algorithm_name="Test-Algo",
            decisions=[dec1, dec2]
        )

        self.assertEqual(summary.total_steps, 2)
        self.assertEqual(summary.total_accesses, 8)
        self.assertEqual(summary.total_hits, 7)
        self.assertEqual(summary.total_misses, 1)
        self.assertEqual(summary.overall_hit_rate, 7 / 8)
        # dec1: promotions={0,1} (2*256MB), demand=0
        # dec2: promotions={2} (1*256MB), demand={3} (1*256MB)
        # total cxl bytes = 4 * 256MB = 1024 MB
        self.assertAlmostEqual(summary.total_cxl_traffic_mb, 1024.0, places=1)
        self.assertAlmostEqual(summary.promotion_traffic_mb, 768.0, places=1)
        self.assertAlmostEqual(summary.demand_cxl_traffic_mb, 256.0, places=1)


if __name__ == "__main__":
    unittest.main()
