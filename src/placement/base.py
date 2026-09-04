"""
Abstract Base Class and Decision Data Structures for MoE Placement Solvers.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import time
from typing import Dict, List, Optional, Set
from ..workload.trace_schema import BatchRoutingEvent


@dataclass
class PlacementDecision:
    """
    Represents a placement assignment and transfer actions for a single batch step and layer.
    """
    step_idx: int
    layer_idx: int
    fast_resident_experts: Set[int]
    cxl_resident_experts: Set[int]
    promotions: Set[int] = field(default_factory=set)        # Experts newly fetched into fast tier
    evictions: Set[int] = field(default_factory=set)         # Experts evicted from fast tier
    unique_demanded_experts: Set[int] = field(default_factory=set)  # All distinct experts requested in this step
    unique_missing_experts: Set[int] = field(default_factory=set)   # Demanded experts not in fast tier (unpromoted)
    hits: int = 0                                            # Fast tier token accesses
    misses: int = 0                                          # CXL tier token accesses
    solver_time_us: float = 0.0                              # Solver execution latency (microseconds)

    @property
    def total_accesses(self) -> int:
        return self.hits + self.misses

    @property
    def hit_rate(self) -> float:
        return (self.hits / self.total_accesses) if self.total_accesses > 0 else 1.0


class PlacementSolver(ABC):
    """
    Abstract interface for all MoE fast/CXL memory placement policies.
    """

    def __init__(self, name: str, num_experts: int = 128):
        self.name = name
        self.num_experts = num_experts

    @abstractmethod
    def reset(self) -> None:
        """Resets any internal history/state."""
        pass

    @abstractmethod
    def solve(
        self,
        batch_event: BatchRoutingEvent,
        fast_capacity: int,
        current_fast_tier: Optional[Set[int]] = None
    ) -> PlacementDecision:
        """
        Computes the expert placement decision for a given batch routing event under fast memory capacity constraint.
        Args:
            batch_event: Aggregated batch routing demand at current step/layer.
            fast_capacity: Maximum number of expert parameter sets fast tier can hold.
            current_fast_tier: Currently resident experts in fast tier from previous step.
        Returns:
            PlacementDecision containing residency maps, migrations, and hit/miss counts.
        """
        pass
