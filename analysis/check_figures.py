import os
from PIL import Image

figs = [
    "figures/tiermoe_system_architecture.png",
    "figures/exp01_rq1_batch_aware/fig1_hit_rate_vs_memory_budget.png",
    "figures/exp01_rq1_batch_aware/fig2_cxl_traffic_vs_batch_size.png",
    "figures/exp01_rq1_batch_aware/fig4_algorithm_pareto_curve.png",
    "figures/exp02_advantage_vs_divergence.png",
    "figures/exp03_hit_rate_qwen3.png",
    "figures/exp04_comparative_hit_rate.png",
    "figures/exp05a_cxl_bandwidth_sensitivity.png",
    "figures/exp05a_transfer_time_reduction.png",
    "figures/exp05b_fig5_stream_scaling_convergence.png",
    "figures/exp05b_fig7_batch_activation_overhead.png",
]

for f in figs:
    if os.path.exists(f):
        im = Image.open(f)
        print(f"{f}: {im.size[0]}x{im.size[1]}, aspect={im.size[0]/im.size[1]:.2f}")
    else:
        print(f"{f}: NOT FOUND")
