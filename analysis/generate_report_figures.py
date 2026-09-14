import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import os

os.makedirs('/home/k8s-admin/Vinay/nebula/figures', exist_ok=True)

# Set style
plt.rcParams.update({
    'font.size': 10,
    'axes.labelsize': 11,
    'axes.titlesize': 12,
    'xtick.labelsize': 9,
    'ytick.labelsize': 9,
    'legend.fontsize': 9,
    'figure.titlesize': 14,
    'figure.dpi': 300
})

# -------------------------------------------------------------
# Figure 4: Queue Serialization Waves (4 concurrent requests)
# -------------------------------------------------------------
fig, ax = plt.subplots(figsize=(8, 4.0))
y_ticks = [0, 1, 2, 3]
y_labels = ['Req 0 (TID 0)', 'Req 1 (TID 1)', 'Req 2 (TID 2)', 'Req 3 (TID 3)']
# Active execution bars
ax.barh(0, 351, left=0, height=0.5, color='#1f77b4', label='Credit Wave 1 (Active Dispatch)', edgecolor='black')
ax.barh(1, 351, left=0, height=0.5, color='#1f77b4', edgecolor='black')
# Wait bars for req 2 & 3
ax.barh(2, 351, left=0, height=0.5, color='#ff7f0e', alpha=0.4, hatch='//', label='Queue Credit Stall (Waiting in request_queue_)', edgecolor='black')
ax.barh(2, 351, left=351, height=0.5, color='#2ca02c', label='Credit Wave 2 (Active Dispatch)', edgecolor='black')
ax.barh(3, 351, left=0, height=0.5, color='#ff7f0e', alpha=0.4, hatch='//', edgecolor='black')
ax.barh(3, 351, left=351, height=0.5, color='#2ca02c', edgecolor='black')

ax.axvline(351, color='red', linestyle='--', alpha=0.8, label='Credit Release (t = 351 ns)')
ax.axvline(702, color='darkred', linestyle=':', alpha=0.8, label='Batch Completion (t = 702 ns)')

ax.set_yticks(y_ticks)
ax.set_yticklabels(y_labels)
ax.set_xlabel('Simulation Time (ns)')
ax.set_title('CXLMemSim Queue Serialization: INITIAL_CREDITS=2 Enforces Discrete Waves')
ax.grid(True, linestyle=':', alpha=0.6, axis='x')
ax.legend(loc='lower right', framealpha=0.9, fontsize=8)
plt.tight_layout()
fig.savefig('/home/k8s-admin/Vinay/nebula/figures/exp05b_fig4_queue_serialization.png')
plt.close(fig)
print("Figure 4 saved.")

# -------------------------------------------------------------
# Figure 5: Stream Scaling & 1/N Convergence Law
# -------------------------------------------------------------
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10.5, 4.2))

# Data from stream_scaling_bench
N_vals = np.array([64, 128, 256, 512, 1024, 2048, 4096, 8192, 16384, 65536, 262144])
makespan = np.array([11346, 11722, 12099, 12476, 13607, 15492, 19639, 27933, 44144, 142541, 535752])
ideal = N_vals * 2.0
stall_factor = makespan / ideal
rel_err = (makespan - ideal) / ideal * 100

N_fit = np.logspace(np.log10(64), np.log10(4194304), 200)
C_calibrated = 5719.0
fit_stall = 1.0 + (C_calibrated / N_fit)
fit_rel_err = (C_calibrated / N_fit) * 100

# Left: Stall Factor
ax1.loglog(N_vals, stall_factor, 'o', color='#d62728', markersize=6, label='Empirical Measurements')
ax1.loglog(N_fit, fit_stall, '--', color='#1f77b4', label=r'Model: $S(N) = 1 + 5719/N$')
ax1.axvline(4194304, color='green', linestyle=':', label='256 MiB Target (S=1.0014)')
ax1.set_xlabel('Stream Length N (Cachelines)')
ax1.set_ylabel('Queue Stall Factor (Makespan / Ideal)')
ax1.set_title('Stall Factor Convergence vs. N')
ax1.grid(True, which='both', linestyle=':', alpha=0.5)
ax1.legend(framealpha=0.9, fontsize=8)

# Right: Relative Error %
ax2.loglog(N_vals, rel_err, 's', color='#9467bd', markersize=6, label='Measured Relative Error (%)')
ax2.loglog(N_fit, fit_rel_err, '--', color='#2ca02c', label=r'1/N Power Law: $\mathrm{RelErr} \propto 1/N$')
ax2.axvline(4194304, color='green', linestyle=':', label='256 MiB Error: 0.14%')
ax2.set_xlabel('Stream Length N (Cachelines)')
ax2.set_ylabel('Relative Error vs. Pure Bandwidth (%)')
ax2.set_title('Relative Error Convergence (1/N Law)')
ax2.grid(True, which='both', linestyle=':', alpha=0.5)
ax2.legend(framealpha=0.9, fontsize=8)

plt.tight_layout()
fig.savefig('/home/k8s-admin/Vinay/nebula/figures/exp05b_fig5_stream_scaling_convergence.png')
plt.close(fig)
print("Figure 5 saved.")

# -------------------------------------------------------------
# Figure 6: Multi-Stream Interleaving & Scheduling Invariance
# -------------------------------------------------------------
fig, ax = plt.subplots(figsize=(8, 4.0))
K_vals = [1, 2, 4, 8, 16, 32]
x = np.arange(len(K_vals))
width = 0.35

rr_makespan = [19639] * 6
chunk_makespan = [19639] * 6

rects1 = ax.bar(x - width/2, [m/1000 for m in rr_makespan], width, label='Round-Robin Interleaved', color='#1f77b4', edgecolor='black')
rects2 = ax.bar(x + width/2, [m/1000 for m in chunk_makespan], width, label='Chunked (Sequential per Stream)', color='#ff7f0e', edgecolor='black')

ax.set_xlabel('Number of Concurrent Streams K (Total N = 4,096 Cachelines)')
ax.set_ylabel('Transfer Makespan (μs)')
ax.set_title('CXLMemSim Scheduling Policy Invariance (RR vs. Chunked)')
ax.set_xticks(x)
ax.set_xticklabels([f'K={k}' for k in K_vals])
ax.set_ylim(0, 25)
ax.grid(True, linestyle=':', alpha=0.6, axis='y')
ax.axhline(19.639, color='red', linestyle='--', label='Invariant Makespan = 19.64 μs')
ax.legend(framealpha=0.9)

for rect in rects1:
    h = rect.get_height()
    ax.annotate(f'{h:.2f}', xy=(rect.get_x() + rect.get_width()/2, h), xytext=(0, 3),
                textcoords="offset points", ha='center', va='bottom', fontsize=8)

plt.tight_layout()
fig.savefig('/home/k8s-admin/Vinay/nebula/figures/exp05b_fig6_scheduling_invariance.png')
plt.close(fig)
print("Figure 6 saved.")

# -------------------------------------------------------------
# Figure 7: Batch Activation Overhead vs K (The Decisive Test)
# -------------------------------------------------------------
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.2))

K_test = [1, 2, 4, 8, 16, 32]
concat_ovhd = [11447, 11549, 11376, 11407, 11469, 11593]
rr_ovhd     = [11447, 11549, 11376, 11407, 11469, 11593]
chunk_ovhd  = [11447, 11549, 11376, 11407, 11469, 11593]
seq_ovhd    = [11470, 22940, 45880, 91760, 183520, 367040]

# Left: Overhead in microseconds
ax1.plot(K_test, [v/1000 for v in concat_ovhd], 'o-', label='Shared Expander (CONCAT)', color='#1f77b4', linewidth=2)
ax1.plot(K_test, [v/1000 for v in rr_ovhd], 's--', label='Shared Expander (Round-Robin)', color='#2ca02c')
ax1.plot(K_test, [v/1000 for v in chunk_ovhd], '^:', label='Shared Expander (Chunked)', color='#ff7f0e')
ax1.plot(K_test, [v/1000 for v in seq_ovhd], 'd-', label=r'Independent Activations ($\mathbf{K \times T_0}$)', color='#d62728', linewidth=2)
ax1.axhline(11.438, color='black', linestyle='--', label=r'Calibrated $T_0 = 11.44\,\mu\mathrm{s}$')

ax1.set_xscale('log', base=2)
ax1.set_yscale('log')
ax1.set_xlabel('Number of Expert Transfers (K)')
ax1.set_ylabel('Measured Overhead Above Ideal (μs)')
ax1.set_title('Overhead vs. K: Shared Link vs. Sequential')
ax1.grid(True, which='both', linestyle=':', alpha=0.5)
ax1.legend(framealpha=0.9, fontsize=8)

# Right: Ratio Overhead / T0
concat_ratio = [v / 11438.0 for v in concat_ovhd]
seq_ratio    = [v / 11438.0 for v in seq_ovhd]

ax2.plot(K_test, concat_ratio, 'o-', color='#1f77b4', linewidth=2, label='Shared Expander: Overhead / T0 ≈ 1.0')
ax2.plot(K_test, seq_ratio, 'd-', color='#d62728', linewidth=2, label='Sequential Expander: Overhead / T0 ≈ K')
ax2.axhline(1.0, color='#1f77b4', linestyle=':')
ax2.set_xscale('log', base=2)
ax2.set_yscale('log', base=2)
ax2.set_xlabel('Number of Expert Transfers (K)')
ax2.set_ylabel('Overhead Ratio (Overhead / T0)')
ax2.set_title(r'Overhead Normalization: Model B ($1\times T_0$) vs. Model C ($K\times T_0$)')
ax2.grid(True, which='both', linestyle=':', alpha=0.5)
ax2.legend(framealpha=0.9, fontsize=8)

plt.tight_layout()
fig.savefig('/home/k8s-admin/Vinay/nebula/figures/exp05b_fig7_batch_activation_overhead.png')
plt.close(fig)
print("Figure 7 saved.")

# -------------------------------------------------------------
# Figure 8: Model Prediction Error vs K
# -------------------------------------------------------------
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10.5, 4.0))

errB_ns = [9, 111, -62, -31, 31, 155]
errC_ns = [9, -11327, -34376, -80097, -171539, -354423]

errB_pct = [0.0, 0.4, -0.1, 0.0, 0.0, 0.1]
errC_pct = [0.0, -40.6, -77.9, -104.1, -120.3, -129.5]

x_idx = np.arange(len(K_test))

# Left: Error in ns
ax1.plot(x_idx, [e/1000 for e in errB_ns], 'o-', color='#2ca02c', linewidth=2, label='Model B Error (V/BW + T0)')
ax1.plot(x_idx, [e/1000 for e in errC_ns], 's-', color='#d62728', linewidth=2, label='Model C Error (V/BW + K*T0)')
ax1.axhline(0, color='black', linestyle=':')
ax1.set_xticks(x_idx)
ax1.set_xticklabels([f'K={k}' for k in K_test])
ax1.set_xlabel('Number of Concurrent Expert Transfers (K)')
ax1.set_ylabel('Prediction Error (μs) [Makespan - Model]')
ax1.set_title('Absolute Model Prediction Error (Shared Link)')
ax1.grid(True, linestyle=':', alpha=0.6)
ax1.legend(framealpha=0.9)

# Right: Error in %
ax2.plot(x_idx, errB_pct, 'o-', color='#2ca02c', linewidth=2, label='Model B: Error within [-0.1%, +0.4%]')
ax2.plot(x_idx, errC_pct, 's-', color='#d62728', linewidth=2, label='Model C: Error degrades to -129.5%')
ax2.axhline(0, color='black', linestyle=':')
ax2.set_xticks(x_idx)
ax2.set_xticklabels([f'K={k}' for k in K_test])
ax2.set_xlabel('Number of Concurrent Expert Transfers (K)')
ax2.set_ylabel('Relative Prediction Error (%)')
ax2.set_title('Relative Error: Massive Rejection of Model C')
ax2.grid(True, linestyle=':', alpha=0.6)
ax2.legend(framealpha=0.9)

plt.tight_layout()
fig.savefig('/home/k8s-admin/Vinay/nebula/figures/exp05b_fig8_model_error_comparison.png')
plt.close(fig)
print("Figure 8 saved.")

# -------------------------------------------------------------
# Figure 9: Full EXP-05B 10 Conditions Breakdown
# -------------------------------------------------------------
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.2))

batch_sizes = [8, 16, 32]
single_traffic_tb = [2813440 / 1e6, 2233344 / 1e6, 1597952 / 1e6]
tiermoe_traffic_tb = [2663680 / 1e6, 2115328 / 1e6, 1573376 / 1e6]

single_time_s = [92.194, 73.185, 52.364]
tiermoe_time_s = [87.287, 69.318, 51.558]

x_b = np.arange(len(batch_sizes))
w = 0.35

ax1.bar(x_b - w/2, single_traffic_tb, w, label='Baseline (Single-Request)', color='#1f77b4', edgecolor='black')
ax1.bar(x_b + w/2, tiermoe_traffic_tb, w, label='TierMoE (Batch-Aware)', color='#2ca02c', edgecolor='black')
ax1.set_xticks(x_b)
ax1.set_xticklabels([f'Batch {b}' for b in batch_sizes])
ax1.set_ylabel('Total CXL Traffic (TB)')
ax1.set_title('EXP-05B: Total CXL Traffic Volume (BW=32 GB/s)')
ax1.grid(True, linestyle=':', alpha=0.6, axis='y')
ax1.legend(framealpha=0.9)

for rect in ax1.patches:
    h = rect.get_height()
    ax1.annotate(f'{h:.2f}', xy=(rect.get_x() + rect.get_width()/2, h), xytext=(0, 3),
                 textcoords="offset points", ha='center', va='bottom', fontsize=8)

# Right: Transfer Time
ax2.bar(x_b - w/2, single_time_s, w, label='Baseline (Single-Request)', color='#1f77b4', edgecolor='black')
ax2.bar(x_b + w/2, tiermoe_time_s, w, label='TierMoE (Batch-Aware)', color='#2ca02c', edgecolor='black')
ax2.set_xticks(x_b)
ax2.set_xticklabels([f'Batch {b}' for b in batch_sizes])
ax2.set_ylabel('CXL Transfer Makespan (seconds)')
ax2.set_title('EXP-05B: CXL Transfer Time (BW=32 GB/s)')
ax2.grid(True, linestyle=':', alpha=0.6, axis='y')
ax2.legend(framealpha=0.9)

for rect in ax2.patches:
    h = rect.get_height()
    ax2.annotate(f'{h:.1f}s', xy=(rect.get_x() + rect.get_width()/2, h), xytext=(0, 3),
                 textcoords="offset points", ha='center', va='bottom', fontsize=8)

plt.tight_layout()
fig.savefig('/home/k8s-admin/Vinay/nebula/figures/exp05b_fig9_full_workload_breakdown.png')
plt.close(fig)
print("Figure 9 saved.")
