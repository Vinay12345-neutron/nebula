"""
GPU Memory Tracker for MoE Inference.
Monitors CUDA memory allocations, base model parameters, KV cache, and expert footprint.
"""

from dataclasses import dataclass
from typing import Dict, Optional
import torch


@dataclass
class MemorySnapshot:
    """Snapshot of GPU memory state in bytes."""
    timestamp_ns: int
    allocated_bytes: int
    reserved_bytes: int
    max_allocated_bytes: int
    base_model_bytes: int = 0
    kv_cache_bytes: int = 0
    expert_weights_bytes: int = 0

    @property
    def allocated_mb(self) -> float:
        return self.allocated_bytes / (1024 * 1024)

    @property
    def reserved_mb(self) -> float:
        return self.reserved_bytes / (1024 * 1024)

    @property
    def max_allocated_mb(self) -> float:
        return self.max_allocated_bytes / (1024 * 1024)


class GPUMemoryTracker:
    """
    Tracks and breaks down GPU memory usage during MoE inference runs.
    """

    def __init__(self, device: Optional[torch.device] = None):
        self.device = device or (torch.device("cuda:0") if torch.cuda.is_available() else torch.device("cpu"))
        self._initial_snapshot: Optional[MemorySnapshot] = None

    def is_cuda(self) -> bool:
        return self.device.type == "cuda" and torch.cuda.is_available()

    def snapshot(
        self,
        base_model_bytes: int = 0,
        kv_cache_bytes: int = 0,
        expert_weights_bytes: int = 0
    ) -> MemorySnapshot:
        """Captures a current memory state snapshot."""
        import time
        if self.is_cuda():
            allocated = torch.cuda.memory_allocated(self.device)
            reserved = torch.cuda.memory_reserved(self.device)
            max_alloc = torch.cuda.max_memory_allocated(self.device)
        else:
            allocated = 0
            reserved = 0
            max_alloc = 0

        snap = MemorySnapshot(
            timestamp_ns=time.time_ns(),
            allocated_bytes=allocated,
            reserved_bytes=reserved,
            max_allocated_bytes=max_alloc,
            base_model_bytes=base_model_bytes,
            kv_cache_bytes=kv_cache_bytes,
            expert_weights_bytes=expert_weights_bytes
        )

        if self._initial_snapshot is None:
            self._initial_snapshot = snap

        return snap

    def reset_peak(self) -> None:
        """Resets peak memory statistics on the tracked device."""
        if self.is_cuda():
            torch.cuda.reset_peak_memory_stats(self.device)
