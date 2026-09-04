"""
Unit tests for trace schema, serialization, and workload generator.
"""

import os
import shutil
import tempfile
import unittest
from src.workload.generator import ConcurrentWorkloadGenerator, SyntheticTraceGenerator
from src.workload.trace_schema import BatchRoutingEvent, RoutingTrace, TokenRoutingEvent


class TestWorkloadFramework(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.generator = SyntheticTraceGenerator(
            num_experts=32,
            top_k=4,
            num_layers=2,
            seed=123
        )

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_synthetic_trace_generation(self):
        trace = self.generator.generate_trace(
            num_requests=4,
            seq_len=8,
            skew_alpha=1.2
        )
        self.assertEqual(trace.num_experts, 32)
        self.assertEqual(trace.top_k, 4)
        self.assertEqual(trace.num_layers, 2)
        # Total events = num_requests * seq_len * num_layers = 4 * 8 * 2 = 64
        self.assertEqual(len(trace.events), 64)

        for ev in trace.events:
            self.assertEqual(len(ev.expert_indices), 4)
            for e in ev.expert_indices:
                self.assertGreaterEqual(e, 0)
                self.assertLess(e, 32)

    def test_jsonl_serialization(self):
        trace = self.generator.generate_trace(num_requests=2, seq_len=4)
        jsonl_path = os.path.join(self.temp_dir, "test_trace.jsonl")
        trace.save_jsonl(jsonl_path)
        self.assertTrue(os.path.exists(jsonl_path))

        loaded = RoutingTrace.load_jsonl(jsonl_path)
        self.assertEqual(loaded.num_experts, trace.num_experts)
        self.assertEqual(loaded.top_k, trace.top_k)
        self.assertEqual(len(loaded.events), len(trace.events))
        self.assertEqual(loaded.events[0].expert_indices, trace.events[0].expert_indices)

    def test_parquet_serialization(self):
        trace = self.generator.generate_trace(num_requests=2, seq_len=4)
        parquet_path = os.path.join(self.temp_dir, "test_trace.parquet")
        trace.save_parquet(parquet_path)
        self.assertTrue(os.path.exists(parquet_path))

        loaded = RoutingTrace.load_parquet(parquet_path)
        self.assertEqual(loaded.num_experts, trace.num_experts)
        self.assertEqual(len(loaded.events), len(trace.events))
        self.assertEqual(loaded.events[0].expert_indices, trace.events[0].expert_indices)

    def test_concurrent_batch_generator(self):
        trace = self.generator.generate_trace(num_requests=6, seq_len=4)
        workload = ConcurrentWorkloadGenerator(trace)
        self.assertEqual(workload.total_requests, 6)

        # Slicing with batch_size=2 should produce 3 batch slices * 4 steps * 2 layers = 24 batch events
        batch_events = list(workload.generate_batches(batch_size=2))
        self.assertEqual(len(batch_events), 24)

        first_batch = batch_events[0]
        self.assertIsInstance(first_batch, BatchRoutingEvent)
        self.assertEqual(len(first_batch.request_ids), 2)
        # Total frequency sum = 2 requests * top_k=4 = 8
        self.assertEqual(sum(first_batch.expert_frequency.values()), 8)


if __name__ == "__main__":
    unittest.main()
