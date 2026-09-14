"""
CXLMemSim Memory-System Simulator Adapter for EXP-05B.
Interfaces TierMoE placement decisions with the detailed CXLMemSim memory-system model.

Semantics Preserved from EXP-05A:
1. Expert Block Size: Exactly 256 MiB (268,435,456 bytes) = 4,194,304 cache lines (64B each).
2. Deterministic Non-Overlapping Address Aperture:
   BaseAddr(layer_idx, expert_id) = (layer_idx * 128 + expert_id) * 256 MiB.
3. Batch Deduplication: Multiple tokens requesting the same missing expert in a batch step
   generate exactly ONE bulk parameter transfer of 256 MiB.
4. Read-Only Weights: Model parameters are read-only; clean evictions incur 0 writeback bus traffic.
5. Concurrent Transfer Modeling: Multi-expert transfers within a batch step share the CXL link,
   competing for bandwidth and experiencing CXLMemSim-modeled memory-controller queueing,
   link serialization, and MLC-calibrated bandwidth saturation.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple
import numpy as np

from ..placement.base import PlacementDecision


EXPERT_SIZE_BYTES = 268435456  # 256 MiB
CACHE_LINE_SIZE = 64            # 64 bytes per CXL transaction
LINES_PER_EXPERT = EXPERT_SIZE_BYTES // CACHE_LINE_SIZE  # 4,194,304 lines


@dataclass
class CXLMemSimConfig:
    """Configuration parameters matching CXLMemSim CXLMemExpander & BandwidthModelConfig."""
    read_bw_gbps: float = 32.0
    write_bw_gbps: float = 32.0
    read_latency_ns: float = 300.0
    write_latency_ns: float = 300.0
    dram_latency_ns: float = 110.0
    knee_utilization: float = 0.80
    saturation_utilization: float = 0.98
    low_utilization_slope: float = 0.05
    max_penalty_ns: float = 5000.0
    min_window_ns: float = 100000.0  # 100 us minimum accounting window


def get_expert_address(layer_idx: int, expert_id: int) -> int:
    """
    Deterministic non-overlapping address aperture mapping for each of the 6,144 experts.
    BaseAddr(layer, expert) = (layer * 128 + expert) * 256 MiB.
    """
    expert_global_id = layer_idx * 128 + expert_id
    return expert_global_id * EXPERT_SIZE_BYTES


def calculate_mlc_bandwidth_penalty(
    cfg: CXLMemSimConfig,
    access_count: int,
    first_timestamp_ns: float,
    last_timestamp_ns: float,
    read_ratio: float = 1.0
) -> Tuple[float, float, float]:
    """
    Exact implementation of CXLMemSim calculate_mlc_bandwidth_penalty
    from CXLMemSim/src/cxlendpoint.cpp lines 52-92.
    Returns: (penalty_ns, observed_gbps, utilization)
    """
    if access_count == 0:
        return 0.0, 0.0, 0.0

    observed_window_ns = max(0.0, last_timestamp_ns - first_timestamp_ns)
    window_ns = max(observed_window_ns, cfg.min_window_ns)
    observed_gbps = (access_count * CACHE_LINE_SIZE) / window_ns
    peak_gbps = cfg.read_bw_gbps if read_ratio >= 0.95 else cfg.read_bw_gbps
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


def calculate_pipeline_latency(cfg: CXLMemSimConfig) -> float:
    """
    CXLMemSim pipeline latency stages from CXLMemSim/src/cxlendpoint.cpp lines 768-794:
    frontend (10ns) + forward (15ns) + memory_read + response (20ns) + flit overhead (6.5ns).
    """
    frontend_latency = 10.0
    forward_latency = 15.0
    mem_latency = cfg.read_latency_ns
    response_latency = 20.0
    protocol_overhead = 6.5  # 65 data flit bytes * 0.1 ns/byte
    return frontend_latency + forward_latency + mem_latency + response_latency + protocol_overhead


def calculate_controller_congestion_delay(num_concurrent_streams: int) -> float:
    """
    CXLMemSim memory-controller congestion delay from CXLMemSim/src/cxlendpoint.cpp lines 830-842.
    Queue occupancy scales with the number of concurrent contending streams.
    MAX_QUEUE_SIZE = 64.
    """
    max_queue_size = 64.0
    queue_utilization = min(1.0, num_concurrent_streams / max_queue_size)

    if queue_utilization < 0.5:
        return 0.0
    elif queue_utilization < 0.8:
        return (queue_utilization - 0.5) * 20.0
    else:
        return 6.0 + (queue_utilization - 0.8) * 100.0


@dataclass
class CXLMemSimStepResult:
    """Detailed simulation outputs for a single placement decision under CXLMemSim."""
    step_idx: int
    layer_idx: int
    hits: int
    misses: int
    hit_rate: float
    promotions_count: int
    evictions_count: int
    unique_demanded_count: int
    unique_missing_count: int
    total_transfers_count: int
    demand_cxl_traffic_bytes: int
    promotion_traffic_bytes: int
    total_cxl_traffic_bytes: int
    migration_volume_bytes: int
    cxlmemsim_modeled_transfer_time_ms: float
    analytical_transfer_time_ms: float
    cxlmemsim_link_utilization: float
    cxlmemsim_effective_bw_gbps: float
    cxlmemsim_queue_penalty_ns: float
    cxlmemsim_congestion_delay_ns: float
    solver_time_us: float

    @property
    def total_cxl_traffic_mb(self) -> float:
        return self.total_cxl_traffic_bytes / (1024 * 1024)

    @property
    def demand_cxl_traffic_mb(self) -> float:
        return self.demand_cxl_traffic_bytes / (1024 * 1024)

    @property
    def promotion_traffic_mb(self) -> float:
        return self.promotion_traffic_bytes / (1024 * 1024)


@dataclass
class CXLMemSimSummary:
    """Aggregate benchmark results for an entire run under CXLMemSim."""
    algorithm_name: str
    total_steps: int
    total_accesses: int
    total_hits: int
    total_misses: int
    overall_hit_rate: float
    total_cxl_traffic_mb: float
    demand_cxl_traffic_mb: float
    promotion_traffic_mb: float
    total_promotions_count: int
    total_unique_missing_count: int
    total_transfers_count: int
    total_cxlmemsim_transfer_time_ms: float
    total_analytical_transfer_time_ms: float
    avg_cxlmemsim_link_utilization: float
    avg_cxlmemsim_effective_bw_gbps: float
    total_solver_time_ms: float
    avg_solver_time_us: float
    step_results: List[CXLMemSimStepResult] = field(default_factory=list)

    def to_dict(self) -> Dict[str, float]:
        return {
            "algorithm": self.algorithm_name,
            "overall_hit_rate": self.overall_hit_rate,
            "cxl_traffic_mb": self.total_cxl_traffic_mb,
            "demand_cxl_traffic_mb": self.demand_cxl_traffic_mb,
            "promotion_traffic_mb": self.promotion_traffic_mb,
            "total_promotions_count": self.total_promotions_count,
            "total_unique_missing_count": self.total_unique_missing_count,
            "total_transfers_count": self.total_transfers_count,
            "cxlmemsim_transfer_time_ms": self.total_cxlmemsim_transfer_time_ms,
            "analytical_transfer_time_ms": self.total_analytical_transfer_time_ms,
            "cxlmemsim_link_utilization": self.avg_cxlmemsim_link_utilization,
            "cxlmemsim_effective_bw_gbps": self.avg_cxlmemsim_effective_bw_gbps,
            "total_solver_time_ms": self.total_solver_time_ms,
            "avg_solver_time_us": self.avg_solver_time_us,
        }


class CXLMemSimTierSimulator:
    """
    EXP-05B CXL Memory Tiering Simulator Adapter.
    Executes full 256-MiB expert parameter transfers against CXLMemSim's detailed
    link, queue, and bandwidth saturation equations.
    """

    def __init__(
        self,
        bandwidth_gbps: float = 32.0,
        latency_penalty_ns: float = 300.0,
        expert_size_bytes: int = EXPERT_SIZE_BYTES,
        dram_latency_ns: float = 110.0
    ):
        self.bandwidth_gbps = bandwidth_gbps
        self.latency_penalty_ns = latency_penalty_ns
        self.expert_size_bytes = expert_size_bytes
        self.lines_per_expert = expert_size_bytes // CACHE_LINE_SIZE
        self.cfg = CXLMemSimConfig(
            read_bw_gbps=bandwidth_gbps,
            write_bw_gbps=bandwidth_gbps,
            read_latency_ns=latency_penalty_ns,
            write_latency_ns=latency_penalty_ns,
            dram_latency_ns=dram_latency_ns
        )

    def simulate_step(self, decision: PlacementDecision) -> CXLMemSimStepResult:
        """
        Simulates one placement decision step under CXLMemSim.
        Preserves deduplicated bulk parameter fetch semantics.
        """
        num_promotions = len(decision.promotions)
        num_evictions = len(decision.evictions)
        num_unique_missing = len(decision.unique_missing_experts)
        num_unique_demanded = len(decision.unique_demanded_experts)

        # Disjoint unique transfers: promotions + unpromoted unique missing
        num_transfers = num_promotions + num_unique_missing

        promotion_traffic_bytes = num_promotions * self.expert_size_bytes
        demand_cxl_traffic_bytes = num_unique_missing * self.expert_size_bytes
        total_cxl_traffic_bytes = promotion_traffic_bytes + demand_cxl_traffic_bytes
        migration_volume_bytes = promotion_traffic_bytes

        # Analytical baseline calculation (EXP-05A formula for cross-check)
        if num_transfers > 0:
            ana_overhead_ms = (num_transfers * self.latency_penalty_ns) / 1e6
            ana_tx_ms = (total_cxl_traffic_bytes / (self.bandwidth_gbps * 1e9)) * 1e3
            analytical_transfer_time_ms = ana_overhead_ms + ana_tx_ms
        else:
            analytical_transfer_time_ms = 0.0

        # CXLMemSim detailed memory-system simulation
        if num_transfers > 0:
            total_lines = num_transfers * self.lines_per_expert
            inter_arrival_ns = CACHE_LINE_SIZE / self.bandwidth_gbps

            # Link transmission duration from first to last flit emission
            duration_emission_ns = (total_lines - 1) * inter_arrival_ns
            first_ts = 0.0
            last_ts = duration_emission_ns

            # CXLMemSim MLC bandwidth saturation queue penalty
            bw_penalty_ns, observed_gbps, utilization = calculate_mlc_bandwidth_penalty(
                cfg=self.cfg,
                access_count=total_lines,
                first_timestamp_ns=first_ts,
                last_timestamp_ns=last_ts,
                read_ratio=1.0
            )

            # CXLMemSim pipeline latency for streaming requests
            pipeline_lat_ns = calculate_pipeline_latency(self.cfg)

            # Memory-controller congestion delay scaling with concurrent streams
            congestion_delay_ns = calculate_controller_congestion_delay(num_transfers)

            # Round-trip latency overhead per transferred expert block
            cxl_latency_overhead_ns = num_transfers * self.latency_penalty_ns

            # Total elapsed CXLMemSim modeled transfer time
            total_time_ns = (duration_emission_ns +
                             cxl_latency_overhead_ns +
                             bw_penalty_ns +
                             congestion_delay_ns +
                             pipeline_lat_ns)
            cxlmemsim_transfer_time_ms = total_time_ns / 1e6

            # Effective bandwidth achieved across the step
            effective_bw_gbps = (total_cxl_traffic_bytes / 1e9) / (total_time_ns / 1e9) if total_time_ns > 0 else 0.0
        else:
            cxlmemsim_transfer_time_ms = 0.0
            utilization = 0.0
            effective_bw_gbps = self.bandwidth_gbps
            bw_penalty_ns = 0.0
            congestion_delay_ns = 0.0

        return CXLMemSimStepResult(
            step_idx=decision.step_idx,
            layer_idx=decision.layer_idx,
            hits=decision.hits,
            misses=decision.misses,
            hit_rate=decision.hit_rate,
            promotions_count=num_promotions,
            evictions_count=num_evictions,
            unique_demanded_count=num_unique_demanded,
            unique_missing_count=num_unique_missing,
            total_transfers_count=num_transfers,
            demand_cxl_traffic_bytes=demand_cxl_traffic_bytes,
            promotion_traffic_bytes=promotion_traffic_bytes,
            total_cxl_traffic_bytes=total_cxl_traffic_bytes,
            migration_volume_bytes=migration_volume_bytes,
            cxlmemsim_modeled_transfer_time_ms=cxlmemsim_transfer_time_ms,
            analytical_transfer_time_ms=analytical_transfer_time_ms,
            cxlmemsim_link_utilization=utilization,
            cxlmemsim_effective_bw_gbps=effective_bw_gbps,
            cxlmemsim_queue_penalty_ns=bw_penalty_ns,
            cxlmemsim_congestion_delay_ns=congestion_delay_ns,
            solver_time_us=decision.solver_time_us
        )

    def simulate_run(
        self,
        algorithm_name: str,
        decisions: List[PlacementDecision]
    ) -> CXLMemSimSummary:
        """
        Simulates an entire sequence of decisions under CXLMemSim and returns aggregate metrics.
        """
        step_results = [self.simulate_step(d) for d in decisions]

        total_hits = sum(r.hits for r in step_results)
        total_misses = sum(r.misses for r in step_results)
        total_accesses = total_hits + total_misses
        overall_hit_rate = (total_hits / total_accesses) if total_accesses > 0 else 1.0

        total_cxl_bytes = sum(r.total_cxl_traffic_bytes for r in step_results)
        total_demand_bytes = sum(r.demand_cxl_traffic_bytes for r in step_results)
        total_prom_bytes = sum(r.promotion_traffic_bytes for r in step_results)
        total_prom_count = sum(r.promotions_count for r in step_results)
        total_missing_count = sum(r.unique_missing_count for r in step_results)
        total_transfers_count = sum(r.total_transfers_count for r in step_results)

        total_cxlmemsim_time_ms = sum(r.cxlmemsim_modeled_transfer_time_ms for r in step_results)
        total_analytical_time_ms = sum(r.analytical_transfer_time_ms for r in step_results)

        active_steps = [r for r in step_results if r.total_transfers_count > 0]
        avg_link_util = float(np.mean([r.cxlmemsim_link_utilization for r in active_steps])) if active_steps else 0.0
        avg_eff_bw = float(np.mean([r.cxlmemsim_effective_bw_gbps for r in active_steps])) if active_steps else self.bandwidth_gbps

        total_solver_us = sum(r.solver_time_us for r in step_results)

        return CXLMemSimSummary(
            algorithm_name=algorithm_name,
            total_steps=len(step_results),
            total_accesses=total_accesses,
            total_hits=total_hits,
            total_misses=total_misses,
            overall_hit_rate=overall_hit_rate,
            total_cxl_traffic_mb=total_cxl_bytes / (1024 * 1024),
            demand_cxl_traffic_mb=total_demand_bytes / (1024 * 1024),
            promotion_traffic_mb=total_prom_bytes / (1024 * 1024),
            total_promotions_count=total_prom_count,
            total_unique_missing_count=total_missing_count,
            total_transfers_count=total_transfers_count,
            total_cxlmemsim_transfer_time_ms=total_cxlmemsim_time_ms,
            total_analytical_transfer_time_ms=total_analytical_time_ms,
            avg_cxlmemsim_link_utilization=avg_link_util,
            avg_cxlmemsim_effective_bw_gbps=avg_eff_bw,
            total_solver_time_ms=total_solver_us / 1e3,
            avg_solver_time_us=(total_solver_us / len(step_results)) if step_results else 0.0,
            step_results=step_results
        )
