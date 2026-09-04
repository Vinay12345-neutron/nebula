"""
Unit tests for placement solvers: Baselines 0-3, Batch-Aware Greedy, and Co-Activation.
Includes tests for EMA coactivation decay and synergy-driven placement ranking.
"""

import unittest
from src.placement.baselines import (
    HBMOnlySolver,
    NaiveOverflowSolver,
    StaticLFUSolver,
    SingleRequestSolver,
    PredictiveActivationAwareSolver,
    CXLLRUTieringSolver,
)
from src.placement.batch_aware import (
    BatchAwareGreedySolver,
    BatchAwareCoActivationSolver,
)
from src.workload.trace_schema import BatchRoutingEvent, TokenRoutingEvent


class TestPlacementSolvers(unittest.TestCase):

    def setUp(self):
        self.num_experts = 16
        # Construct controlled synthetic batch event
        # Request A demands: [1, 2, 5, 8]
        # Request B demands: [5, 8, 10, 12]
        # Aggregate demand: E5: 2, E8: 2, E1: 1, E2: 1, E10: 1, E12: 1 (Total: 8)
        events = [
            TokenRoutingEvent("req_A", step_idx=0, layer_idx=0, token_idx=0, expert_indices=[1, 2, 5, 8]),
            TokenRoutingEvent("req_B", step_idx=0, layer_idx=0, token_idx=0, expert_indices=[5, 8, 10, 12]),
        ]
        self.batch_event = BatchRoutingEvent.from_events(
            batch_id="test_batch",
            step_idx=0,
            layer_idx=0,
            events=events
        )

    def test_hbm_only_solver(self):
        solver = HBMOnlySolver(num_experts=self.num_experts)
        dec = solver.solve(self.batch_event, fast_capacity=self.num_experts)
        self.assertEqual(dec.hits, 8)
        self.assertEqual(dec.misses, 0)
        self.assertEqual(dec.hit_rate, 1.0)
        self.assertEqual(len(dec.fast_resident_experts), self.num_experts)
        self.assertEqual(len(dec.unique_missing_experts), 0)

    def test_naive_overflow_solver(self):
        solver = NaiveOverflowSolver(num_experts=self.num_experts)
        dec = solver.solve(self.batch_event, fast_capacity=4)
        self.assertEqual(len(dec.fast_resident_experts), 4)
        self.assertEqual(dec.fast_resident_experts, {1, 2, 5, 8})
        self.assertEqual(dec.hits, 6)
        self.assertEqual(dec.misses, 2)
        self.assertEqual(dec.unique_missing_experts, {10, 12})

    def test_static_lfu_solver(self):
        solver = StaticLFUSolver(num_experts=self.num_experts)
        dec = solver.solve(self.batch_event, fast_capacity=2)
        self.assertEqual(len(dec.fast_resident_experts), 2)
        self.assertEqual(dec.fast_resident_experts, {5, 8})
        self.assertEqual(dec.hits, 4)
        self.assertEqual(dec.misses, 4)
        self.assertEqual(dec.unique_missing_experts, {1, 2, 10, 12})

    def test_single_request_solver(self):
        solver = SingleRequestSolver(num_experts=self.num_experts)
        dec = solver.solve(self.batch_event, fast_capacity=3)
        self.assertEqual(len(dec.fast_resident_experts), 3)
        self.assertEqual(dec.fast_resident_experts, {1, 2, 5})
        self.assertEqual(dec.hits, 4)
        self.assertEqual(dec.misses, 4)
        self.assertEqual(dec.unique_missing_experts, {8, 10, 12})

    def test_batch_aware_greedy_solver(self):
        solver = BatchAwareGreedySolver(num_experts=self.num_experts, migration_penalty_weight=0.0)
        dec = solver.solve(self.batch_event, fast_capacity=2)
        self.assertEqual(len(dec.fast_resident_experts), 2)
        self.assertEqual(dec.fast_resident_experts, {5, 8})
        self.assertEqual(dec.hits, 4)
        self.assertEqual(dec.misses, 4)
        self.assertEqual(dec.unique_missing_experts, {1, 2, 10, 12})

    def test_coactivation_recent_boost(self):
        """Test 1: Recent coactivation increases pairwise score in the matrix."""
        solver = BatchAwareCoActivationSolver(num_experts=16, decay_rate=0.9)
        # Feed event where E3 and E7 co-activate
        req_map = {"req1": [3, 7]}
        solver.update_coactivation_ema(req_map)
        score_3_7 = solver._coactivation_matrix[3, 7]
        self.assertGreater(score_3_7, 0.0)
        self.assertAlmostEqual(score_3_7, 0.1, places=3)  # (1 - 0.9) * 1.0 = 0.1

    def test_coactivation_decay(self):
        """Test 2: Old coactivation decays over subsequent steps when not reinforced."""
        solver = BatchAwareCoActivationSolver(num_experts=16, decay_rate=0.8)
        # Step 1: E3 and E7 co-activate
        solver.update_coactivation_ema({"req1": [3, 7]})
        initial_score = solver._coactivation_matrix[3, 7]

        # Step 2: Unrelated event (E1 and E2 coactivate)
        solver.update_coactivation_ema({"req2": [1, 2]})
        decayed_score = solver._coactivation_matrix[3, 7]

        self.assertLess(decayed_score, initial_score)
        self.assertAlmostEqual(decayed_score, initial_score * 0.8, places=3)

    def test_coactivation_changes_ranking(self):
        """
        Test 3: Co-activation synergy breaks tie / alters placement vs pure frequency.
        Setup:
        - E0 has frequency 2
        - E1, E2, E3 all have frequency 1
        - However, E1 and E0 have a strong established co-activation affinity.
        - Under capacity = 2, Co-Activation solver should choose {E0, E1} rather than arbitrary tie.
        """
        solver = BatchAwareCoActivationSolver(
            num_experts=8,
            coactivation_weight=1.0,
            migration_penalty_weight=0.0,
            decay_rate=0.9
        )
        # Establish prior coactivation between E0 and E1
        for _ in range(5):
            solver.update_coactivation_ema({"prior_req": [0, 1]})

        # Now present batch:
        # Req A: [0, 1]
        # Req B: [0, 2]
        # Frequencies: E0: 2, E1: 1, E2: 1.
        batch = BatchRoutingEvent.from_events(
            batch_id="test_synergy",
            step_idx=0,
            layer_idx=0,
            events=[
                TokenRoutingEvent("req_A", step_idx=0, layer_idx=0, token_idx=0, expert_indices=[0, 1]),
                TokenRoutingEvent("req_B", step_idx=0, layer_idx=0, token_idx=0, expert_indices=[0, 2]),
            ]
        )
        dec = solver.solve(batch, fast_capacity=2)
        # Must select E0 (highest frequency) and E1 (highest coactivation synergy with E0)
        self.assertEqual(dec.fast_resident_experts, {0, 1})

    def test_predictive_solver(self):
        solver = PredictiveActivationAwareSolver(num_experts=self.num_experts)
        dec = solver.solve(self.batch_event, fast_capacity=3)
        self.assertEqual(len(dec.fast_resident_experts), 3)
        self.assertGreaterEqual(dec.hits, 1)

    def test_cxl_lru_tiering_solver(self):
        solver = CXLLRUTieringSolver(num_experts=self.num_experts)
        dec1 = solver.solve(self.batch_event, fast_capacity=3)
        self.assertEqual(len(dec1.fast_resident_experts), 3)

        # Second step with new expert access
        event2 = BatchRoutingEvent.from_events(
            batch_id="batch_2",
            step_idx=1,
            layer_idx=0,
            events=[TokenRoutingEvent("req_C", step_idx=1, layer_idx=0, token_idx=0, expert_indices=[14, 15])]
        )
        dec2 = solver.solve(event2, fast_capacity=3)
        self.assertEqual(len(dec2.fast_resident_experts), 3)
        # 14 and 15 must be promoted into fast resident
        self.assertTrue(14 in dec2.fast_resident_experts or 15 in dec2.fast_resident_experts)


if __name__ == "__main__":
    unittest.main()
