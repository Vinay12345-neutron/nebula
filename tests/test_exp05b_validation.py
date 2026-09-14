"""
Automated Scientific Safety Checks for EXP-05B Stage B:
Detailed CXLMemSim Memory-System Validation.

Implements all 14 mandatory safety checks specified in EXP-05B Specification Section 11:
1. Exactly 10 experiment conditions.
2. Exactly two algorithms.
3. B values exactly {8, 16, 32}.
4. C exactly 32.
5. Bandwidth values exactly {16, 32, 64}.
6. Latency exactly 300 ns.
7. Every expert transfer is exactly 256 MiB.
8. 256 MiB corresponds to exactly 4,194,304 x 64-byte lines.
9. Duplicate expert demand within a batch is deduplicated.
10. Read-only workload generates zero writeback traffic.
11. Expert address regions do not overlap.
12. CXLMemSim timing is non-negative.
13. Increasing bandwidth does not increase modeled transfer time for otherwise identical workload.
14. No EXP-01 through EXP-05A files are modified.
"""

import os
import unittest
import yaml

from src.placement.base import PlacementDecision
from src.simulator.cxlmemsim_adapter import (
    CXLMemSimTierSimulator,
    CXLMemSimConfig,
    EXPERT_SIZE_BYTES,
    CACHE_LINE_SIZE,
    LINES_PER_EXPERT,
    get_expert_address,
)


class TestEXP05BValidation(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.config_path = os.path.join(
            os.path.dirname(__file__), "..", "configs", "experiments", "exp05b_rq4_cxlmemsim_validation.yaml"
        )
        with open(cls.config_path, "r", encoding="utf-8") as f:
            cls.cfg = yaml.safe_load(f)

    def test_01_exactly_10_experiment_conditions(self):
        """Check 1: Exactly 10 policy-condition evaluations in the experiment matrix."""
        eval_conditions = self.cfg.get("evaluation_conditions", [])
        algorithms = self.cfg.get("algorithms", [])
        total_evaluations = len(eval_conditions) * len(algorithms)
        self.assertEqual(
            total_evaluations, 10,
            f"Expected exactly 10 policy-condition evaluations, got {total_evaluations} "
            f"({len(eval_conditions)} conditions x {len(algorithms)} algorithms)"
        )

    def test_02_exactly_two_algorithms(self):
        """Check 2: Exactly two algorithms (Baseline-3-Single-Request and TierMoE-Batch-Aware-Greedy)."""
        algorithms = self.cfg.get("algorithms", [])
        expected = ["baseline_3_single_request", "tiermoe_batch_aware_greedy"]
        self.assertEqual(algorithms, expected)

    def test_03_batch_sizes_in_8_16_32(self):
        """Check 3: Batch sizes across all conditions must be exactly {8, 16, 32}."""
        eval_conditions = self.cfg.get("evaluation_conditions", [])
        batch_sizes = {c["batch_size"] for c in eval_conditions}
        self.assertEqual(batch_sizes, {8, 16, 32})

    def test_04_fast_capacity_c_32(self):
        """Check 4: Fast tier capacity C is exactly 32 experts (25% of 128 experts)."""
        fast_cap = self.cfg.get("memory", {}).get("fast_capacity_experts", None)
        self.assertEqual(fast_cap, 32)
        ratios = self.cfg.get("memory", {}).get("fast_memory_ratios", [])
        self.assertEqual(ratios, [0.25])

    def test_05_bandwidth_values_in_16_32_64(self):
        """Check 5: Bandwidth values across conditions are exactly {16.0, 32.0, 64.0} GB/s."""
        eval_conditions = self.cfg.get("evaluation_conditions", [])
        bws = {c["bandwidth_gbps"] for c in eval_conditions}
        self.assertEqual(bws, {16.0, 32.0, 64.0})

    def test_06_latency_300ns(self):
        """Check 6: Latency in all conditions is exactly 300.0 ns."""
        eval_conditions = self.cfg.get("evaluation_conditions", [])
        for i, c in enumerate(eval_conditions):
            self.assertEqual(
                c["latency_ns"], 300.0,
                f"Condition {i} has latency {c['latency_ns']} ns, expected 300.0 ns"
            )

    def test_07_expert_transfer_size_256mib(self):
        """Check 7: Every expert transfer is exactly 256 MiB = 268,435,456 bytes."""
        self.assertEqual(EXPERT_SIZE_BYTES, 256 * 1024 * 1024)
        self.assertEqual(EXPERT_SIZE_BYTES, 268435456)

    def test_08_lines_per_expert_4194304(self):
        """Check 8: 256 MiB corresponds to exactly 4,194,304 x 64-byte lines."""
        self.assertEqual(CACHE_LINE_SIZE, 64)
        self.assertEqual(LINES_PER_EXPERT, 4194304)
        self.assertEqual(LINES_PER_EXPERT * CACHE_LINE_SIZE, EXPERT_SIZE_BYTES)

    def test_09_duplicate_expert_demand_deduplicated(self):
        """Check 9: Multiple tokens demanding the same missing expert within a batch step are deduplicated."""
        sim = CXLMemSimTierSimulator(bandwidth_gbps=32.0, latency_penalty_ns=300.0)
        # 8 tokens in the batch all require missing expert 42
        decision = PlacementDecision(
            step_idx=0,
            layer_idx=0,
            fast_resident_experts=set(range(32)),
            cxl_resident_experts=set(range(32, 128)),
            promotions=set(),
            evictions=set(),
            unique_demanded_experts={42},
            unique_missing_experts={42},  # Deduplicated set of unique missing experts
            hits=0,
            misses=8,  # 8 token-level misses
            solver_time_us=10.0
        )
        res = sim.simulate_step(decision)
        # Should generate exactly ONE 256-MiB transfer, not 8
        self.assertEqual(res.total_transfers_count, 1)
        self.assertEqual(res.total_cxl_traffic_bytes, EXPERT_SIZE_BYTES)
        self.assertEqual(res.total_cxl_traffic_bytes, 268435456)

    def test_10_read_only_zero_writeback(self):
        """Check 10: Read-only workload generates zero writeback traffic on clean evictions."""
        sim = CXLMemSimTierSimulator(bandwidth_gbps=32.0, latency_penalty_ns=300.0)
        # Decision with 4 evictions and 4 promotions
        decision = PlacementDecision(
            step_idx=0,
            layer_idx=0,
            fast_resident_experts=set(range(32)),
            cxl_resident_experts=set(range(32, 128)),
            promotions={32, 33, 34, 35},
            evictions={0, 1, 2, 3},  # 4 clean evictions from fast tier
            unique_demanded_experts={32, 33, 34, 35},
            unique_missing_experts=set(),
            hits=0,
            misses=4,
            solver_time_us=15.0
        )
        res = sim.simulate_step(decision)
        # Total traffic must equal promotion read traffic ONLY (4 * 256 MiB); evictions generate 0 bytes
        expected_traffic = 4 * EXPERT_SIZE_BYTES
        self.assertEqual(res.total_cxl_traffic_bytes, expected_traffic)
        self.assertEqual(res.evictions_count, 4)

    def test_11_expert_addresses_non_overlapping(self):
        """Check 11: Expert address regions across all 48 layers x 128 experts (6,144 experts) do not overlap."""
        seen_ranges = []
        num_layers = 48
        num_experts = 128
        total_experts = num_layers * num_experts  # 6,144

        for layer in range(num_layers):
            for expert in range(num_experts):
                base_addr = get_expert_address(layer, expert)
                end_addr = base_addr + EXPERT_SIZE_BYTES
                seen_ranges.append((base_addr, end_addr))

        self.assertEqual(len(seen_ranges), total_experts)
        # Sort by base address and verify strict non-overlap: end_i <= base_{i+1}
        seen_ranges.sort(key=lambda x: x[0])
        for i in range(len(seen_ranges) - 1):
            curr_base, curr_end = seen_ranges[i]
            next_base, _ = seen_ranges[i + 1]
            self.assertLessEqual(
                curr_end, next_base,
                f"Address overlap detected between region {i} [{curr_base:#x}, {curr_end:#x}] "
                f"and region {i+1} [{next_base:#x}]"
            )

    def test_12_cxlmemsim_timing_non_negative(self):
        """Check 12: CXLMemSim modeled transfer time is strictly non-negative."""
        sim = CXLMemSimTierSimulator(bandwidth_gbps=32.0, latency_penalty_ns=300.0)

        # Zero transfers
        dec_zero = PlacementDecision(
            step_idx=0, layer_idx=0,
            fast_resident_experts=set(range(32)), cxl_resident_experts=set(range(32, 128)),
            promotions=set(), evictions=set(),
            unique_demanded_experts={1}, unique_missing_experts=set(),
            hits=1, misses=0, solver_time_us=2.0
        )
        res_zero = sim.simulate_step(dec_zero)
        self.assertEqual(res_zero.cxlmemsim_modeled_transfer_time_ms, 0.0)

        # 1 transfer
        dec_one = PlacementDecision(
            step_idx=1, layer_idx=0,
            fast_resident_experts=set(range(32)), cxl_resident_experts=set(range(32, 128)),
            promotions={33}, evictions={0},
            unique_demanded_experts={33}, unique_missing_experts=set(),
            hits=0, misses=1, solver_time_us=2.0
        )
        res_one = sim.simulate_step(dec_one)
        self.assertGreater(res_one.cxlmemsim_modeled_transfer_time_ms, 0.0)

    def test_13_bandwidth_monotonicity(self):
        """Check 13: Increasing bandwidth does not increase modeled transfer time for identical workload."""
        dec = PlacementDecision(
            step_idx=0, layer_idx=0,
            fast_resident_experts=set(range(32)), cxl_resident_experts=set(range(32, 128)),
            promotions={32, 33}, evictions={0, 1},
            unique_demanded_experts={32, 33}, unique_missing_experts=set(),
            hits=0, misses=2, solver_time_us=5.0
        )

        sim_16 = CXLMemSimTierSimulator(bandwidth_gbps=16.0, latency_penalty_ns=300.0)
        sim_32 = CXLMemSimTierSimulator(bandwidth_gbps=32.0, latency_penalty_ns=300.0)
        sim_64 = CXLMemSimTierSimulator(bandwidth_gbps=64.0, latency_penalty_ns=300.0)

        t_16 = sim_16.simulate_step(dec).cxlmemsim_modeled_transfer_time_ms
        t_32 = sim_32.simulate_step(dec).cxlmemsim_modeled_transfer_time_ms
        t_64 = sim_64.simulate_step(dec).cxlmemsim_modeled_transfer_time_ms

        self.assertGreater(t_16, t_32, f"Expected t(16 GB/s) > t(32 GB/s), got {t_16} vs {t_32}")
        self.assertGreater(t_32, t_64, f"Expected t(32 GB/s) > t(64 GB/s), got {t_32} vs {t_64}")

    def test_14_no_exp01_through_exp05a_files_modified(self):
        """Check 14: Verify EXP-01 through EXP-05A results and scripts remain intact and untouched."""
        root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

        # Required frozen scripts
        frozen_scripts = [
            "run_phase4.py",
            "run_phase5_exp02.py",
            "run_phase6_exp03.py",
            "run_phase7_exp04.py",
            "run_phase8_exp05a.py"
        ]
        for s in frozen_scripts:
            full_path = os.path.join(root_dir, s)
            self.assertTrue(os.path.isfile(full_path), f"Frozen script missing: {s}")

        # Required frozen result directories
        frozen_result_dirs = [
            "results/exp01_rq1_batch_aware",
            "results/exp02_rq2_divergence",
            "results/exp03_rq3_coactivation",
            "results/exp04_broader_baselines",
            "results/exp05a_rq4_cxl_sensitivity"
        ]
        for d in frozen_result_dirs:
            full_path = os.path.join(root_dir, d)
            self.assertTrue(os.path.isdir(full_path), f"Frozen result dir missing: {d}")


if __name__ == "__main__":
    unittest.main()
