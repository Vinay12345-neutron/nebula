---
description: Analyze completed experiments, generate statistics and figures, and update research findings.
---

# Workflow: Analyze Experiment

Step-by-step workflow for processing raw experimental results and evaluating hypotheses.

1. **Validate Run Completeness:**
   - Confirm all runs in `results/<experiment_name>/` completed successfully.
   - Verify presence of `meta.json`, `config.yaml`, and raw metric files.
2. **Execute Analysis:**
   - Run aggregation scripts against the result data.
3. **Generate Visualizations:**
   - Output plots to `figures/<experiment_name>/`.
4. **Update Current State & Log:**
   - Update `CURRENT_STATE.md` under "Empirical Evidence" with findings.
   - Record an entry in `RESEARCH_LOG.md`.
