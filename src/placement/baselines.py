"""
Standard Baseline MoE Placement Solvers:
- Baseline 0: HBM-Only (unconstrained upper bound)
- Baseline 1: Naive Overflow (FIFO arrival order)
- Baseline 2: Static LFU (Global frequency ranking)
- Baseline 3: Single-Request Greedy (Independent sequential request placement)
"""

import time
from typing import Dict, List, Optional, Set
import numpy as np
from .base import PlacementDecision, PlacementSolver
from ..workload.trace_schema import BatchRoutingEvent


class HBMOnlySolver(PlacementSolver):
    """
    Baseline 0: All experts resident in fast GPU memory.
    Upper bound performance reference.
    """

    def __init__(self, num_experts: int = 128):
        super().__init__(name="Baseline-0-HBM-Only", num_experts=num_experts)

    def reset(self) -> None:
        pass

    def solve(
        self,
        batch_event: BatchRoutingEvent,
        fast_capacity: int,
        current_fast_tier: Optional[Set[int]] = None
    ) -> PlacementDecision:
        t0 = time.perf_counter()
        all_experts = set(range(self.num_experts))
        total_accesses = sum(batch_event.expert_frequency.values())
        demanded = set(batch_event.expert_frequency.keys())

        current = current_fast_tier or set()
        promotions = all_experts - current
        evictions = set()

        t1 = time.perf_counter()
        return PlacementDecision(
            step_idx=batch_event.step_idx,
            layer_idx=batch_event.layer_idx,
            fast_resident_experts=all_experts,
            cxl_resident_experts=set(),
            promotions=promotions,
            evictions=evictions,
            unique_demanded_experts=demanded,
            unique_missing_experts=set(),
            hits=total_accesses,
            misses=0,
            solver_time_us=(t1 - t0) * 1e6
        )


class NaiveOverflowSolver(PlacementSolver):
    """
    Baseline 1: Naive FIFO overflow.
    Places active experts into fast tier in order of encounter until full.
    Remaining experts stay in CXL memory.
    """

    def __init__(self, num_experts: int = 128):
        super().__init__(name="Baseline-1-Naive-Overflow", num_experts=num_experts)

    def reset(self) -> None:
        pass

    def solve(
        self,
        batch_event: BatchRoutingEvent,
        fast_capacity: int,
        current_fast_tier: Optional[Set[int]] = None
    ) -> PlacementDecision:
        t0 = time.perf_counter()
        current = set(current_fast_tier or set())
        cap = min(fast_capacity, self.num_experts)
        demanded = set(batch_event.expert_frequency.keys())

        # Preserve existing resident experts, add new requested ones until cap
        new_fast = set()
        for e in current:
            if len(new_fast) < cap:
                new_fast.add(e)

        # Add newly requested experts in encounter order
        for req_id, exp_list in batch_event.request_expert_map.items():
            for e in exp_list:
                if len(new_fast) < cap:
                    new_fast.add(e)

        # Calculate hits and misses
        hits = 0
        misses = 0
        for exp_id, count in batch_event.expert_frequency.items():
            if exp_id in new_fast:
                hits += count
            else:
                misses += count

        promotions = new_fast - current
        evictions = current - new_fast
        cxl_resident = set(range(self.num_experts)) - new_fast
        missing_demanded = demanded - new_fast

        t1 = time.perf_counter()
        return PlacementDecision(
            step_idx=batch_event.step_idx,
            layer_idx=batch_event.layer_idx,
            fast_resident_experts=new_fast,
            cxl_resident_experts=cxl_resident,
            promotions=promotions,
            evictions=evictions,
            unique_demanded_experts=demanded,
            unique_missing_experts=missing_demanded,
            hits=hits,
            misses=misses,
            solver_time_us=(t1 - t0) * 1e6
        )


class StaticLFUSolver(PlacementSolver):
    """
    Baseline 2: Static / Global Least Frequently Used (LFU).
    Keeps the globally most frequently accessed experts resident in fast memory.
    """

    def __init__(self, num_experts: int = 128, global_freq: Optional[Dict[int, int]] = None):
        super().__init__(name="Baseline-2-Static-LFU", num_experts=num_experts)
        self._global_freq: Dict[int, int] = dict(global_freq or {})

    def reset(self) -> None:
        self._global_freq.clear()

    def update_global_frequency(self, freq_dict: Dict[int, int]) -> None:
        for e, count in freq_dict.items():
            self._global_freq[e] = self._global_freq.get(e, 0) + count

    def solve(
        self,
        batch_event: BatchRoutingEvent,
        fast_capacity: int,
        current_fast_tier: Optional[Set[int]] = None
    ) -> PlacementDecision:
        t0 = time.perf_counter()
        self.update_global_frequency(batch_event.expert_frequency)

        cap = min(fast_capacity, self.num_experts)
        demanded = set(batch_event.expert_frequency.keys())

        # Sort experts by global popularity descending
        sorted_experts = sorted(
            range(self.num_experts),
            key=lambda e: self._global_freq.get(e, 0),
            reverse=True
        )
        fast_resident = set(sorted_experts[:cap])
        cxl_resident = set(sorted_experts[cap:])

        current = current_fast_tier or set()
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


class SingleRequestSolver(PlacementSolver):
    """
    Baseline 3: Single-Request Greedy.
    Optimizes fast-tier residency for individual requests sequentially
    without aggregating cross-request batch demand.
    """

    def __init__(self, num_experts: int = 128):
        super().__init__(name="Baseline-3-Single-Request", num_experts=num_experts)

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
        fast_resident: Set[int] = set()
        demanded = set(batch_event.expert_frequency.keys())

        # Iterate request by request independently in arrival order
        for req_id, exp_list in batch_event.request_expert_map.items():
            for e in exp_list:
                if len(fast_resident) < cap:
                    fast_resident.add(e)
                else:
                    break
            if len(fast_resident) >= cap:
                break

        # Fill any remaining capacity with remaining unallocated experts
        if len(fast_resident) < cap:
            for e in range(self.num_experts):
                if len(fast_resident) < cap:
                    fast_resident.add(e)
                else:
                    break

        cxl_resident = set(range(self.num_experts)) - fast_resident
        current = current_fast_tier or set()
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


class PredictiveActivationAwareSolver(PlacementSolver):
    """
    Baseline 4: Activation-Aware Predictive Placement (MoE-Infinity / ProMoE style).
    Maintains per-request temporal activation history and predicts next-step expert activations
    using sequence-level locality. Combines immediate demand with lookahead predictions.
    """

    def __init__(self, num_experts: int = 128, history_len: int = 8, decay: float = 0.85):
        super().__init__(name="Baseline-4-Predictive-Activation-Aware", num_experts=num_experts)
        self.history_len = history_len
        self.decay = decay
        self._request_history: Dict[str, List[Set[int]]] = {}

    def reset(self) -> None:
        self._request_history.clear()

    def solve(
        self,
        batch_event: BatchRoutingEvent,
        fast_capacity: int,
        current_fast_tier: Optional[Set[int]] = None
    ) -> PlacementDecision:
        t0 = time.perf_counter()
        cap = min(fast_capacity, self.num_experts)
        current = set(current_fast_tier or set())
        demanded = set(batch_event.expert_frequency.keys())

        # Update per-sequence activation history and compute predictive lookahead scores
        predictive_scores = np.zeros(self.num_experts, dtype=np.float32)

        for req_id, exp_list in batch_event.request_expert_map.items():
            if req_id not in self._request_history:
                self._request_history[req_id] = []
            cur_set = set(exp_list)
            self._request_history[req_id].append(cur_set)
            if len(self._request_history[req_id]) > self.history_len:
                self._request_history[req_id].pop(0)

            # Weight historical activations with geometric decay
            for hist_idx, past_set in enumerate(reversed(self._request_history[req_id])):
                weight = self.decay ** hist_idx
                for e in past_set:
                    if e < self.num_experts:
                        predictive_scores[e] += weight

        # Combine immediate demand with sequence prediction
        for e, freq in batch_event.expert_frequency.items():
            if e < self.num_experts:
                predictive_scores[e] += freq * 2.0

        # Select top-cap predicted experts
        if cap >= self.num_experts:
            fast_resident = set(range(self.num_experts))
        elif cap > 0:
            top_indices = np.argpartition(-predictive_scores, cap - 1)[:cap]
            fast_resident = set(top_indices.tolist())
        else:
            fast_resident = set()

        cxl_resident = set(range(self.num_experts)) - fast_resident
        promotions = fast_resident - current
        evictions = current - fast_resident
        missing_demanded = demanded - fast_resident

        hits = sum(batch_event.expert_frequency.get(e, 0) for e in fast_resident)
        misses = sum(batch_event.expert_frequency.get(e, 0) for e in (demanded - fast_resident))

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


class CXLLRUTieringSolver(PlacementSolver):
    """
    Baseline 5: CXL Memory Tiering with Demand-Driven LRU Page Migration (CXL-MoE architecture).
    Maintains fast memory as an active LRU cache. Upon access, touches resident experts;
    demanded non-resident experts trigger on-demand CXL promotions, evicting the least-recently-used.
    """

    def __init__(self, num_experts: int = 128):
        super().__init__(name="Baseline-5-CXL-LRU-Tiering", num_experts=num_experts)
        self._last_access: Dict[int, int] = {}
        self._clock = 0

    def reset(self) -> None:
        self._last_access.clear()
        self._clock = 0

    def solve(
        self,
        batch_event: BatchRoutingEvent,
        fast_capacity: int,
        current_fast_tier: Optional[Set[int]] = None
    ) -> PlacementDecision:
        t0 = time.perf_counter()
        self._clock += 1
        cap = min(fast_capacity, self.num_experts)
        current = set(current_fast_tier or set())
        demanded = set(batch_event.expert_frequency.keys())

        # If fast tier is uninitialized, fill with initial demanded up to cap
        if not current:
            fast_resident = set(list(demanded)[:cap])
            if len(fast_resident) < cap:
                for e in range(self.num_experts):
                    if len(fast_resident) < cap:
                        fast_resident.add(e)
                    else:
                        break
        else:
            fast_resident = set(current)

        # Update timestamps for currently resident accessed experts
        for e in demanded:
            if e in fast_resident:
                self._last_access[e] = self._clock

        # Missing experts must be promoted into fast tier via LRU eviction
        missing = [e for e in demanded if e not in fast_resident]
        for e in missing:
            if len(fast_resident) < cap:
                fast_resident.add(e)
                self._last_access[e] = self._clock
            elif cap > 0:
                # Find LRU candidate in fast_resident (preferring ones not in current step's demanded set)
                candidates = list(fast_resident - demanded)
                if not candidates:
                    candidates = list(fast_resident)
                # Sort candidate by oldest access time
                lru_expert = min(candidates, key=lambda exp: self._last_access.get(exp, 0))
                fast_resident.remove(lru_expert)
                fast_resident.add(e)
                self._last_access[e] = self._clock

        cxl_resident = set(range(self.num_experts)) - fast_resident
        promotions = fast_resident - current
        evictions = current - fast_resident
        missing_demanded = demanded - fast_resident

        hits = sum(batch_event.expert_frequency.get(e, 0) for e in fast_resident)
        misses = sum(batch_event.expert_frequency.get(e, 0) for e in (demanded - fast_resident))

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
