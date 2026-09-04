"""
Standardized MoE Routing Trace Schema.
Defines structured serialization for token and batch expert activation events.
"""

from dataclasses import dataclass, field, asdict
import json
import os
from typing import Any, Dict, List, Optional
import pandas as pd


@dataclass
class TokenRoutingEvent:
    """Routing decision for a single token in a specific layer."""
    request_id: str
    step_idx: int
    layer_idx: int
    token_idx: int
    expert_indices: List[int]
    routing_weights: Optional[List[float]] = None


@dataclass
class BatchRoutingEvent:
    """Aggregated expert routing demand across a concurrent batch at a specific step and layer."""
    batch_id: str
    step_idx: int
    layer_idx: int
    request_ids: List[str]
    # Mapping expert_id -> aggregate access frequency in this batch step
    expert_frequency: Dict[int, int] = field(default_factory=dict)
    # Per-request active expert sets: request_id -> list of expert IDs
    request_expert_map: Dict[str, List[int]] = field(default_factory=dict)

    @classmethod
    def from_events(
        cls,
        batch_id: str,
        step_idx: int,
        layer_idx: int,
        events: List[TokenRoutingEvent]
    ) -> "BatchRoutingEvent":
        freq: Dict[int, int] = {}
        req_map: Dict[str, List[int]] = {}
        req_ids = []

        for ev in events:
            if ev.request_id not in req_map:
                req_map[ev.request_id] = []
                req_ids.append(ev.request_id)
            for exp_id in ev.expert_indices:
                freq[exp_id] = freq.get(exp_id, 0) + 1
                req_map[ev.request_id].append(exp_id)

        return cls(
            batch_id=batch_id,
            step_idx=step_idx,
            layer_idx=layer_idx,
            request_ids=req_ids,
            expert_frequency=freq,
            request_expert_map=req_map
        )


@dataclass
class RoutingTrace:
    """Collection of routing events with dataset and model metadata."""
    model_name: str
    num_experts: int
    top_k: int
    num_layers: int
    events: List[TokenRoutingEvent] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_event(self, event: TokenRoutingEvent) -> None:
        self.events.append(event)

    def to_dataframe(self) -> pd.DataFrame:
        records = [
            {
                "request_id": e.request_id,
                "step_idx": e.step_idx,
                "layer_idx": e.layer_idx,
                "token_idx": e.token_idx,
                "expert_indices": json.dumps(e.expert_indices),
                "routing_weights": json.dumps(e.routing_weights) if e.routing_weights else None
            }
            for e in self.events
        ]
        return pd.DataFrame(records)

    @classmethod
    def from_dataframe(
        cls,
        df: pd.DataFrame,
        model_name: str,
        num_experts: int,
        top_k: int,
        num_layers: int,
        metadata: Optional[Dict[str, Any]] = None
    ) -> "RoutingTrace":
        events = []
        for _, row in df.iterrows():
            expert_indices = (
                json.loads(row["expert_indices"])
                if isinstance(row["expert_indices"], str)
                else list(row["expert_indices"])
            )
            weights = None
            if pd.notna(row.get("routing_weights")) and row.get("routing_weights"):
                weights = (
                    json.loads(row["routing_weights"])
                    if isinstance(row["routing_weights"], str)
                    else list(row["routing_weights"])
                )

            events.append(
                TokenRoutingEvent(
                    request_id=str(row["request_id"]),
                    step_idx=int(row["step_idx"]),
                    layer_idx=int(row["layer_idx"]),
                    token_idx=int(row["token_idx"]),
                    expert_indices=expert_indices,
                    routing_weights=weights
                )
            )

        return cls(
            model_name=model_name,
            num_experts=num_experts,
            top_k=top_k,
            num_layers=num_layers,
            events=events,
            metadata=metadata or {}
        )

    def save_jsonl(self, file_path: str) -> None:
        os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            # First line: metadata header
            header = {
                "__metadata__": True,
                "model_name": self.model_name,
                "num_experts": self.num_experts,
                "top_k": self.top_k,
                "num_layers": self.num_layers,
                "metadata": self.metadata
            }
            f.write(json.dumps(header) + "\n")
            for ev in self.events:
                f.write(json.dumps(asdict(ev)) + "\n")

    @classmethod
    def load_jsonl(cls, file_path: str) -> "RoutingTrace":
        events = []
        header_meta: Dict[str, Any] = {}
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                data = json.loads(line.strip())
                if data.get("__metadata__"):
                    header_meta = data
                else:
                    events.append(TokenRoutingEvent(**data))

        return cls(
            model_name=header_meta.get("model_name", "unknown"),
            num_experts=header_meta.get("num_experts", 128),
            top_k=header_meta.get("top_k", 8),
            num_layers=header_meta.get("num_layers", 1),
            events=events,
            metadata=header_meta.get("metadata", {})
        )

    def save_parquet(self, file_path: str) -> None:
        os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
        df = self.to_dataframe()
        df.to_parquet(file_path, index=False)
        # Save sidecar metadata JSON
        meta_path = file_path.rsplit(".", 1)[0] + "_metadata.json"
        meta_dict = {
            "model_name": self.model_name,
            "num_experts": self.num_experts,
            "top_k": self.top_k,
            "num_layers": self.num_layers,
            "total_events": len(self.events),
            "metadata": self.metadata
        }
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta_dict, f, indent=2)

    @classmethod
    def load_parquet(cls, file_path: str) -> "RoutingTrace":
        df = pd.read_parquet(file_path)
        meta_path = file_path.rsplit(".", 1)[0] + "_metadata.json"
        meta_dict = {}
        if os.path.exists(meta_path):
            with open(meta_path, "r", encoding="utf-8") as f:
                meta_dict = json.load(f)

        return cls.from_dataframe(
            df=df,
            model_name=meta_dict.get("model_name", "unknown"),
            num_experts=meta_dict.get("num_experts", 128),
            top_k=meta_dict.get("top_k", 8),
            num_layers=meta_dict.get("num_layers", 1),
            metadata=meta_dict.get("metadata", {})
        )
