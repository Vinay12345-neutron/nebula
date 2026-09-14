"""
Unit and Integration Tests for TierMoE Interactive Demonstration Loader.
Validates that all experimental data across EXP-01 to EXP-05B load accurately
with strict adherence to verified repository results and schemas.
"""

import unittest
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from demo.data_loader import (
    get_project_facts,
    get_rq_verdicts,
    load_exp01,
    load_exp02,
    load_exp03,
    load_exp04,
    load_exp05a,
    load_exp05b,
    lookup_what_if,
)


class TestTierMoEDemo(unittest.TestCase):
    """Test suite for TierMoE demonstration data loader and query engine."""

    def test_project_facts(self):
        facts = get_project_facts()
        self.assertEqual(facts["model"], "Qwen3-30B-A3B-Instruct-2507")
        self.assertEqual(facts["total_experts"], 128)
        self.assertEqual(facts["active_experts_per_token"], 8)
        self.assertEqual(facts["total_expert_footprint_tib"], "1.50 TiB")
        self.assertEqual(facts["authentic_routing_events"], 461184)

    def test_rq_verdicts(self):
        verdicts = get_rq_verdicts()
        self.assertEqual(len(verdicts), 6)
        statuses = [v["status"] for v in verdicts]
        self.assertIn("SUPPORTED (UNDER PRESSURE)", statuses[0])
        self.assertIn("PARTIALLY SUPPORTED", statuses[1])
        self.assertIn("NOT SUPPORTED", statuses[2])
        self.assertIn("SUPPORTED (IMPLEMENTED BASELINES)", statuses[3])
        self.assertIn("SUPPORTED (MODELED SENSITIVITY)", statuses[4])
        self.assertIn("SUPPORTED (TESTED CONFIGURATION)", statuses[5])

    def test_exp01_loading(self):
        df, analysis = load_exp01()
        self.assertFalse(df.empty)
        self.assertIn("TierMoE-Batch-Aware-Greedy", df["algorithm"].unique())
        self.assertIn("Baseline-3-Single-Request", df["algorithm"].unique())
        self.assertIn("batch_size", df.columns)
        self.assertIn("overall_hit_rate", df.columns)
        self.assertEqual(analysis["h1_status"], "SUPPORTED")

    def test_exp02_loading(self):
        df, analysis = load_exp02()
        self.assertFalse(df.empty)
        self.assertIn("skew_alpha", df.columns)
        self.assertIn("avg_request_divergence", df.columns)
        self.assertIn("avg_jaccard_overlap", df.columns)
        self.assertEqual(analysis["h2_status"], "PARTIALLY SUPPORTED")

    def test_exp03_loading(self):
        df, analysis = load_exp03()
        self.assertFalse(df.empty)
        self.assertIn("sharegpt", df["dataset"].unique())
        self.assertIn("gsm8k", df["dataset"].unique())
        self.assertEqual(analysis["h3_status"], "NOT SUPPORTED")

    def test_exp04_loading(self):
        df, analysis = load_exp04()
        self.assertFalse(df.empty)
        algos = df["algorithm"].unique()
        self.assertIn("Baseline-4-Predictive-Activation-Aware", algos)
        self.assertIn("Baseline-5-CXL-LRU-Tiering", algos)
        self.assertIn("TierMoE-Batch-Aware-Greedy", algos)

    def test_exp05a_loading(self):
        df, analysis = load_exp05a()
        self.assertEqual(len(df), 81)
        self.assertTrue(analysis["invariance_verified"])
        self.assertAlmostEqual(analysis["bw_scaling_factor"], 4.0, places=1)

    def test_exp05b_loading(self):
        df, analysis, microbench = load_exp05b()
        self.assertFalse(df.empty)
        self.assertIn("stream_scaling", microbench)
        self.assertIn("batch_activation", microbench)
        scaling = microbench["stream_scaling"]
        self.assertEqual(scaling["calibrated_C"], 5719.0)
        self.assertAlmostEqual(scaling["calibrated_T0_us"], 11.438, places=2)

    def test_what_if_query(self):
        # Valid evaluated condition
        res = lookup_what_if(
            workload="sharegpt",
            batch_size=16,
            capacity_ratio=0.25,
            policy="TierMoE-Batch-Aware-Greedy",
            bandwidth_gbps=32.0,
        )
        self.assertTrue(res["evaluated"])
        self.assertAlmostEqual(res["hit_rate_pct"], 83.085, places=1)

        # Unevaluated condition should return evaluated=False gracefully
        res_none = lookup_what_if(
            workload="synthetic",
            batch_size=100,  # Never evaluated
            capacity_ratio=0.33,
            policy="UnknownPolicy",
            bandwidth_gbps=999.0,
        )
        self.assertFalse(res_none["evaluated"])
        self.assertIn("not directly evaluated", res_none["message"])

    def test_plotly_format(self):
        try:
            import plotly.express as px
            from demo.app import format_plot
            fig = px.line(x=[1, 2, 3], y=[4, 5, 6], title="Test Plot")
            formatted = format_plot(fig)
            self.assertIsNotNone(formatted)
        except ImportError:
            pass


if __name__ == "__main__":
    unittest.main()
