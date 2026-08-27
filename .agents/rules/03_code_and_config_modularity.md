# Rule 03: Code & Config Modularity

1. **Declarative Configurations**: All experiments must be configured using declarative YAML files in `configs/`.
2. **Zero Hardcoded Parameters**: Model architectures, expert counts, top-$k$ routing values, batch sizes, sequence lengths, memory budgets, and CXL specs must never be hardcoded in execution scripts.
3. **Directory Separation**:
   - `configs/`: Experiment configuration definitions.
   - `experiments/`: Standalone runner scripts.
   - `results/`: Immutable raw execution outputs and metadata.
   - `analysis/`: Post-processing, aggregation, and statistical scripts.
   - `figures/`: Rendered publication-ready plots.
   - `papers/`: Literature review notes and references.
   - `docs/`: Technical notes and documentation.
