# Project TierMoE: Research Workspace Guidelines

This repository hosts research for **TierMoE**: *Batch-Aware Expert Placement for Memory-Tiered MoE Inference*.

All AI agents and collaborators operating within this workspace must adhere to the following governance rules:

1. **[01_scientific_integrity.md](.agents/rules/01_scientific_integrity.md)**: "Do not optimize what we have not measured." Isolate solver and migration overheads; report statistical uncertainty for stochastic runs.
2. **[02_simulation_transparency.md](.agents/rules/02_simulation_transparency.md)**: Clearly delineate physical RTX A6000 GPU measurements from simulated CXL metrics.
3. **[03_code_and_config_modularity.md](.agents/rules/03_code_and_config_modularity.md)**: Keep all experimental parameters in declarative YAML configs under `configs/`.
4. **[04_reproducibility_contract.md](.agents/rules/04_reproducibility_contract.md)**: Every experiment run must capture git commit hash, seed (if applicable), environment specs, and raw metrics.

The authoritative research specification is documented in `README.md`.
