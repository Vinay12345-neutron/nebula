"""
End-to-End High-Performance Benchmark Evaluation Runner.
Executes placement algorithms against trace batches across multiple deterministic seeds,
simulates CXL memory tiering, and produces immutable, self-contained run artifacts.
"""

from dataclasses import dataclass, field, asdict
import hashlib
import json
import os
import platform
import subprocess
import time
from typing import Any, Dict, List, Optional, Type
import numpy as np
import pandas as pd
import torch
import yaml

from ..placement.base import PlacementDecision, PlacementSolver
from ..placement.baselines import (
    HBMOnlySolver,
    NaiveOverflowSolver,
    StaticLFUSolver,
    SingleRequestSolver,
    PredictiveActivationAwareSolver,
    CXLLRUTieringSolver,
)
from ..placement.batch_aware import (
    BatchAwareGreedySolver,
    BatchAwareCoActivationSolver,
)
from ..simulator.cxl_model import CXLMemoryTierSimulator, SimulationSummary
from ..workload.generator import ConcurrentWorkloadGenerator, SyntheticTraceGenerator
from ..workload.trace_schema import BatchRoutingEvent, RoutingTrace


ALGORITHM_MAP: Dict[str, Type[PlacementSolver]] = {
    "baseline_0_hbm_only": HBMOnlySolver,
    "baseline_1_naive_overflow": NaiveOverflowSolver,
    "baseline_2_static_lfu": StaticLFUSolver,
    "baseline_3_single_request": SingleRequestSolver,
    "baseline_4_predictive": PredictiveActivationAwareSolver,
    "baseline_5_cxl_lru": CXLLRUTieringSolver,
    "tiermoe_batch_aware_greedy": BatchAwareGreedySolver,
    "tiermoe_batch_aware_coactivation": BatchAwareCoActivationSolver,
    "nebula_batch_aware_greedy": BatchAwareGreedySolver,
    "nebula_batch_aware_coactivation": BatchAwareCoActivationSolver,
}


@dataclass
class RunConfig:
    """Parsed experiment execution configuration with multi-seed support."""
    experiment_id: str
    experiment_name: str
    num_requests: int
    input_len: int
    output_len: int
    batch_sizes: List[int]
    fast_memory_ratios: List[float]
    algorithms: List[str]
    seeds: List[int] = field(default_factory=lambda: [42, 100, 2026])
    num_experts: int = 128
    top_k: int = 8
    num_layers: int = 32
    expert_size_bytes: int = 268435456  # 256 MB
    cxl_latency_ns: float = 300.0
    cxl_bandwidth_gbps: float = 32.0
    skew_alpha: float = 1.1
    skew_alphas: List[float] = field(default_factory=lambda: [1.1])
    results_dir: str = "results/benchmarks"

    @classmethod
    def from_yaml(cls, yaml_path: str) -> "RunConfig":
        with open(yaml_path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)

        exp = raw.get("experiment", {})
        wl = raw.get("workload", {})
        mem = raw.get("memory", {})
        cxl = raw.get("cxl_simulation", {})
        outputs = raw.get("outputs", {})

        raw_seeds = wl.get("seeds")
        if raw_seeds is None:
            raw_seed = wl.get("seed", 42)
            seeds = [raw_seed] if isinstance(raw_seed, int) else raw_seed
        else:
            seeds = raw_seeds

        raw_skews = wl.get("expert_skew_alphas")
        if raw_skews is not None:
            skew_alphas = [float(s) for s in raw_skews]
            primary_skew = skew_alphas[0]
        else:
            single_skew = float(wl.get("expert_skew_alpha", 1.1))
            skew_alphas = [single_skew]
            primary_skew = single_skew

        return cls(
            experiment_id=exp.get("id", "EXP-UNKNOWN"),
            experiment_name=exp.get("name", "unnamed_run"),
            num_requests=wl.get("num_requests", 32),
            input_len=wl.get("input_len", 64),
            output_len=wl.get("output_len", 64),
            batch_sizes=wl.get("batch_sizes", [1, 4, 8, 16]),
            fast_memory_ratios=mem.get("fast_memory_ratios", [0.25, 0.50, 0.75, 1.00]),
            algorithms=raw.get("algorithms", list(ALGORITHM_MAP.keys())),
            seeds=seeds,
            skew_alpha=primary_skew,
            skew_alphas=skew_alphas,
            cxl_latency_ns=cxl.get("modeled_latency_ns", 300.0),
            cxl_bandwidth_gbps=cxl.get("modeled_bandwidth_gbps", 32.0),
            results_dir=outputs.get("results_dir", "results/benchmarks")
        )


class BenchmarkRunner:
    """
    Orchestrates trace generation, placement evaluation, CXL simulation, and artifact recording.
    """

    def __init__(self, config: RunConfig):
        self.config = config
        self.simulator = CXLMemoryTierSimulator(
            latency_penalty_ns=config.cxl_latency_ns,
            bandwidth_gbps=config.cxl_bandwidth_gbps,
            expert_size_bytes=config.expert_size_bytes
        )

    @staticmethod
    def compute_jaccard_overlap(request_expert_map: Dict[str, List[int]]) -> float:
        req_sets = [set(exps) for exps in request_expert_map.values() if exps]
        n = len(req_sets)
        if n <= 1:
            return 1.0
        total_jaccard = 0.0
        pairs = 0
        for i in range(n):
            for j in range(i + 1, n):
                inter = len(req_sets[i] & req_sets[j])
                union = len(req_sets[i] | req_sets[j])
                total_jaccard += (inter / union) if union > 0 else 0.0
                pairs += 1
        return total_jaccard / pairs if pairs > 0 else 0.0

    @staticmethod
    def compute_expansion_ratio(request_expert_map: Dict[str, List[int]]) -> float:
        req_sets = [set(exps) for exps in request_expert_map.values() if exps]
        if not req_sets:
            return 0.0
        union_size = len(set.union(*req_sets))
        sum_sizes = sum(len(s) for s in req_sets)
        return (union_size / sum_sizes) if sum_sizes > 0 else 1.0

    def run(self, trace_override: Optional[RoutingTrace] = None) -> str:
        """
        Executes the benchmark matrix across all configured seeds and skew levels.
        Returns the path to the run directory.
        """
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        seed_str = "_".join(map(str, self.config.seeds))
        run_hash = hashlib.md5(f"{self.config.experiment_id}_{timestamp}_{seed_str}".encode()).hexdigest()[:8]
        run_dir = os.path.join(self.config.results_dir, f"run_{timestamp}_{run_hash}")
        os.makedirs(run_dir, exist_ok=True)

        self._write_metadata(run_dir)

        all_summaries: List[Dict[str, Any]] = []
        sampled_step_records: List[Dict[str, Any]] = []

        total_conditions_per_seed_skew = len(self.config.batch_sizes) * len(self.config.fast_memory_ratios) * len(self.config.algorithms)
        grand_total = total_conditions_per_seed_skew * len(self.config.seeds) * len(self.config.skew_alphas)
        cond_counter = 0

        print(f"\n  * Executing {grand_total} conditions across {len(self.config.seeds)} seed(s) and {len(self.config.skew_alphas)} skew level(s)")

        for seed in self.config.seeds:
            for skew_alpha in self.config.skew_alphas:
                # Deterministic trace generation for this seed and skew
                if trace_override is not None:
                    trace = trace_override
                else:
                    synth = SyntheticTraceGenerator(
                        num_experts=self.config.num_experts,
                        top_k=self.config.top_k,
                        num_layers=self.config.num_layers,
                        seed=seed
                    )
                    trace = synth.generate_trace(
                        num_requests=self.config.num_requests,
                        seq_len=self.config.input_len + self.config.output_len,
                        skew_alpha=skew_alpha
                    )

                workload_gen = ConcurrentWorkloadGenerator(trace)

                for batch_size in self.config.batch_sizes:
                    t_b0 = time.time()
                    batch_events = list(workload_gen.generate_batches(batch_size=batch_size))

                    # Calculate online overlap telemetry on representative sample
                    sample_events = batch_events[:min(len(batch_events), 500)]
                    jaccard_scores = [self.compute_jaccard_overlap(be.request_expert_map) for be in sample_events]
                    avg_jaccard = float(np.mean(jaccard_scores)) if jaccard_scores else 1.0
                    avg_divergence = 1.0 - avg_jaccard
                    expansion_scores = [self.compute_expansion_ratio(be.request_expert_map) for be in sample_events]
                    avg_expansion = float(np.mean(expansion_scores)) if expansion_scores else 0.0

                    # Calculate average unique demanded working set for this batch size
                    avg_working_set = float(np.mean([len(be.expert_frequency) for be in batch_events])) if batch_events else 0.0

                    for ratio in self.config.fast_memory_ratios:
                        fast_cap = max(1, int(self.config.num_experts * ratio))
                        pressure_ratio = avg_working_set / fast_cap if fast_cap > 0 else 0.0

                        if pressure_ratio <= 1.0:
                            regime = "no-pressure"
                        elif pressure_ratio < 1.5:
                            regime = "capacity-pressure"
                        else:
                            regime = "severe-pressure"

                        for algo_key in self.config.algorithms:
                            if algo_key not in ALGORITHM_MAP:
                                continue

                            solver_cls = ALGORITHM_MAP[algo_key]
                            solver = solver_cls(num_experts=self.config.num_experts)
                            solver.reset()

                            current_fast_tier: Optional[set] = None
                            decisions: List[PlacementDecision] = []

                            for b_ev in batch_events:
                                dec = solver.solve(
                                    batch_event=b_ev,
                                    fast_capacity=fast_cap,
                                    current_fast_tier=current_fast_tier
                                )
                                decisions.append(dec)
                                current_fast_tier = dec.fast_resident_experts

                            summary = self.simulator.simulate_run(
                                algorithm_name=solver.name,
                                decisions=decisions
                            )

                            summary_dict = summary.to_dict()
                            summary_dict.update({
                                "seed": seed,
                                "skew_alpha": skew_alpha,
                                "batch_size": batch_size,
                                "fast_memory_ratio": ratio,
                                "fast_capacity_experts": fast_cap,
                                "avg_working_set_experts": avg_working_set,
                                "capacity_pressure_ratio": pressure_ratio,
                                "pressure_regime": regime,
                                "is_capacity_constrained": bool(avg_working_set > fast_cap),
                                "avg_jaccard_overlap": avg_jaccard,
                                "avg_request_divergence": avg_divergence,
                                "avg_expansion_ratio": avg_expansion,
                                "total_experts": self.config.num_experts,
                            })
                            all_summaries.append(summary_dict)

                            # Sample first 3 steps
                            for sr in summary.step_results[:3]:
                                rec = asdict(sr)
                                rec.update({
                                    "seed": seed,
                                    "algorithm": solver.name,
                                    "batch_size": batch_size,
                                    "fast_memory_ratio": ratio
                                })
                                sampled_step_records.append(rec)

                            cond_counter += 1

                    dt_b = time.time() - t_b0
                    print(f"    [Seed {seed} | α={skew_alpha:.1f} | B={batch_size:2d}] Processed in {dt_b:.2f}s ({cond_counter}/{grand_total} conditions complete)")

        # Save summary datasets
        summary_df = pd.DataFrame(all_summaries)
        summary_df.to_parquet(os.path.join(run_dir, "summary_metrics.parquet"), index=False)
        summary_df.to_json(os.path.join(run_dir, "summary_metrics.json"), orient="records", indent=2)

        steps_df = pd.DataFrame(sampled_step_records)
        steps_df.to_parquet(os.path.join(run_dir, "raw_steps.parquet"), index=False)

        return run_dir

    def _write_metadata(self, run_dir: str) -> None:
        with open(os.path.join(run_dir, "config.yaml"), "w", encoding="utf-8") as f:
            yaml.dump(asdict(self.config), f, default_flow_style=False)

        with open(os.path.join(run_dir, "seed.txt"), "w", encoding="utf-8") as f:
            f.write(f"seeds: {self.config.seeds}\nexecution_type: deterministic_multi_seed_replay\n")

        git_hash = "unknown"
        try:
            git_hash = subprocess.check_output(["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL).decode().strip()
        except Exception:
            pass

        meta = {
            "experiment_id": self.config.experiment_id,
            "experiment_name": self.config.experiment_name,
            "git_commit": git_hash,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "platform": platform.platform(),
            "python_version": platform.python_version(),
            "pytorch_version": torch.__version__,
            "cuda_available": torch.cuda.is_available(),
            "cuda_device_count": torch.cuda.device_count() if torch.cuda.is_available() else 0,
        }
        with open(os.path.join(run_dir, "meta.json"), "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)
