# Rule 04: Reproducibility Contract

1. **Self-Contained Run Artifacts**: Every experiment execution must write to an isolated directory:
   `results/<experiment_name>/run_<timestamp>_<hash>/`
2. **Required Metadata**: Each run directory must contain:
   - `config.yaml`: Exact snapshot of the experiment configuration used.
   - `meta.json`: Git commit hash, timestamp, platform/OS info, PyTorch & CUDA versions.
   - `seed.txt` (or rationale for single deterministic run).
   - `raw_metrics.jsonl` or `raw_metrics.parquet`: Unmodified execution and simulation traces.
3. **Zero In-Place Overwrites**: Existing result directories are immutable records and must never be overwritten.
