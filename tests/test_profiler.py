"""
Unit tests for MoERouterProfiler and GPUMemoryTracker.
"""

import unittest
import torch
import torch.nn as nn
from src.profiler.router_hook import MoERouterProfiler
from src.profiler.memory_tracker import GPUMemoryTracker


class MockMoELayer(nn.Module):
    def __init__(self, hidden_dim: int = 16, num_experts: int = 16):
        super().__init__()
        self.gate = nn.Linear(hidden_dim, num_experts, bias=False)
        self.experts = nn.ModuleList([nn.Linear(hidden_dim, hidden_dim) for _ in range(num_experts)])

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        logits = self.gate(x)
        return logits


class MockMoEModel(nn.Module):
    def __init__(self, num_layers: int = 2, hidden_dim: int = 16, num_experts: int = 16):
        super().__init__()
        self.layers = nn.ModuleList([MockMoELayer(hidden_dim, num_experts) for _ in range(num_layers)])

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        out = x
        for layer in self.layers:
            out = layer(out)
        return out


class TestMoEProfiler(unittest.TestCase):

    def setUp(self):
        self.num_layers = 2
        self.num_experts = 16
        self.top_k = 4
        self.model = MockMoEModel(num_layers=self.num_layers, hidden_dim=16, num_experts=self.num_experts)

    def test_profiler_attach_and_capture(self):
        profiler = MoERouterProfiler(top_k=self.top_k, router_module_pattern="gate")
        hook_count = profiler.attach(self.model)
        self.assertEqual(hook_count, self.num_layers)
        self.assertTrue(profiler.is_active)

        # Forward pass with batch=2, seq=3, hidden=16
        dummy_input = torch.randn(2, 3, 16)
        _ = self.model(dummy_input)

        # Expect records for both layers
        self.assertEqual(len(profiler.records), self.num_layers)

        for rec in profiler.records:
            self.assertEqual(rec.batch_size, 2)
            self.assertEqual(rec.seq_len, 3)
            # Shape should be [batch=2, seq=3, top_k=4]
            self.assertEqual(len(rec.expert_indices), 2)
            self.assertEqual(len(rec.expert_indices[0]), 3)
            self.assertEqual(len(rec.expert_indices[0][0]), self.top_k)

            # All expert IDs in range [0, 15]
            for b in range(2):
                for s in range(3):
                    for e in rec.expert_indices[b][s]:
                        self.assertGreaterEqual(e, 0)
                        self.assertLess(e, self.num_experts)

        profiler.detach()
        self.assertFalse(profiler.is_active)

    def test_profiler_step_and_clear(self):
        profiler = MoERouterProfiler(top_k=2)
        profiler.attach(self.model)

        dummy_input = torch.randn(1, 1, 16)
        _ = self.model(dummy_input)
        self.assertEqual(len(profiler.records), 2)

        profiler.step()
        _ = self.model(dummy_input)
        self.assertEqual(len(profiler.records), 4)

        profiler.clear()
        self.assertEqual(len(profiler.records), 0)
        profiler.detach()

    def test_memory_tracker_snapshot(self):
        tracker = GPUMemoryTracker()
        snap = tracker.snapshot(base_model_bytes=1000, kv_cache_bytes=500, expert_weights_bytes=2000)
        self.assertGreater(snap.timestamp_ns, 0)
        self.assertEqual(snap.base_model_bytes, 1000)
        self.assertEqual(snap.kv_cache_bytes, 500)
        self.assertEqual(snap.expert_weights_bytes, 2000)


if __name__ == "__main__":
    unittest.main()
