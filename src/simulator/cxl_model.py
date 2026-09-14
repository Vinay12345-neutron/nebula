"""
CXL Memory Tiering Simulator.
Models CXL 2.0/3.0 Type-3 memory pool characteristics, bandwidth constraints,
latency penalties, queue serialization, and cross-tier migration traffic.

Traffic Accounting Semantics:
1. demand_cxl_traffic_bytes:
   Bytes transferred over CXL on-demand to satisfy accesses to distinct non-resident
   experts that are streamed without being promoted to the fast tier.
   Computed as: len(unique_missing_experts) * expert_size_bytes.
2. promotion_traffic_bytes:
   Bytes explicitly transferred across CXL to promote newly resident experts into fast tier.
   Computed as: len(promotions) * expert_size_bytes.
3. total_cxl_traffic_bytes:
   Total unique parameter bytes crossing the CXL tier boundary:
   total_cxl_traffic_bytes = demand_cxl_traffic_bytes + promotion_traffic_bytes.
   Zero double-counting: an expert promoted is resident for that step and not counted as a demand miss.
4. Clean Evictions:
   Model weights are read-only; clean evictions discard memory pages and generate 0 writeback bus traffic.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from ..placement.base import PlacementDecision


@dataclass
class SimulationStepResult:
    """Detailed simulation outputs for a single placement step."""
    step_idx: int
    layer_idx: int
    hits: int
    misses: int
    hit_rate: float
    promotions_count: int
    evictions_count: int
    unique_demanded_count: int
    unique_missing_count: int
    demand_cxl_traffic_bytes: int
    promotion_traffic_bytes: int
    total_cxl_traffic_bytes: int
    migration_volume_bytes: int
    migration_latency_us: float
    cxl_access_latency_us: float
    solver_time_us: float
    modeled_cxl_transfer_time_ms: float = 0.0

    @property
    def migration_volume_mb(self) -> float:
        return self.migration_volume_bytes / (1024 * 1024)

    @property
    def demand_cxl_traffic_mb(self) -> float:
        return self.demand_cxl_traffic_bytes / (1024 * 1024)

    @property
    def promotion_traffic_mb(self) -> float:
        return self.promotion_traffic_bytes / (1024 * 1024)

    @property
    def cxl_traffic_mb(self) -> float:
        return self.total_cxl_traffic_bytes / (1024 * 1024)


@dataclass
class SimulationSummary:
    """Aggregate benchmark results across an entire experiment run."""
    algorithm_name: str
    total_steps: int
    total_accesses: int
    total_hits: int
    total_misses: int
    overall_hit_rate: float
    total_cxl_traffic_mb: float
    demand_cxl_traffic_mb: float
    promotion_traffic_mb: float
    total_migration_volume_mb: float
    total_migration_latency_ms: float
    total_cxl_access_latency_ms: float
    total_solver_time_ms: float
    avg_solver_time_us: float
    total_modeled_cxl_transfer_time_ms: float = 0.0
    step_results: List[SimulationStepResult] = field(default_factory=list)

    def to_dict(self) -> Dict[str, float]:
        """Returns standard metrics dictionary."""
        return {
            "algorithm": self.algorithm_name,
            "overall_hit_rate": self.overall_hit_rate,
            "cxl_traffic_mb": self.total_cxl_traffic_mb,
            "demand_cxl_traffic_mb": self.demand_cxl_traffic_mb,
            "promotion_traffic_mb": self.promotion_traffic_mb,
            "migration_volume_mb": self.total_migration_volume_mb,
            "migration_latency_ms": self.total_migration_latency_ms,
            "cxl_access_latency_ms": self.total_cxl_access_latency_ms,
            "modeled_cxl_transfer_time_ms": self.total_modeled_cxl_transfer_time_ms,
            "total_solver_time_ms": self.total_solver_time_ms,
            "avg_solver_time_us": self.avg_solver_time_us,
        }


class CXLMemoryTierSimulator:
    """
    Simulates CXL memory pool access latency, bandwidth contention,
    and migration volume driven by expert placement decisions.
    """

    def __init__(
        self,
        latency_penalty_ns: float = 300.0,
        bandwidth_gbps: float = 32.0,
        expert_size_bytes: int = 268435456,  # 256 MB per expert
        contention_factor: float = 1.25
    ):
        self.latency_penalty_ns = latency_penalty_ns
        self.bandwidth_gbps = bandwidth_gbps
        self.expert_size_bytes = expert_size_bytes
        self.contention_factor = contention_factor

    def simulate_step(self, decision: PlacementDecision) -> SimulationStepResult:
        """
        Simulates latency, bandwidth saturation, and traffic for one decision with deduplication.
        """
        num_promotions = len(decision.promotions)
        num_evictions = len(decision.evictions)
        num_unique_missing = len(decision.unique_missing_experts)
        num_unique_demanded = len(decision.unique_demanded_experts)

        # Promotion traffic = bulk parameter fetch for newly resident experts
        promotion_traffic_bytes = num_promotions * self.expert_size_bytes

        # Demand traffic = bulk parameter streaming for unique non-resident missing experts (not promoted)
        demand_cxl_traffic_bytes = num_unique_missing * self.expert_size_bytes

        # Total unique bytes crossing the CXL bus
        total_cxl_traffic_bytes = demand_cxl_traffic_bytes + promotion_traffic_bytes

        # Migration volume = promotion volume (clean evictions do not require writeback)
        migration_volume_bytes = promotion_traffic_bytes

        # Migration transfer latency (microseconds) over CXL bandwidth
        bytes_per_us = (self.bandwidth_gbps * 1e9) / 1e6
        migration_latency_us = (migration_volume_bytes / bytes_per_us) if bytes_per_us > 0 else 0.0

        # Apply contention penalty if migrating multiple experts concurrently
        if num_promotions > 1:
            migration_latency_us *= (self.contention_factor ** (num_promotions - 1))

        # CXL read access latency penalty for unique on-demand streaming misses
        cxl_access_latency_us = (num_unique_missing * self.latency_penalty_ns) / 1e3

        # Modeled CXL parameter transfer time (milliseconds):
        # Quantifies cross-tier transfer cost across CXL bandwidth plus link round-trip latency overhead.
        # Total distinct expert parameter block transfers = promotions + unique unpromoted demand misses.
        num_transfers = num_promotions + num_unique_missing
        transfer_latency_overhead_ms = (num_transfers * self.latency_penalty_ns) / 1e6
        bytes_per_ms = (self.bandwidth_gbps * 1e9) / 1e3
        transfer_transmission_time_ms = (total_cxl_traffic_bytes / bytes_per_ms) if bytes_per_ms > 0 else 0.0
        modeled_cxl_transfer_time_ms = transfer_latency_overhead_ms + transfer_transmission_time_ms

        return SimulationStepResult(
            step_idx=decision.step_idx,
            layer_idx=decision.layer_idx,
            hits=decision.hits,
            misses=decision.misses,
            hit_rate=decision.hit_rate,
            promotions_count=num_promotions,
            evictions_count=num_evictions,
            unique_demanded_count=num_unique_demanded,
            unique_missing_count=num_unique_missing,
            demand_cxl_traffic_bytes=demand_cxl_traffic_bytes,
            promotion_traffic_bytes=promotion_traffic_bytes,
            total_cxl_traffic_bytes=total_cxl_traffic_bytes,
            migration_volume_bytes=migration_volume_bytes,
            migration_latency_us=migration_latency_us,
            cxl_access_latency_us=cxl_access_latency_us,
            solver_time_us=decision.solver_time_us,
            modeled_cxl_transfer_time_ms=modeled_cxl_transfer_time_ms
        )

    def simulate_run(
        self,
        algorithm_name: str,
        decisions: List[PlacementDecision]
    ) -> SimulationSummary:
        """
        Simulates an entire sequence of decisions and returns aggregate metrics.
        """
        step_results = [self.simulate_step(d) for d in decisions]

        total_hits = sum(r.hits for r in step_results)
        total_misses = sum(r.misses for r in step_results)
        total_accesses = total_hits + total_misses
        overall_hit_rate = (total_hits / total_accesses) if total_accesses > 0 else 1.0

        total_cxl_bytes = sum(r.total_cxl_traffic_bytes for r in step_results)
        total_demand_bytes = sum(r.demand_cxl_traffic_bytes for r in step_results)
        total_prom_bytes = sum(r.promotion_traffic_bytes for r in step_results)
        total_mig_bytes = sum(r.migration_volume_bytes for r in step_results)
        total_mig_lat_us = sum(r.migration_latency_us for r in step_results)
        total_cxl_lat_us = sum(r.cxl_access_latency_us for r in step_results)
        total_solver_us = sum(r.solver_time_us for r in step_results)
        total_modeled_transfer_ms = sum(r.modeled_cxl_transfer_time_ms for r in step_results)

        return SimulationSummary(
            algorithm_name=algorithm_name,
            total_steps=len(step_results),
            total_accesses=total_accesses,
            total_hits=total_hits,
            total_misses=total_misses,
            overall_hit_rate=overall_hit_rate,
            total_cxl_traffic_mb=total_cxl_bytes / (1024 * 1024),
            demand_cxl_traffic_mb=total_demand_bytes / (1024 * 1024),
            promotion_traffic_mb=total_prom_bytes / (1024 * 1024),
            total_migration_volume_mb=total_mig_bytes / (1024 * 1024),
            total_migration_latency_ms=total_mig_lat_us / 1e3,
            total_cxl_access_latency_ms=total_cxl_lat_us / 1e3,
            total_solver_time_ms=total_solver_us / 1e3,
            avg_solver_time_us=(total_solver_us / len(step_results)) if step_results else 0.0,
            total_modeled_cxl_transfer_time_ms=total_modeled_transfer_ms,
            step_results=step_results
        )
