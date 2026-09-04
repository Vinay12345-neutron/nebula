"""
PyTorch Forward Hook Profiler for MoE Router Gating Layers.
Captures per-layer, per-token expert activation decisions and routing weights.
"""

from dataclasses import dataclass, field
import time
from typing import Any, Dict, List, Optional, Tuple
import torch
import torch.nn as nn


@dataclass
class RoutingRecord:
    """A record of expert routing decisions for a single forward step."""
    layer_idx: int
    step_idx: int
    timestamp_ns: int
    batch_size: int
    seq_len: int
    expert_indices: List[List[List[int]]]  # [batch, seq, top_k]
    routing_weights: Optional[List[List[List[float]]]] = None  # [batch, seq, top_k]


class MoERouterProfiler:
    """
    Non-intrusive forward hook profiler for MoE router gating layers.
    Attaches read-only PyTorch forward hooks to extract active expert IDs
    during standard inference without altering model outputs.
    """

    def __init__(
        self,
        top_k: int = 8,
        record_weights: bool = True,
        router_module_pattern: str = "gate"
    ):
        self.top_k = top_k
        self.record_weights = record_weights
        self.router_module_pattern = router_module_pattern
        self._hooks: List[Any] = []
        self._records: List[RoutingRecord] = []
        self._step_counter = 0
        self._is_active = False

    @property
    def is_active(self) -> bool:
        return self._is_active

    @property
    def records(self) -> List[RoutingRecord]:
        return self._records

    def clear(self) -> None:
        """Clear all stored routing records."""
        self._records.clear()
        self._step_counter = 0

    def attach(self, model: nn.Module) -> int:
        """
        Attaches forward hooks to all router gating modules matching pattern.
        Returns the count of attached hooks.
        """
        self.detach()
        hook_count = 0
        layer_idx = 0

        for name, module in model.named_modules():
            if self._is_router_module(name, module):
                hook = module.register_forward_hook(
                    self._create_hook_fn(layer_idx=layer_idx, module_name=name)
                )
                self._hooks.append(hook)
                hook_count += 1
                layer_idx += 1

        self._is_active = hook_count > 0
        return hook_count

    def detach(self) -> None:
        """Removes all registered PyTorch forward hooks."""
        for hook in self._hooks:
            hook.remove()
        self._hooks.clear()
        self._is_active = False

    def step(self) -> None:
        """Advances the step counter (e.g. for autoregressive decoding steps)."""
        self._step_counter += 1

    def _is_router_module(self, name: str, module: nn.Module) -> bool:
        """Checks if a module corresponds to an MoE router gate."""
        if not isinstance(module, (nn.Linear, nn.Module)):
            return False
        # Explicitly exclude internal expert projections like gate_proj or gate_up_proj
        lower_name = name.lower()
        if "gate_proj" in lower_name or "gate_up_proj" in lower_name:
            return False
        parts = lower_name.split(".")
        return (self.router_module_pattern.lower() in lower_name) or (parts[-1] == "gate")

    def _create_hook_fn(self, layer_idx: int, module_name: str):
        """Generates the hook closure for a specific layer."""
        def hook_fn(module: nn.Module, inputs: Any, output: Any):
            if not self._is_active:
                return

            # Extract router logits from module output or input
            logits = output
            if isinstance(output, (tuple, list)):
                logits = output[0]

            if not isinstance(logits, torch.Tensor):
                return

            with torch.no_grad():
                # Shape is typically [batch_size, seq_len, num_experts]
                # or [total_tokens, num_experts]
                shape = logits.shape
                if len(shape) == 2:
                    batch_size = shape[0]
                    seq_len = 1
                    reshaped = logits.unsqueeze(1)
                elif len(shape) >= 3:
                    batch_size = shape[0]
                    seq_len = shape[1]
                    reshaped = logits
                else:
                    return

                k = min(self.top_k, reshaped.shape[-1])
                topk_weights, topk_indices = torch.topk(reshaped, k=k, dim=-1)

                indices_list = topk_indices.detach().cpu().tolist()
                weights_list = topk_weights.detach().cpu().tolist() if self.record_weights else None

                record = RoutingRecord(
                    layer_idx=layer_idx,
                    step_idx=self._step_counter,
                    timestamp_ns=time.time_ns(),
                    batch_size=batch_size,
                    seq_len=seq_len,
                    expert_indices=indices_list,
                    routing_weights=weights_list
                )
                self._records.append(record)

        return hook_fn

    def __enter__(self):
        self._is_active = True
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.detach()
