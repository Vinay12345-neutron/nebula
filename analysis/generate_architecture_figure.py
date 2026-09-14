import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as patches

fig, ax = plt.subplots(figsize=(10, 5.2), dpi=300)
ax.axis('off')

# Colors
c_req = '#E0F2FE'       # Light sky
c_router = '#F1F5F9'    # Slate light
c_agg = '#FEF3C7'       # Amber light
c_solver = '#DCFCE7'    # Green light
c_hbm = '#DBEAFE'       # Blue light
c_cxl = '#F3E8FF'       # Purple light
c_border = '#334155'    # Slate dark

# Box 1: Concurrent Inference Requests
ax.add_patch(patches.FancyBboxPatch((0.03, 0.62), 0.22, 0.32, boxstyle="round,pad=0.03", ec=c_border, fc=c_req, lw=1.5))
ax.text(0.14, 0.88, "Concurrent Inference Requests", ha='center', va='center', fontsize=10, fontweight='bold', color='#0F172A')
ax.text(0.14, 0.78, "Batch Size B ∈ [1, 32]\nReq 1: Top-8 Experts\nReq 2: Top-8 Experts\n... Req B: Top-8 Experts", ha='center', va='center', fontsize=8, color='#334155')
ax.text(0.14, 0.66, "Token Routing Decisions", ha='center', va='center', fontsize=7.5, fontstyle='italic', color='#64748B')

# Arrow 1 -> 2
ax.annotate('', xy=(0.31, 0.78), xytext=(0.26, 0.78),
            arrowprops=dict(facecolor='#475569', edgecolor='#475569', arrowstyle="-|>", lw=2, mutation_scale=15))

# Box 2: MoE Layer Execution & Profiler
ax.add_patch(patches.FancyBboxPatch((0.32, 0.62), 0.24, 0.32, boxstyle="round,pad=0.03", ec=c_border, fc=c_router, lw=1.5))
ax.text(0.44, 0.88, "MoE Routing Engine", ha='center', va='center', fontsize=10, fontweight='bold', color='#0F172A')
ax.text(0.44, 0.78, "Qwen3-30B-A3B (48 Layers)\n128 Total Experts\nTop-8 Gating Network\n461,184 Real Routing Events", ha='center', va='center', fontsize=8, color='#334155')
ax.text(0.44, 0.66, "Forward Router Hooks", ha='center', va='center', fontsize=7.5, fontstyle='italic', color='#64748B')

# Arrow 2 -> 3
ax.annotate('', xy=(0.62, 0.78), xytext=(0.57, 0.78),
            arrowprops=dict(facecolor='#475569', edgecolor='#475569', arrowstyle="-|>", lw=2, mutation_scale=15))

# Box 3: Batch Demand Aggregator
ax.add_patch(patches.FancyBboxPatch((0.63, 0.62), 0.33, 0.32, boxstyle="round,pad=0.03", ec=c_border, fc=c_agg, lw=1.5))
ax.text(0.795, 0.88, "Batch Demand Aggregator", ha='center', va='center', fontsize=10, fontweight='bold', color='#92400E')
ax.text(0.795, 0.77, r"$f_e(B) = \sum_{r=1}^B \mathbf{1}\{e \in \mathrm{Demand}_r\}$" + "\n" +
                      "Multi-Tenant Access Frequency\nInter-Request Overlap Extraction\nWorking Set Expansion Tracking", ha='center', va='center', fontsize=8, color='#78350F')

# Arrow Down to Solver
ax.annotate('', xy=(0.50, 0.50), xytext=(0.50, 0.58),
            arrowprops=dict(facecolor='#475569', edgecolor='#475569', arrowstyle="-|>", lw=2, mutation_scale=15))

# Box 4: TierMoE Placement Solver
ax.add_patch(patches.FancyBboxPatch((0.15, 0.28), 0.70, 0.22, boxstyle="round,pad=0.03", ec='#15803D', fc=c_solver, lw=2))
ax.text(0.50, 0.44, "TierMoE Batch-Aware Placement Solver", ha='center', va='center', fontsize=11, fontweight='bold', color='#14532D')
ax.text(0.50, 0.35, r"Scoring Rule:  $\mathrm{Score}(e) = f_e(B) + \lambda \cdot \mathbf{1}\{e \in M_{\mathrm{current}}\}$   $(\lambda = 0.5)$" + "\n" +
                      "Marginal Utility Optimization with Residency Hysteresis  |  Solver Overhead: ~51.2 μs/step\n" +
                      r"Constraint: Select Top-$C$ Experts into Fast HBM Budget  ($C \in \{32, 64\}$ Experts)", ha='center', va='center', fontsize=8.5, color='#166534')

# Arrows from Solver to Tiers
ax.annotate('', xy=(0.28, 0.18), xytext=(0.35, 0.27),
            arrowprops=dict(facecolor='#1E40AF', edgecolor='#1E40AF', arrowstyle="-|>", lw=2, mutation_scale=15))
ax.annotate('', xy=(0.72, 0.18), xytext=(0.65, 0.27),
            arrowprops=dict(facecolor='#6B21A8', edgecolor='#6B21A8', arrowstyle="-|>", lw=2, mutation_scale=15))

# Box 5: Fast GPU HBM Tier
ax.add_patch(patches.FancyBboxPatch((0.10, 0.02), 0.36, 0.16, boxstyle="round,pad=0.03", ec='#1E40AF', fc=c_hbm, lw=1.5))
ax.text(0.28, 0.13, "Fast Memory Tier: GPU HBM", ha='center', va='center', fontsize=9.5, fontweight='bold', color='#1E3A8A')
ax.text(0.28, 0.06, "Top-C Placed Experts (Resident Cache)\nHigh Bandwidth (1-2 TB/s)  |  Low Latency\nServes Hits with Zero Cross-Tier Penalty", ha='center', va='center', fontsize=7.5, color='#1E40AF')

# Box 6: Slower CXL Memory Tier
ax.add_patch(patches.FancyBboxPatch((0.54, 0.02), 0.36, 0.16, boxstyle="round,pad=0.03", ec='#6B21A8', fc=c_cxl, lw=1.5))
ax.text(0.72, 0.13, "Capacity Tier: CXL.mem Pool", ha='center', va='center', fontsize=9.5, fontweight='bold', color='#581C87')
ax.text(0.72, 0.06, "Remaining Experts (Cold/Secondary Store)\nPCIe 5.0 Type-3 Expander (16-64 GB/s)\nBulk On-Demand Expert Transfers (256 MB)", ha='center', va='center', fontsize=7.5, color='#6B21A8')

plt.tight_layout()
fig.savefig('/home/k8s-admin/Vinay/nebula/figures/tiermoe_system_architecture.png', bbox_inches='tight')
plt.close(fig)
print("System architecture figure generated successfully.")
