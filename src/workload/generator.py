"""
Synthetic and Trace-Driven Concurrent Workload Generator.
Constructs multi-tenant request streams with controlled batch size, sequence lengths,
expert popularity skew (Zipfian), and request divergence.
"""

from typing import Dict, Generator, List, Optional, Tuple
import numpy as np
from .trace_schema import BatchRoutingEvent, RoutingTrace, TokenRoutingEvent


class SyntheticTraceGenerator:
    """
    Generates synthetic MoE routing traces with controlled statistical properties:
    - Zipfian expert popularity skew (alpha)
    - Co-activation cluster correlation
    - Request overlap and divergence
    """

    def __init__(
        self,
        num_experts: int = 128,
        top_k: int = 8,
        num_layers: int = 32,
        seed: int = 42
    ):
        self.num_experts = num_experts
        self.top_k = top_k
        self.num_layers = num_layers
        self.seed = seed
        self._rng = np.random.default_rng(seed)

    def generate_trace(
        self,
        num_requests: int = 64,
        seq_len: int = 128,
        skew_alpha: float = 1.1,
        coactivation_clusters: int = 8,
        model_name: str = "synthetic-moe-128"
    ) -> RoutingTrace:
        """
        Generates a complete multi-request routing trace.
        """
        # Create Zipfian probabilities over experts
        ranks = np.arange(1, self.num_experts + 1)
        weights = 1.0 / (ranks ** skew_alpha)
        base_probs = weights / weights.sum()

        # Build co-activation cluster map
        cluster_size = self.num_experts // coactivation_clusters
        clusters = [
            list(range(i * cluster_size, min((i + 1) * cluster_size, self.num_experts)))
            for i in range(coactivation_clusters)
        ]

        events: List[TokenRoutingEvent] = []

        for req_idx in range(num_requests):
            req_id = f"req_{req_idx:04d}"
            # Assign preferred cluster to induce request-level domain correlation
            pref_cluster_idx = self._rng.choice(len(clusters))
            pref_cluster = clusters[pref_cluster_idx]

            req_probs = base_probs.copy()
            # Boost preferred cluster probability
            req_probs[pref_cluster] *= 3.0
            req_probs /= req_probs.sum()

            for step in range(seq_len):
                for layer in range(self.num_layers):
                    # Sample top_k unique experts without replacement
                    selected_experts = self._rng.choice(
                        self.num_experts,
                        size=self.top_k,
                        replace=False,
                        p=req_probs
                    ).tolist()

                    # Synthetic normalized routing weights (Dirichlet)
                    raw_weights = self._rng.dirichlet(np.ones(self.top_k)).tolist()

                    event = TokenRoutingEvent(
                        request_id=req_id,
                        step_idx=step,
                        layer_idx=layer,
                        token_idx=step,
                        expert_indices=selected_experts,
                        routing_weights=raw_weights
                    )
                    events.append(event)

        return RoutingTrace(
            model_name=model_name,
            num_experts=self.num_experts,
            top_k=self.top_k,
            num_layers=self.num_layers,
            events=events,
            metadata={
                "num_requests": num_requests,
                "seq_len": seq_len,
                "skew_alpha": skew_alpha,
                "seed": self.seed
            }
        )


class ConcurrentWorkloadGenerator:
    """
    Groups token routing events into concurrent batches of size B.
    Yields sequential BatchRoutingEvent instances across decoding steps and layers.
    """

    def __init__(self, trace: RoutingTrace):
        self.trace = trace
        # Index events by (request_id, step_idx, layer_idx)
        self._index: Dict[Tuple[str, int, int], TokenRoutingEvent] = {}
        self._request_ids: List[str] = []
        self._max_step = 0
        self._num_layers = trace.num_layers

        self._build_index()

    def _build_index(self) -> None:
        seen_reqs = set()
        for ev in self.trace.events:
            self._index[(ev.request_id, ev.step_idx, ev.layer_idx)] = ev
            if ev.request_id not in seen_reqs:
                seen_reqs.add(ev.request_id)
                self._request_ids.append(ev.request_id)
            if ev.step_idx > self._max_step:
                self._max_step = ev.step_idx

    @property
    def total_requests(self) -> int:
        return len(self._request_ids)

    def generate_batches(
        self,
        batch_size: int,
        max_steps: Optional[int] = None
    ) -> Generator[BatchRoutingEvent, None, None]:
        """
        Yields batch routing events for each (step, layer) tuple across concurrent request slices.
        """
        num_batches = (len(self._request_ids) + batch_size - 1) // batch_size
        steps_limit = min(self._max_step + 1, max_steps) if max_steps else self._max_step + 1

        for b_idx in range(num_batches):
            batch_reqs = self._request_ids[b_idx * batch_size : (b_idx + 1) * batch_size]
            batch_id = f"batch_{b_idx:03d}"

            for step in range(steps_limit):
                for layer in range(self._num_layers):
                    step_events: List[TokenRoutingEvent] = []
                    for req_id in batch_reqs:
                        key = (req_id, step, layer)
                        if key in self._index:
                            step_events.append(self._index[key])

                    if step_events:
                        yield BatchRoutingEvent.from_events(
                            batch_id=batch_id,
                            step_idx=step,
                            layer_idx=layer,
                            events=step_events
                        )
