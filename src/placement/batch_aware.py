"""
TierMoE Proposed Placement Solvers:
- BatchAwareGreedySolver: Aggregate concurrent batch demand optimization with migration awareness.
- BatchAwareCoActivationSolver: Aggregate batch demand + temporally decayed (EMA) pairwise expert co-activation.
"""

import time
from typing import Dict, List, Optional, Set
import numpy as np
from .base import PlacementDecision, PlacementSolver
from ..workload.trace_schema import BatchRoutingEvent


class BatchAwareGreedySolver(PlacementSolver):
    """
    TierMoE Marginal Utility Solver.
    Ranks experts by aggregate demand across concurrent batch B with residency hysteresis.
    """

    def __init__(
        self,
        num_experts: int = 128,
        migration_penalty_weight: float = 0.5
    ):
        super().__init__(name="TierMoE-Batch-Aware-Greedy", num_experts=num_experts)
        self.migration_penalty_weight = migration_penalty_weight

    def reset(self) -> None:
        pass

    def solve(
        self,
        batch_event: BatchRoutingEvent,
        fast_capacity: int,
        current_fast_tier: Optional[Set[int]] = None
    ) -> PlacementDecision:
        t0 = time.perf_counter()
        cap = min(fast_capacity, self.num_experts)
        current = current_fast_tier or set()
        demanded = set(batch_event.expert_frequency.keys())

        # Vectorized score construction (Instantaneous batch demand + Hysteresis)
        scores = np.zeros(self.num_experts, dtype=np.float32)
        for e, freq in batch_event.expert_frequency.items():
            if e < self.num_experts:
                scores[e] = freq

        if current and self.migration_penalty_weight > 0.0:
            for e in current:
                if e < self.num_experts:
                    scores[e] += self.migration_penalty_weight

        # Top-cap experts
        if cap >= self.num_experts:
            fast_resident = set(range(self.num_experts))
        elif cap > 0:
            top_k_indices = np.argpartition(-scores, cap - 1)[:cap]
            fast_resident = set(top_k_indices.tolist())
        else:
            fast_resident = set()

        cxl_resident = set(range(self.num_experts)) - fast_resident
        promotions = fast_resident - current
        evictions = current - fast_resident
        missing_demanded = demanded - fast_resident

        hits = 0
        misses = 0
        for exp_id, count in batch_event.expert_frequency.items():
            if exp_id in fast_resident:
                hits += count
            else:
                misses += count

        t1 = time.perf_counter()
        return PlacementDecision(
            step_idx=batch_event.step_idx,
            layer_idx=batch_event.layer_idx,
            fast_resident_experts=fast_resident,
            cxl_resident_experts=cxl_resident,
            promotions=promotions,
            evictions=evictions,
            unique_demanded_experts=demanded,
            unique_missing_experts=missing_demanded,
            hits=hits,
            misses=misses,
            solver_time_us=(t1 - t0) * 1e6
        )


class BatchAwareCoActivationSolver(PlacementSolver):
    """
    TierMoE Co-Activation Aware Solver with Exponential Moving Average (EMA) Decay.

    Temporal Model Specification:
    - Decay parameter (beta): 0.90 per step (configurable).
    - Update rule: C_t = beta * C_{t-1} + (1 - beta) * Delta_C_t, where Delta_C_t is the
      instantaneous co-occurrence matrix for the current step.
    - Timing: Matrix decays and incorporates the current batch's co-activations before placement.
    - Scale: Normalized EMA keeps pairwise synergy values on the same scale [0, B] as instantaneous frequency.
    """

    def __init__(
        self,
        num_experts: int = 128,
        coactivation_weight: float = 0.3,
        migration_penalty_weight: float = 0.5,
        decay_rate: float = 0.90
    ):
        super().__init__(name="TierMoE-Batch-Aware-CoActivation", num_experts=num_experts)
        self.coactivation_weight = coactivation_weight
        self.migration_penalty_weight = migration_penalty_weight
        self.decay_rate = decay_rate
        self._coactivation_matrix = np.zeros((num_experts, num_experts), dtype=np.float32)

    def reset(self) -> None:
        self._coactivation_matrix.fill(0.0)

    def update_coactivation_ema(self, request_expert_map: Dict[str, List[int]]) -> None:
        """
        Applies exponential decay to historical co-activation matrix and adds current step delta.
        """
        # Step 1: Exponential decay of past history
        self._coactivation_matrix *= self.decay_rate

        # Step 2: Extract current batch instantaneous co-occurrences
        delta_matrix = np.zeros((self.num_experts, self.num_experts), dtype=np.float32)
        for exp_list in request_expert_map.values():
            if len(exp_list) > 1:
                unique_exps = np.array(list(set(exp_list)), dtype=np.int32)
                valid_exps = unique_exps[unique_exps < self.num_experts]
                if len(valid_exps) > 1:
                    mesh_i, mesh_j = np.meshgrid(valid_exps, valid_exps)
                    mask = mesh_i != mesh_j
                    delta_matrix[mesh_i[mask], mesh_j[mask]] += 1.0

        # Step 3: EMA blend: C_t = beta * C_{t-1} + (1 - beta) * Delta_C
        self._coactivation_matrix += (1.0 - self.decay_rate) * delta_matrix

    def solve(
        self,
        batch_event: BatchRoutingEvent,
        fast_capacity: int,
        current_fast_tier: Optional[Set[int]] = None
    ) -> PlacementDecision:
        t0 = time.perf_counter()
        # Update temporal co-activation matrix with EMA
        self.update_coactivation_ema(batch_event.request_expert_map)

        cap = min(fast_capacity, self.num_experts)
        current = current_fast_tier or set()
        demanded = set(batch_event.expert_frequency.keys())

        # Step 1: Base scores vector (Instantaneous frequency + Hysteresis)
        scores = np.zeros(self.num_experts, dtype=np.float32)
        for e, freq in batch_event.expert_frequency.items():
            if e < self.num_experts:
                scores[e] = freq

        if current and self.migration_penalty_weight > 0.0:
            for e in current:
                if e < self.num_experts:
                    scores[e] += self.migration_penalty_weight

        # Step 2: Incremental greedy selection using synergy vector
        if cap >= self.num_experts:
            fast_resident = set(range(self.num_experts))
        elif cap > 0:
            selected: List[int] = []
            available_mask = np.ones(self.num_experts, dtype=bool)
            synergy_vector = np.zeros(self.num_experts, dtype=np.float32)

            for _ in range(cap):
                # Combined score = base score + weighted co-activation synergy
                total_scores = scores + (self.coactivation_weight * synergy_vector)
                total_scores[~available_mask] = -1e9

                best_exp = int(np.argmax(total_scores))
                selected.append(best_exp)
                available_mask[best_exp] = False

                # Incrementally add selected expert's row to synergy vector
                synergy_vector += self._coactivation_matrix[best_exp, :]

            fast_resident = set(selected)
        else:
            fast_resident = set()

        cxl_resident = set(range(self.num_experts)) - fast_resident
        promotions = fast_resident - current
        evictions = current - fast_resident
        missing_demanded = demanded - fast_resident

        hits = 0
        misses = 0
        for exp_id, count in batch_event.expert_frequency.items():
            if exp_id in fast_resident:
                hits += count
            else:
                misses += count

        t1 = time.perf_counter()
        return PlacementDecision(
            step_idx=batch_event.step_idx,
            layer_idx=batch_event.layer_idx,
            fast_resident_experts=fast_resident,
            cxl_resident_experts=cxl_resident,
            promotions=promotions,
            evictions=evictions,
            unique_demanded_experts=demanded,
            unique_missing_experts=missing_demanded,
            hits=hits,
            misses=misses,
            solver_time_us=(t1 - t0) * 1e6
        )
