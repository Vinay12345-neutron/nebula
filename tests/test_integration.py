"""
Integration tests for the end-to-end evaluation runner.
"""

import os
import shutil
import tempfile
import unittest
import pandas as pd
from src.evaluation.runner import BenchmarkRunner, RunConfig


class TestIntegrationPipeline(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.config = RunConfig(
            experiment_id="TEST-EXP-01",
            experiment_name="integration_test_run",
            num_requests=4,
            input_len=4,
            output_len=4,
            batch_sizes=[1, 2],
            fast_memory_ratios=[0.5, 1.0],
            algorithms=[
                "baseline_0_hbm_only",
                "baseline_1_naive_overflow",
                "baseline_2_static_lfu",
                "tiermoe_batch_aware_greedy"
            ],
            seeds=[999],
            num_experts=16,
            top_k=4,
            num_layers=2,
            expert_size_bytes=1024 * 1024,  # 1 MB for testing
            results_dir=os.path.join(self.temp_dir, "results")
        )

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_end_to_end_benchmark_run(self):
        runner = BenchmarkRunner(self.config)
        run_dir = runner.run()

        self.assertTrue(os.path.exists(run_dir))

        # Check required reproducibility metadata (Rule 04)
        self.assertTrue(os.path.exists(os.path.join(run_dir, "config.yaml")))
        self.assertTrue(os.path.exists(os.path.join(run_dir, "meta.json")))
        self.assertTrue(os.path.exists(os.path.join(run_dir, "seed.txt")))

        # Check result artifacts
        summary_parquet = os.path.join(run_dir, "summary_metrics.parquet")
        summary_json = os.path.join(run_dir, "summary_metrics.json")
        raw_steps_parquet = os.path.join(run_dir, "raw_steps.parquet")

        self.assertTrue(os.path.exists(summary_parquet))
        self.assertTrue(os.path.exists(summary_json))
        self.assertTrue(os.path.exists(raw_steps_parquet))

        # Verify summary content
        df = pd.read_parquet(summary_parquet)
        self.assertGreater(len(df), 0)

        # 1 seed * 2 batch sizes * 2 memory ratios * 4 algorithms = 16 summary rows
        self.assertEqual(len(df), 16)

        # Check that hit rates are bounded in [0, 1]
        for hr in df["overall_hit_rate"]:
            self.assertGreaterEqual(hr, 0.0)
            self.assertLessEqual(hr, 1.0)


if __name__ == "__main__":
    unittest.main()
