# Rule 02: Simulation Transparency & Hardware Grounding

1. **Hardware Environment**: The development workstation contains 2 × NVIDIA RTX A6000 GPUs (48GB GDDR6 each).
2. **No False Hardware Claims**: The RTX A6000 does not contain CXL memory. Never present physical GPU GDDR6/PCIe operations as physical CXL hardware.
3. **Hybrid Methodology Demarcation**: All logs, plots, reports, and data files must explicitly label metrics:
   - `[Real Hardware]`: Real GPU execution time, CUDA memory footprint, router forward-pass traces.
   - `[Simulated CXL]`: Modeled CXL latency penalties, bandwidth bounds, tier migration delays, and NUMA memory models.
4. **Grounding Parameters**: CXL simulation parameters (latency: 150–800ns, bandwidth: 16–64 GB/s) must be grounded in published literature or verified hardware datasheets.
