---
description: Design reproducible experiments linked to Nebula research questions and hypotheses.
---

# Workflow: Plan Experiment

Step-by-step workflow for designing a validated, reproducible Nebula-MoE experiment.

1. **Review Research State:**
   - Read `CURRENT_STATE.md` to identify the next priority Research Question and Hypothesis.
2. **Define Experiment Configuration:**
   - Specify batch sizes, memory budget ratios, CXL parameters, and seed count (or deterministic rationale).
   - Write the declarative YAML config to `configs/<experiment_name>.yaml`.
3. **Rule Verification:**
   - Verify compliance with `01_scientific_integrity.md`, `02_simulation_transparency.md`, and `03_code_and_config_modularity.md`.
4. **Log and Await Approval:**
   - Present the experiment plan for user approval before executing any runs.
