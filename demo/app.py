"""
TierMoE Interactive Research Demonstration
Comprehensive systems demonstration covering EXP-01 through EXP-05B.
Presents the complete research narrative over existing experimental telemetry.
"""

from pathlib import Path
import os
import sys
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# Add parent directory to path for clean relative imports
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

# -----------------------------------------------------------------------------
# Page Configuration & Styling
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="TierMoE: Research Demonstration",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

def format_plot(fig, height=400):
    """Formats Plotly figure with dark-mode elegance and high contrast."""
    fig.update_layout(
        height=height,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#cbd5e1", size=11),
        margin=dict(l=20, r=20, t=40, b=20),
        legend=dict(
            bgcolor="rgba(15, 23, 42, 0.75)",
            bordercolor="rgba(148, 163, 184, 0.25)",
            borderwidth=1,
        ),
    )
    fig.update_xaxes(
        gridcolor="rgba(148, 163, 184, 0.12)",
        zerolinecolor="rgba(148, 163, 184, 0.25)",
        tickfont=dict(color="#94a3b8"),
        title_font=dict(color="#e2e8f0"),
    )
    fig.update_yaxes(
        gridcolor="rgba(148, 163, 184, 0.12)",
        zerolinecolor="rgba(148, 163, 184, 0.25)",
        tickfont=dict(color="#94a3b8"),
        title_font=dict(color="#e2e8f0"),
    )
    return fig

st.markdown("""
<style>
    .main-title {
        font-size: 2.3rem;
        font-weight: 800;
        letter-spacing: -0.02em;
        margin-bottom: 0.15rem;
        color: #60a5fa !important;
    }
    .sub-title {
        font-size: 1.15rem;
        font-weight: 500;
        color: #94a3b8 !important;
        margin-bottom: 1.2rem;
    }
    .badge {
        display: inline-block;
        padding: 0.28rem 0.75rem;
        font-size: 0.82rem;
        font-weight: 600;
        border-radius: 9999px;
        margin-right: 0.4rem;
        margin-bottom: 0.45rem;
    }
    .badge-blue { background-color: rgba(59, 130, 246, 0.18); color: #60a5fa !important; border: 1px solid rgba(59, 130, 246, 0.4); }
    .badge-green { background-color: rgba(34, 197, 94, 0.18); color: #4ade80 !important; border: 1px solid rgba(34, 197, 94, 0.4); }
    .badge-orange { background-color: rgba(249, 115, 22, 0.18); color: #fb923c !important; border: 1px solid rgba(249, 115, 22, 0.4); }
    .badge-red { background-color: rgba(239, 68, 68, 0.18); color: #f87171 !important; border: 1px solid rgba(239, 68, 68, 0.4); }
    .badge-purple { background-color: rgba(168, 85, 247, 0.18); color: #c084fc !important; border: 1px solid rgba(168, 85, 247, 0.4); }
    
    .card {
        background-color: rgba(30, 41, 59, 0.55);
        border: 1px solid rgba(148, 163, 184, 0.18);
        border-radius: 0.75rem;
        padding: 1.1rem 1.25rem;
        margin-bottom: 1rem;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.15);
    }
    .card-metric-title {
        font-size: 0.8rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        color: #94a3b8 !important;
    }
    .card-metric-value {
        font-size: 1.8rem;
        font-weight: 700;
        color: #f8fafc !important;
        margin-top: 0.2rem;
        margin-bottom: 0.1rem;
    }
    .card-metric-sub {
        font-size: 0.82rem;
        color: #94a3b8 !important;
    }
    .alert-box {
        padding: 0.95rem 1.2rem;
        border-radius: 0.6rem;
        border-left: 4px solid;
        margin-bottom: 1rem;
        font-size: 0.92rem;
        line-height: 1.5;
        background-color: rgba(30, 41, 59, 0.5);
        color: #e2e8f0;
    }
    .alert-info { border-left-color: #3b82f6; background-color: rgba(59, 130, 246, 0.1); }
    .alert-warning { border-left-color: #f59e0b; background-color: rgba(245, 158, 11, 0.1); }
    .alert-success { border-left-color: #10b981; background-color: rgba(16, 185, 129, 0.1); }
    
    .code-box {
        background-color: rgba(15, 23, 42, 0.85);
        border: 1px solid rgba(148, 163, 184, 0.25);
        border-radius: 0.6rem;
        padding: 1rem;
        font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
        font-size: 0.82rem;
        line-height: 1.38;
        color: #38bdf8;
        white-space: pre;
        overflow-x: auto;
    }
</style>
""", unsafe_allow_html=True)

facts = get_project_facts()

# -----------------------------------------------------------------------------
# Global Navigation Sidebar
# -----------------------------------------------------------------------------
st.sidebar.markdown("## **TierMoE Demo**")
st.sidebar.caption("Batch-Aware Expert Placement for Memory-Tiered MoE Inference")

nav_choice = st.sidebar.radio(
    "Navigation",
    [
        "🏠 Overview & Architecture",
        "📊 EXP-01 — Concurrency Sweeps",
        "🔀 EXP-02 — Routing Divergence",
        "🧠 EXP-03 — Authentic Traces & Co-Activation",
        "⚔️ EXP-04 — Broader Published Baselines",
        "⚡ EXP-05A — CXL Sensitivity (Modeled)",
        "🔬 EXP-05B — CXLMemSim Characterization",
        "🗺️ Complete Research Storyline",
        "🔮 Interactive 'What-If?' Explorer",
        "📦 Reproducibility & Paper Download",
    ],
    index=0,
)

st.sidebar.markdown("---")
st.sidebar.markdown("### **System Characterization**")
st.sidebar.markdown(f"""
- **Model:** `{facts['model']}`
- **Expert Blocks:** 128 total ({facts['expert_block_size_mib']} each)
- **Active / Token:** Top-{facts['active_experts_per_token']} ({facts['moe_layers']} layers)
- **Total Footprint:** **{facts['total_expert_footprint_tib']}** (1,536 GiB)
- **Physical Events:** **{facts['authentic_routing_events']:,}** routing decisions
- **Testbed:** {facts['eval_hardware']}
""")

st.sidebar.markdown("---")
st.sidebar.caption("⚠️ **Methodological Scope:** Evaluated on dual RTX A6000s; physical CXL hardware was unavailable. CXL results utilize modeled interconnect transfer times and upstream CXLMemSim characterization.")

paper_path = BASE_DIR / "docs/TierMoE_Final_Research_Paper.pdf"
if paper_path.exists():
    with open(paper_path, "rb") as f:
        pdf_bytes = f.read()
    st.sidebar.download_button(
        label="📄 Download Research Paper (PDF)",
        data=pdf_bytes,
        file_name="TierMoE_Final_Research_Paper.pdf",
        mime="application/pdf",
        use_container_width=True,
    )


# =============================================================================
# PAGE 1: OVERVIEW & ARCHITECTURE
# =============================================================================
if nav_choice == "🏠 Overview & Architecture":
    st.markdown('<div class="main-title">TierMoE: Batch-Aware Expert Placement</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-title">Interactive Research Demonstration — Complete Experimental Narrative</div>', unsafe_allow_html=True)

    st.markdown("""
    <span class="badge badge-blue">Dual RTX A6000 (96 GB)</span>
    <span class="badge badge-green">461,184 Authentic Routing Events</span>
    <span class="badge badge-purple">1.50 TiB Total Expert Footprint</span>
    <span class="badge badge-orange">Qwen3-30B-A3B (128 Experts, Top-8)</span>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns([3, 2])

    with col1:
        st.markdown("### The Memory-Tiering Problem in MoE Inference")
        st.write("""
        Modern Mixture-of-Experts (MoE) architectures achieve high computational efficiency by routing each token
        to a tiny subset of parameters (e.g., top-8 out of 128 experts). However, **the entire 1.50 TiB expert parameter set
        must remain accessible at runtime**.

        When multiple user inference requests execute concurrently, their routing decisions diverge across distinct experts.
        Because fast accelerator memory (HBM) is strictly constrained (e.g., 48 GB per GPU), serving concurrent batches
        forces expert parameters into slower memory tiers (such as CXL-attached memory or host DRAM).
        Existing isolated heuristics either ignore intra-batch concurrency or suffer severe intra-batch cache thrashing.
        """)

        st.markdown("### What TierMoE Does")
        st.markdown("""
        1. **Aggregates Expert Demand:** Observes the union of routing decisions across all requests in concurrent batch $\\mathcal{B}$.
        2. **Scores Marginal Utility:** Assigns each candidate expert an activation frequency score plus a residency hysteresis bonus:
        """)

        st.latex(r"\text{Score}(e) = \sum_{r \in \mathcal{B}} \mathbf{1}\{e \in \text{Demand}_r\} + \lambda \cdot \mathbf{1}\{e \in \mathcal{M}_{\text{current}}\}, \quad \lambda = 0.5")

        st.markdown("""
        3. **Deterministic Top-$C$ Placement:** Selects the top-$C$ scoring experts to retain in fast GPU memory in $\mathcal{O}(N)$ time.
        4. **Eliminates Thrashing:** Leaves unselected experts in slow memory, drastically reducing cross-tier parameter transfers.
        5. **Microsecond Execution:** Solves the placement decision in only **51.2 μs**, adding negligible overhead to token generation.
        """)

    with col2:
        st.markdown("### Conceptual Architecture")
        st.markdown("""
<pre class="code-box">
      Concurrent Inference Requests (Batch B)
                      ↓
       Instantaneous Routing Demands
                      ↓
       ┌──────────────────────────────┐
       │ Batch-Aware Demand Aggregator │
       │     Score(e) = Freq + λ·Res  │
       └──────────────┬───────────────┘
                      ↓
             Top-C Expert Quota
              ┌───────┴───────┐
              ↓               ↓
        ┌───────────┐   ┌───────────┐
        │ Fast Tier │   │ Slow Tier │
        │ (GPU HBM) │   │   (CXL)   │
        └─────┬─────┘   └─────┬─────┘
              └───────┬───────┘
                      ↓
           MoE Layer Token Execution
</pre>
        """, unsafe_allow_html=True)

        st.markdown("""
        <div class="alert-box alert-info">
            <b>Evaluation Testbed:</b> Qwen3-30B-A3B (128 experts, top-8 routing, 48 layers).
            Evaluated using dual NVIDIA RTX A6000 GPUs across authentic dialogue (ShareGPT) and mathematical reasoning (GSM8K).
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("### Scientific Verdicts Across All Six Research Questions")

    verdicts = get_rq_verdicts()
    rq_table = []
    for v in verdicts:
        rq_table.append({
            "Research Question": v["rq"],
            "Hypothesis & Investigation": v["question"],
            "Experiment": v["experiment"],
            "Scientific Verdict": v["status"],
            "Key Empirical Finding": v["finding"],
        })
    st.dataframe(pd.DataFrame(rq_table), use_container_width=True, hide_index=True)


# =============================================================================
# PAGE 2: EXP-01 CONCURRENCY SWEEPS
# =============================================================================
elif nav_choice == "📊 EXP-01 — Concurrency Sweeps":
    st.markdown('<div class="main-title">EXP-01: Concurrency Sweeps</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-title">Hypothesis H1 — Batch-Aware Placement Advantage Under Concurrent Memory Pressure</div>', unsafe_allow_html=True)

    df01, analysis01 = load_exp01()

    st.markdown("""
    <div class="alert-box alert-info">
        <b>Hypothesis H1:</b> Aggregating expert demand across concurrent sequences enables batch-aware placement
        to improve fast-tier hit rate and reduce CXL traffic when memory is constrained.
        <b>Status: SUPPORTED (Under Capacity Pressure).</b>
    </div>
    """, unsafe_allow_html=True)

    # Interactive Controls
    ctrl_col1, ctrl_col2, ctrl_col3 = st.columns(3)
    with ctrl_col1:
        b_val = st.selectbox("Batch Size (B)", sorted(df01["batch_size"].unique()), index=4)  # B=16
    with ctrl_col2:
        ratio_val = st.selectbox("Fast Memory Ratio", sorted(df01["fast_memory_ratio"].unique()), index=0)  # 0.25 (C=32)
    with ctrl_col3:
        seed_option = st.selectbox("Evaluation Seed", ["Multi-Seed Mean ± SEM", 42, 100, 2026])

    # Filter data
    cond_df = df01[(df01["batch_size"] == b_val) & (df01["fast_memory_ratio"] == ratio_val)]

    # Compute key metrics
    tiermoe_rows = cond_df[cond_df["algorithm"] == "TierMoE-Batch-Aware-Greedy"]
    single_rows = cond_df[cond_df["algorithm"] == "Baseline-3-Single-Request"]

    tm_hit = tiermoe_rows["overall_hit_rate"].mean() * 100.0
    sr_hit = single_rows["overall_hit_rate"].mean() * 100.0
    hit_diff_pp = tm_hit - sr_hit

    tm_traf_gb = tiermoe_rows["cxl_traffic_mb"].mean() / 1024.0
    sr_traf_gb = single_rows["cxl_traffic_mb"].mean() / 1024.0
    traf_red_pct = ((sr_traf_gb - tm_traf_gb) / sr_traf_gb) * 100.0 if sr_traf_gb > 0 else 0.0

    working_set = cond_df["avg_working_set_experts"].iloc[0]
    capacity = cond_df["fast_capacity_experts"].iloc[0]
    pressure_ratio = cond_df["capacity_pressure_ratio"].iloc[0]
    pressure_regime = cond_df["pressure_regime"].iloc[0]

    # Metric Cards
    m1, m2, m3, m4, m5 = st.columns(5)
    with m1:
        st.markdown(f'<div class="card"><div class="card-metric-title">TierMoE Hit Rate</div><div class="card-metric-value">{tm_hit:.2f}%</div><div class="card-metric-sub">Fast memory hits</div></div>', unsafe_allow_html=True)
    with m2:
        st.markdown(f'<div class="card"><div class="card-metric-title">Single-Request Hit</div><div class="card-metric-value">{sr_hit:.2f}%</div><div class="card-metric-sub">Isolated baseline</div></div>', unsafe_allow_html=True)
    with m3:
        badge_cls = "color: #4ade80;" if hit_diff_pp > 0 else "color: #94a3b8;"
        st.markdown(f'<div class="card"><div class="card-metric-title">Hit Rate Gain</div><div class="card-metric-value" style="{badge_cls}">+{hit_diff_pp:.2f} pp</div><div class="card-metric-sub">Percentage points</div></div>', unsafe_allow_html=True)
    with m4:
        st.markdown(f'<div class="card"><div class="card-metric-title">CXL Traffic Reduction</div><div class="card-metric-value">{traf_red_pct:.2f}%</div><div class="card-metric-sub">{tm_traf_gb:.1f} vs {sr_traf_gb:.1f} GB</div></div>', unsafe_allow_html=True)
    with m5:
        regime_color = "#f87171" if pressure_regime == "severe-pressure" else ("#fbbf24" if pressure_regime == "capacity-pressure" else "#4ade80")
        st.markdown(f'<div class="card"><div class="card-metric-title">Pressure Regime</div><div class="card-metric-value" style="font-size:1.15rem; color:{regime_color};">{pressure_regime.upper()}</div><div class="card-metric-sub">W={working_set:.1f} / C={capacity}</div></div>', unsafe_allow_html=True)

    st.markdown("---")

    # Interactive Plots
    pcol1, pcol2 = st.columns(2)

    with pcol1:
        st.markdown("#### Fast-Tier Hit Rate vs. Batch Size")
        sweep_df = df01[df01["fast_memory_ratio"] == ratio_val].groupby(["algorithm", "batch_size"])["overall_hit_rate"].mean().reset_index()
        sweep_df["hit_rate_pct"] = sweep_df["overall_hit_rate"] * 100.0

        fig_hit = px.line(
            sweep_df,
            x="batch_size",
            y="hit_rate_pct",
            color="algorithm",
            markers=True,
            title=f"Hit Rate vs. Batch Size (Fast Memory Ratio = {ratio_val})",
            labels={"batch_size": "Batch Size (B)", "hit_rate_pct": "Overall Hit Rate (%)", "algorithm": "Algorithm"},
            category_orders={"batch_size": [1, 2, 4, 8, 16, 32]},
        )
        format_plot(fig_hit)
        fig_hit.update_layout(hovermode="x unified", legend=dict(orientation="h", yanchor="bottom", y=-0.4, xanchor="center", x=0.5))
        st.plotly_chart(fig_hit, use_container_width=True)

    with pcol2:
        st.markdown("#### Modeled CXL Traffic vs. Batch Size")
        sweep_traf = df01[df01["fast_memory_ratio"] == ratio_val].groupby(["algorithm", "batch_size"])["cxl_traffic_mb"].mean().reset_index()
        sweep_traf["cxl_traffic_gb"] = sweep_traf["cxl_traffic_mb"] / 1024.0

        fig_traf = px.bar(
            sweep_traf,
            x="batch_size",
            y="cxl_traffic_gb",
            color="algorithm",
            barmode="group",
            title=f"Modeled CXL Traffic vs. Batch Size (Fast Memory Ratio = {ratio_val})",
            labels={"batch_size": "Batch Size (B)", "cxl_traffic_gb": "CXL Traffic (GB)", "algorithm": "Algorithm"},
        )
        format_plot(fig_traf)
        fig_traf.update_layout(hovermode="x unified", legend=dict(orientation="h", yanchor="bottom", y=-0.4, xanchor="center", x=0.5))
        st.plotly_chart(fig_traf, use_container_width=True)

    st.markdown("### Complete Condition Breakdown")
    piv = cond_df.groupby("algorithm").agg(
        mean_hit_rate=("overall_hit_rate", lambda x: f"{x.mean()*100:.2f}%"),
        cxl_traffic_gb=("cxl_traffic_mb", lambda x: f"{x.mean()/1024:.2f} GB"),
        avg_solver_time_us=("avg_solver_time_us", lambda x: f"{x.mean():.1f} μs"),
    ).reset_index()
    st.dataframe(piv, use_container_width=True, hide_index=True)


# =============================================================================
# PAGE 3: EXP-02 ROUTING DIVERGENCE
# =============================================================================
elif nav_choice == "🔀 EXP-02 — Routing Divergence":
    st.markdown('<div class="main-title">EXP-02: Routing Divergence</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-title">Hypothesis H2 — Inter-Request Overlap & The Confounding of Working-Set Expansion</div>', unsafe_allow_html=True)

    df02, analysis02 = load_exp02()

    st.markdown("""
    <div class="alert-box alert-warning">
        <b>Hypothesis H2 Scientific Assessment: PARTIALLY SUPPORTED.</b><br/>
        Under controlled batch size (e.g. fixed B=16), TierMoE's advantage increases monotonically as routing divergence rises.
        However, pooled correlation across all batch sizes is confounded (r = 0.292, p = 0.272) because higher divergence simultaneously expands the working set, causing memory saturation.
    </div>
    """, unsafe_allow_html=True)

    # Interactive Selectors
    sc1, sc2 = st.columns(2)
    with sc1:
        b_sel = st.selectbox("Batch Size (B)", sorted(df02["batch_size"].unique()), index=2)  # B=16
    with sc2:
        alpha_sel = st.selectbox("Zipf Skew Alpha (α)", sorted(df02["skew_alpha"].unique()), index=0)  # 0.8 (high divergence)

    sub_df = df02[(df02["batch_size"] == b_sel) & (df02["skew_alpha"] == alpha_sel)]
    jaccard = sub_df["avg_jaccard_overlap"].mean()
    divergence = sub_df["avg_request_divergence"].mean()
    working_set = sub_df["avg_working_set_experts"].mean()

    # Controlled B=16 comparison
    b16_df = df02[(df02["batch_size"] == 16) & (df02["fast_memory_ratio"] == 0.25)]
    piv_b16 = b16_df.pivot_table(index="skew_alpha", columns="algorithm", values="overall_hit_rate").reset_index()
    piv_b16["divergence"] = b16_df.groupby("skew_alpha")["avg_request_divergence"].first().values
    piv_b16["jaccard"] = b16_df.groupby("skew_alpha")["avg_jaccard_overlap"].first().values
    piv_b16["advantage_pp"] = (piv_b16["TierMoE-Batch-Aware-Greedy"] - piv_b16["Baseline-3-Single-Request"]) * 100.0

    ec1, ec2, ec3, ec4 = st.columns(4)
    with ec1:
        st.markdown(f'<div class="card"><div class="card-metric-title">Jaccard Overlap (J̄)</div><div class="card-metric-value">{jaccard:.3f}</div><div class="card-metric-sub">Mean pairwise token overlap</div></div>', unsafe_allow_html=True)
    with ec2:
        st.markdown(f'<div class="card"><div class="card-metric-title">Divergence (D = 1 - J̄)</div><div class="card-metric-value">{divergence:.3f}</div><div class="card-metric-sub">Disjoint request routing</div></div>', unsafe_allow_html=True)
    with ec3:
        st.markdown(f'<div class="card"><div class="card-metric-title">Working Set (W)</div><div class="card-metric-value">{working_set:.1f}</div><div class="card-metric-sub">Active experts in batch</div></div>', unsafe_allow_html=True)
    with ec4:
        adv_val = piv_b16[piv_b16["skew_alpha"] == alpha_sel]["advantage_pp"].values
        adv_str = f"+{adv_val[0]:.2f} pp" if len(adv_val) > 0 else "N/A"
        st.markdown(f'<div class="card"><div class="card-metric-title">Advantage (B=16, C=32)</div><div class="card-metric-value">{adv_str}</div><div class="card-metric-sub">TierMoE over Single-Request</div></div>', unsafe_allow_html=True)

    st.markdown("---")

    pc1, pc2 = st.columns(2)

    with pc1:
        st.markdown("#### Controlled Comparison: Advantage vs. Divergence (Fixed B=16, C=32)")
        fig_div = px.line(
            piv_b16.sort_values("divergence"),
            x="divergence",
            y="advantage_pp",
            markers=True,
            title="TierMoE Advantage Monotonically Increases with Divergence (B=16)",
            labels={"divergence": "Request Divergence D = 1 - J̄", "advantage_pp": "TierMoE Hit Rate Advantage (pp)"},
        )
        format_plot(fig_div)
        fig_div.update_traces(line=dict(color="#38bdf8", width=3), marker=dict(size=10, color="#60a5fa"))
        st.plotly_chart(fig_div, use_container_width=True)
        st.caption("At α=1.4 (low divergence D=0.751), gain is +1.99 pp. At α=0.8 (high divergence D=0.908), gain rises to +9.45 pp.")

    with pc2:
        st.markdown("#### Working-Set Confounding Across All Tested Batches")
        scatter_df = df02[df02["fast_memory_ratio"] == 0.25].copy()
        piv_all = scatter_df.pivot_table(index=["batch_size", "skew_alpha"], columns="algorithm", values="overall_hit_rate").reset_index()
        piv_all["divergence"] = scatter_df.groupby(["batch_size", "skew_alpha"])["avg_request_divergence"].first().values
        piv_all["working_set"] = scatter_df.groupby(["batch_size", "skew_alpha"])["avg_working_set_experts"].first().values
        piv_all["advantage_pp"] = (piv_all["TierMoE-Batch-Aware-Greedy"] - piv_all["Baseline-3-Single-Request"]) * 100.0

        fig_scat = px.scatter(
            piv_all,
            x="divergence",
            y="advantage_pp",
            color="batch_size",
            size="working_set",
            title="Pooled Divergence vs Advantage (Confounded by Working Set)",
            labels={"divergence": "Request Divergence D", "advantage_pp": "Advantage (pp)", "batch_size": "Batch Size"},
        )
        format_plot(fig_scat)
        st.plotly_chart(fig_scat, use_container_width=True)
        st.caption("Pooled correlation yields r = 0.292, p = 0.272. Larger batches simultaneously increase D and W, saturating memory capacity.")


# =============================================================================
# PAGE 4: EXP-03 AUTHENTIC TRACES & CO-ACTIVATION
# =============================================================================
elif nav_choice == "🧠 EXP-03 — Authentic Traces & Co-Activation":
    st.markdown('<div class="main-title">EXP-03: Authentic Traces & Co-Activation</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-title">Hypothesis H3 — Testing Pairwise Co-Activation Tracking on 461,184 Physical Qwen3 Routing Decisions</div>', unsafe_allow_html=True)

    df03, analysis03 = load_exp03()

    st.markdown("""
    <div class="alert-box alert-warning">
        <b>Hypothesis H3 Scientific Verdict: NOT SUPPORTED.</b><br/>
        Tracking temporal pairwise expert co-activation did <i>not</i> provide a statistically significant hit-rate improvement
        over instantaneous batch frequency (t = -1.387, p = 0.259) while incurring <b>12.5× higher solver overhead</b> (642.2 μs vs. 51.2 μs).
    </div>
    """, unsafe_allow_html=True)

    # Workload selector
    w_choice = st.radio("Workload", ["ShareGPT (Conversational Dialogue)", "GSM8K (Mathematical Reasoning)"], horizontal=True)
    dataset_key = "sharegpt" if "ShareGPT" in w_choice else "gsm8k"

    w_df = df03[df03["dataset"] == dataset_key]

    # Metrics overview
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        events = facts["authentic_sharegpt_events"] if dataset_key == "sharegpt" else facts["authentic_gsm8k_events"]
        st.markdown(f'<div class="card"><div class="card-metric-title">Profiled Decisions</div><div class="card-metric-value">{events:,}</div><div class="card-metric-sub">Layer router telemetry</div></div>', unsafe_allow_html=True)
    with c2:
        st.markdown(f'<div class="card"><div class="card-metric-title">Co-Activation Hit</div><div class="card-metric-value">92.23%</div><div class="card-metric-sub">ShareGPT (B=8, C=32)</div></div>', unsafe_allow_html=True)
    with c3:
        st.markdown(f'<div class="card"><div class="card-metric-title">TierMoE Greedy Hit</div><div class="card-metric-value">92.51%</div><div class="card-metric-sub">ShareGPT (B=8, C=32)</div></div>', unsafe_allow_html=True)
    with c4:
        st.markdown(f'<div class="card"><div class="card-metric-title">Paired t-Test</div><div class="card-metric-value">p = 0.259</div><div class="card-metric-sub">t = -1.387 (Not significant)</div></div>', unsafe_allow_html=True)

    st.markdown("---")

    # Plots
    col_p1, col_p2 = st.columns(2)

    with col_p1:
        st.markdown("#### Hit Rate Under Authentic Workloads")
        chart_df = w_df.groupby(["algorithm", "batch_size", "fast_memory_ratio"])["overall_hit_rate"].mean().reset_index()
        chart_df["hit_rate_pct"] = chart_df["overall_hit_rate"] * 100.0
        chart_df["setting"] = chart_df.apply(lambda r: f"B={int(r['batch_size'])}, C={int(128*r['fast_memory_ratio'])}", axis=1)

        fig_hit = px.bar(
            chart_df[chart_df["algorithm"].isin(["Baseline-2-Static-LFU", "TierMoE-Batch-Aware-CoActivation", "TierMoE-Batch-Aware-Greedy"])],
            x="setting",
            y="hit_rate_pct",
            color="algorithm",
            barmode="group",
            title=f"Hit Rate Comparison ({w_choice.split()[0]})",
            labels={"setting": "Evaluated Setting", "hit_rate_pct": "Hit Rate (%)"},
        )
        format_plot(fig_hit)
        st.plotly_chart(fig_hit, use_container_width=True)

    with col_p2:
        st.markdown("#### Placement Solver Overhead Comparison")
        overhead_data = pd.DataFrame([
            {"Algorithm": "TierMoE-Batch-Aware-Greedy", "Overhead_us": 51.2, "Type": "Instantaneous Frequency"},
            {"Algorithm": "TierMoE-Batch-Aware-CoActivation", "Overhead_us": 642.2, "Type": "Pairwise Co-Activation Graph"},
        ])
        fig_ov = px.bar(
            overhead_data,
            x="Algorithm",
            y="Overhead_us",
            color="Type",
            text="Overhead_us",
            title="Algorithm Solver Execution Overhead (μs)",
            labels={"Overhead_us": "Execution Time (μs)"},
        )
        format_plot(fig_ov)
        fig_ov.update_traces(texttemplate="%{text:.1f} μs", textposition="outside")
        st.plotly_chart(fig_ov, use_container_width=True)
        st.caption("TierMoE greedy placement solves in ~51 μs (0.05 ms), while co-activation requires 642 μs — a 12.5× latency penalty without hit-rate gain.")


# =============================================================================
# PAGE 5: EXP-04 BROADER PUBLISHED BASELINES
# =============================================================================
elif nav_choice == "⚔️ EXP-04 — Broader Published Baselines":
    st.markdown('<div class="main-title">EXP-04: Broader Published Baselines</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-title">Hypothesis H4 — Comparative Evaluation Against Representative MoE Serving Heuristics</div>', unsafe_allow_html=True)

    df04, analysis04 = load_exp04()

    st.markdown("""
    <div class="alert-box alert-success">
        <b>Comparative Findings:</b><br/>
        • <b>vs. Predictive Lookahead (MoE-Infinity/ProMoE style):</b> TierMoE achieves <b>+6.99 pp higher hit rate</b> (p = 0.00086).<br/>
        • <b>vs. Reactive CXL-LRU Tiering (CXL-MoE style):</b> TierMoE achieves <b>+16.61 to +32.27 pp higher hit rate</b> because LRU suffers severe intra-batch cache thrashing.
    </div>
    """, unsafe_allow_html=True)

    st.caption("⚠️ <i>Note on Baseline Implementations:</i> Baselines B4 and B5 represent conceptual, trace-driven reproductions of predictive prefetching and demand-LRU tiering principles rather than full proprietary vendor runtime frameworks.")

    # Controls
    b_sel04 = st.selectbox("Select Setting", [
        "B=8, C=32 (High Pressure)",
        "B=16, C=32 (Severe Pressure)",
        "B=32, C=32 (Extreme Pressure)",
        "B=32, C=64 (Moderate Pressure)",
    ], index=1)

    mapping = {
        "B=8, C=32 (High Pressure)": (8, 0.25),
        "B=16, C=32 (Severe Pressure)": (16, 0.25),
        "B=32, C=32 (Extreme Pressure)": (32, 0.25),
        "B=32, C=64 (Moderate Pressure)": (32, 0.50),
    }
    b_match, r_match = mapping[b_sel04]

    eval_df = df04[(df04["batch_size"] == b_match) & (df04["fast_memory_ratio"] == r_match)].copy()
    eval_df["hit_rate_pct"] = eval_df["overall_hit_rate"] * 100.0
    eval_df["traffic_gb"] = eval_df["cxl_traffic_mb"] / 1024.0

    # Clean display names
    display_names = {
        "Baseline-0-HBM-Only": "B0: HBM-Only (Upper Bound)",
        "Baseline-2-Static-LFU": "B2: Static LFU",
        "Baseline-3-Single-Request": "B3: Single-Request Isolated",
        "Baseline-4-Predictive-Activation-Aware": "B4: Predictive Lookahead (MoE-Infinity style)",
        "Baseline-5-CXL-LRU-Tiering": "B5: Reactive CXL-LRU (CXL-MoE style)",
        "TierMoE-Batch-Aware-Greedy": "TierMoE (Batch-Aware Greedy)",
    }
    eval_df["Policy"] = eval_df["algorithm"].map(display_names)

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("#### HBM Hit Rate Comparison (%)")
        fig_bhit = px.bar(
            eval_df,
            x="Policy",
            y="hit_rate_pct",
            color="algorithm",
            text="hit_rate_pct",
            title=f"Hit Rate Comparison: {b_sel04}",
            labels={"hit_rate_pct": "Hit Rate (%)"},
        )
        format_plot(fig_bhit)
        fig_bhit.update_traces(texttemplate="%{text:.2f}%", textposition="outside")
        fig_bhit.update_layout(showlegend=False, xaxis_tickangle=-30)
        st.plotly_chart(fig_bhit, use_container_width=True)

    with c2:
        st.markdown("#### Modeled CXL Traffic Comparison (GB)")
        fig_btraf = px.bar(
            eval_df,
            x="Policy",
            y="traffic_gb",
            color="algorithm",
            text="traffic_gb",
            title=f"Modeled CXL Parameter Traffic: {b_sel04}",
            labels={"traffic_gb": "Traffic (GB)"},
        )
        format_plot(fig_btraf)
        fig_btraf.update_traces(texttemplate="%{text:.1f} GB", textposition="outside")
        fig_btraf.update_layout(showlegend=False, xaxis_tickangle=-30)
        st.plotly_chart(fig_btraf, use_container_width=True)

    st.markdown("### The Intra-Batch Thrashing Mechanism in CXL-LRU")
    st.write("""
    Under reactive demand-paging (CXL-LRU), each token arrival that misses HBM evicts an existing expert block.
    When concurrent sequences in batch size $B=32$ request 79 distinct experts, LRU constantly evicts experts that
    other sequences immediately need in the same step. Consequently, **CXL-LRU hit rate collapses to 45.35% at B=32**,
    while TierMoE preserves a **77.62% hit rate (+32.27 pp)** by committing a stable batch-level expert quota.
    """)


# =============================================================================
# PAGE 6: EXP-05A CXL INTERCONNECT SENSITIVITY
# =============================================================================
elif nav_choice == "⚡ EXP-05A — CXL Sensitivity (Modeled)":
    st.markdown('<div class="main-title">EXP-05A: CXL Sensitivity Analysis</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-title">Hypothesis H5 — Translating Cross-Tier Traffic Reduction into Transfer-Time Savings</div>', unsafe_allow_html=True)

    df05a, analysis05a = load_exp05a()

    st.markdown("""
    <div class="alert-box alert-info">
        <b>Analytical Interconnect Model:</b> $T_{\\text{link}} \\approx V_{\\text{CXL}} / \\text{BW}_{\\text{CXL}}$.<br/>
        Physical CXL hardware was not available; parameter-transfer times are derived from the first-order link model.
        <b>Key Finding:</b> Link bandwidth dominates transfer time ($4.00\\times$ scaling from 16 to 64 GB/s); read latency contributes $< 0.005\\%$.
    </div>
    """, unsafe_allow_html=True)

    # Controls
    sc1, sc2, sc3 = st.columns(3)
    with sc1:
        bw_sel = st.selectbox("CXL Link Bandwidth", [16.0, 32.0, 64.0], index=1, format_func=lambda x: f"{int(x)} GB/s")
    with sc2:
        lat_sel = st.selectbox("CXL Read Latency", [150.0, 300.0, 600.0], index=1, format_func=lambda x: f"{int(x)} ns")
    with sc3:
        b_sel05a = st.selectbox("Batch Size (B)", [8, 16, 32], index=1)

    # Filter
    sub05a = df05a[
        (df05a["cxl_bandwidth_gbps"] == bw_sel) &
        (df05a["cxl_latency_ns"] == lat_sel) &
        (df05a["batch_size"] == b_sel05a)
    ]

    tm_row = sub05a[sub05a["algorithm"] == "TierMoE-Batch-Aware-Greedy"].iloc[0]
    sr_row = sub05a[sub05a["algorithm"] == "Baseline-3-Single-Request"].iloc[0]
    lfu_row = sub05a[sub05a["algorithm"] == "Baseline-2-Static-LFU"].iloc[0]

    time_saved_s = sr_row["modeled_cxl_transfer_time_s"] - tm_row["modeled_cxl_transfer_time_s"]
    time_red_pct = (time_saved_s / sr_row["modeled_cxl_transfer_time_s"]) * 100.0

    mc1, mc2, mc3, mc4 = st.columns(4)
    with mc1:
        st.markdown(f'<div class="card"><div class="card-metric-title">TierMoE Transfer Time</div><div class="card-metric-value">{tm_row["modeled_cxl_transfer_time_s"]:.2f} s</div><div class="card-metric-sub">Modeled parameter fetch</div></div>', unsafe_allow_html=True)
    with mc2:
        st.markdown(f'<div class="card"><div class="card-metric-title">Single-Request Time</div><div class="card-metric-value">{sr_row["modeled_cxl_transfer_time_s"]:.2f} s</div><div class="card-metric-sub">Isolated baseline</div></div>', unsafe_allow_html=True)
    with mc3:
        st.markdown(f'<div class="card"><div class="card-metric-title">Absolute Time Saved</div><div class="card-metric-value">{time_saved_s:.2f} s</div><div class="card-metric-sub">Per inference evaluation run</div></div>', unsafe_allow_html=True)
    with mc4:
        st.markdown(f'<div class="card"><div class="card-metric-title">Relative Time Saved</div><div class="card-metric-value">{time_red_pct:.2f}%</div><div class="card-metric-sub">Matches traffic reduction</div></div>', unsafe_allow_html=True)

    st.markdown("---")

    pc1, pc2 = st.columns(2)

    with pc1:
        st.markdown("#### Modeled Transfer Time vs. CXL Bandwidth (B=16)")
        bw_plot_df = df05a[(df05a["batch_size"] == 16) & (df05a["cxl_latency_ns"] == 300.0)]
        fig_bw = px.line(
            bw_plot_df,
            x="cxl_bandwidth_gbps",
            y="modeled_cxl_transfer_time_s",
            color="algorithm",
            markers=True,
            title="Transfer Time vs. Bandwidth (4.00× Scaling from 64 to 16 GB/s)",
            labels={"cxl_bandwidth_gbps": "CXL Bandwidth (GB/s)", "modeled_cxl_transfer_time_s": "Transfer Time (s)"},
        )
        format_plot(fig_bw)
        st.plotly_chart(fig_bw, use_container_width=True)

    with pc2:
        st.markdown("#### Transfer Time Invariance Across CXL Read Latencies")
        lat_plot_df = df05a[(df05a["batch_size"] == 16) & (df05a["cxl_bandwidth_gbps"] == 32.0)]
        fig_lat = px.line(
            lat_plot_df,
            x="cxl_latency_ns",
            y="modeled_cxl_transfer_time_s",
            color="algorithm",
            markers=True,
            title="Read Latency Invariance (< 0.005% Variation)",
            labels={"cxl_latency_ns": "Read Latency (ns)", "modeled_cxl_transfer_time_s": "Transfer Time (s)"},
        )
        format_plot(fig_lat)
        st.plotly_chart(fig_lat, use_container_width=True)


# =============================================================================
# PAGE 7: EXP-05B CXLMEMSIM QUEUE CHARACTERIZATION
# =============================================================================
elif nav_choice == "🔬 EXP-05B — CXLMemSim Characterization":
    st.markdown('<div class="main-title">EXP-05B: CXLMemSim Characterization</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-title">Hypothesis H6 — Discrete-Event Simulator Queue Dynamics & The 1/N Power Law</div>', unsafe_allow_html=True)

    df05b, analysis05b, microbench = load_exp05b()

    st.markdown("""
    <div class="alert-box alert-info">
        <b>Simulation Scope Disclaimer:</b> This characterization uses upstream <code>CXLMemSim</code> discrete-event simulations
        under tested configurations (BW=32 GB/s, latency=300 ns). It is <i>not</i> a physical CXL benchmark, nor a full-scale native simulation
        of all 75,546 transfers. It physically grounds queue startup and serialization behavior.
    </div>
    """, unsafe_allow_html=True)

    st.markdown("### Calibrated Startup Overhead & The 1/N Power Law")

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f'<div class="card"><div class="card-metric-title">Startup Overhead (T₀)</div><div class="card-metric-value">11.44 μs</div><div class="card-metric-sub">T₀ = C · Δt = 5,719 × 2 ns</div></div>', unsafe_allow_html=True)
    with c2:
        st.markdown(f'<div class="card"><div class="card-metric-title">Stall Factor @ 256 MiB</div><div class="card-metric-value">1.0014</div><div class="card-metric-sub">S = 1 + 5,719 / 4,194,304</div></div>', unsafe_allow_html=True)
    with c3:
        st.markdown(f'<div class="card"><div class="card-metric-title">Relative Error vs V/BW</div><div class="card-metric-value">0.14%</div><div class="card-metric-sub">Overhead amortized</div></div>', unsafe_allow_html=True)
    with c4:
        st.markdown(f'<div class="card"><div class="card-metric-title">Batch Activation Overhead</div><div class="card-metric-value">1.0 × T₀</div><div class="card-metric-sub">Shared expander invariance</div></div>', unsafe_allow_html=True)

    st.markdown("---")

    # Microbenchmark Plots
    col_mb1, col_mb2 = st.columns(2)

    with col_mb1:
        st.markdown("#### 1/N Power Law Relative Error Convergence")
        scaling = microbench["stream_scaling"]
        scale_df = pd.DataFrame({
            "Cachelines": scaling["N_cachelines"],
            "Measured_Error_Pct": scaling["rel_err_pct"],
            "Model_Fit_Pct": [(5719.0 / n) * 100.0 for n in scaling["N_cachelines"]],
        })
        fig_scale = px.line(
            scale_df,
            x="Cachelines",
            y=["Measured_Error_Pct", "Model_Fit_Pct"],
            log_x=True,
            log_y=True,
            markers=True,
            title="CXLMemSim Relative Error vs. Stream Length (1/N Convergence)",
            labels={"Cachelines": "Stream Length N (Cache Lines)", "value": "Relative Error (%)"},
        )
        format_plot(fig_scale)
        st.plotly_chart(fig_scale, use_container_width=True)
        st.caption("As stream size grows from 64 cache lines (4 KiB) to 262,144 cache lines (16 MiB), relative error converges from 8764% down to 2.19%, reaching 0.14% at 256 MiB.")

    with col_mb2:
        st.markdown("#### Batch Activation Overhead: Shared vs. Sequential Link")
        batch_bench = microbench["batch_activation"]
        batch_df = pd.DataFrame({
            "K_Experts": batch_bench["K_values"],
            "Shared_Expander_Overhead_us": [v / 1000.0 for v in batch_bench["concat_overhead_ns"]],
            "Sequential_Independent_us": [v / 1000.0 for v in batch_bench["sequential_overhead_ns"]],
        })
        fig_batch = px.line(
            batch_df,
            x="K_Experts",
            y=["Shared_Expander_Overhead_us", "Sequential_Independent_us"],
            log_x=True,
            log_y=True,
            markers=True,
            title="Batch Activation Overhead vs. Number of Experts (K)",
            labels={"K_Experts": "Concurrent Experts Fetched (K)", "value": "Measured Overhead (μs)"},
        )
        format_plot(fig_batch)
        st.plotly_chart(fig_batch, use_container_width=True)
        st.caption("Under a shared CXL expander link, K concurrent expert transfers incur approximately a single queue startup overhead (T₀ ≈ 11.44 μs), rather than K separate sequential penalties.")


# =============================================================================
# PAGE 8: COMPLETE RESEARCH STORYLINE
# =============================================================================
elif nav_choice == "🗺️ Complete Research Storyline":
    st.markdown('<div class="main-title">The Complete TierMoE Research Story</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-title">From the Memory-Tiering Bottleneck to Queue Characterization</div>', unsafe_allow_html=True)

    story_steps = [
        {
            "num": "01",
            "title": "The Memory-Tiering Crisis in Concurrent MoE Serving",
            "narrative": "MoE models like Qwen3-30B-A3B activate only 8 experts per token, but the full 1.50 TiB parameter footprint cannot fit into 48 GB/96 GB of fast GPU memory. Serving concurrent user requests causes dynamic expert divergence, forcing parameters across tiered interconnects.",
        },
        {
            "num": "02",
            "title": "EXP-01: Concurrency Creates the Batch-Aware Opportunity",
            "narrative": "Under memory pressure (W > C), TierMoE leverages inter-request overlap to improve HBM hit rate by +3.79 to +8.68 pp and cut CXL parameter traffic by 13.20% to 20.44% compared to isolated single-request scheduling.",
        },
        {
            "num": "03",
            "title": "EXP-02: Request Divergence Governs Marginal Utility",
            "narrative": "In controlled batch comparisons (fixed B=16), TierMoE's advantage grows monotonically from +1.99 pp (low divergence) to +9.45 pp (high divergence). In pooled analysis, working-set expansion acts as a confounding factor (r=0.292, p=0.272).",
        },
        {
            "num": "04",
            "title": "EXP-03: Authentic Qwen3 Traces Reject Complex Co-Activation",
            "narrative": "Testing 461,184 authentic routing decisions across ShareGPT and GSM8K reveals that tracking pairwise co-activation history yields no statistically significant hit-rate benefit (p=0.259) while introducing a 12.5× higher solver overhead (642 μs vs 51 μs). Instantaneous batch frequency is optimal.",
        },
        {
            "num": "05",
            "title": "EXP-04: Simple Greedy Placement Outperforms Heuristic Baselines",
            "narrative": "TierMoE outperforms predictive sequence lookahead (+6.99 pp mean, p < 0.001) and reactive CXL-LRU tiering (+16.61 to +32.27 pp). Reactive LRU suffers catastrophic intra-batch thrashing because concurrent sequences constantly evict each other's active working set.",
        },
        {
            "num": "06",
            "title": "EXP-05A: Traffic Reductions Translate into Modeled Transfer-Time Savings",
            "narrative": "Sensitivity sweeps across 16–64 GB/s and 150–600 ns show link bandwidth dominates bulk transfer time (4.00× scaling). TierMoE saves up to 6.39 seconds of modeled transfer time per run at 16 GB/s.",
        },
        {
            "num": "07",
            "title": "EXP-05B: CXLMemSim Validates Bulk Transfer Amortization",
            "narrative": "Discrete-event queue characterization in CXLMemSim reveals a 1/N power law. For 256 MiB expert blocks, queue stall is just 1.0014 (0.14% relative error), confirming that the first-order link model V/BW accurately captures bulk transfer dynamics, with a single T₀ ≈ 11.44 μs startup overhead per batch step.",
        },
    ]

    for step in story_steps:
        st.markdown(f"""
        <div class="card">
            <div style="display: flex; align-items: center; margin-bottom: 0.5rem;">
                <span class="badge badge-blue" style="font-size: 0.95rem; margin-right: 0.8rem;">STEP {step['num']}</span>
                <span style="font-size: 1.2rem; font-weight: 700; color: #f1f5f9;">{step['title']}</span>
            </div>
            <div style="font-size: 0.95rem; line-height: 1.5; color: #cbd5e1;">{step['narrative']}</div>
        </div>
        """, unsafe_allow_html=True)


# =============================================================================
# PAGE 9: WHAT-IF? SCENARIO EXPLORER
# =============================================================================
elif nav_choice == "🔮 Interactive 'What-If?' Explorer":
    st.markdown('<div class="main-title">Interactive "What-If?" Explorer</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-title">Query Evaluated Experimental Conditions Directly from Repository Telemetry</div>', unsafe_allow_html=True)

    st.caption("🔍 Queries existing measured/modeled results. If a requested combination was not experimentally evaluated, a fallback notice is explicitly displayed without silent extrapolation.")

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        w_in = st.selectbox("Workload", ["ShareGPT", "GSM8K", "Synthetic"])
    with c2:
        b_in = st.selectbox("Batch Size", [1, 2, 4, 8, 16, 32], index=3)
    with c3:
        r_in = st.selectbox("Fast Capacity Ratio", [0.25, 0.50, 0.75, 1.00], index=0)
    with c4:
        p_in = st.selectbox("Policy", [
            "TierMoE-Batch-Aware-Greedy",
            "Baseline-3-Single-Request",
            "Baseline-2-Static-LFU",
            "Baseline-4-Predictive-Activation-Aware",
            "Baseline-5-CXL-LRU-Tiering",
            "TierMoE-Batch-Aware-CoActivation",
            "Baseline-0-HBM-Only",
        ])
    with c5:
        bw_in = st.selectbox("CXL Bandwidth", [16.0, 32.0, 64.0], index=1, format_func=lambda x: f"{int(x)} GB/s")

    res = lookup_what_if(w_in, b_in, r_in, p_in, bw_in)

    if res["evaluated"]:
        st.markdown("""<div class="alert-box alert-success"><b>Configuration Evaluated:</b> Verified empirical and modeled telemetry found in repository results.</div>""", unsafe_allow_html=True)
        
        # Look up baseline (Single-Request) for paired comparison under same conditions
        res_base = lookup_what_if(w_in, b_in, r_in, "Baseline-3-Single-Request", bw_in) if p_in != "Baseline-3-Single-Request" else None

        m1, m2, m3, m4 = st.columns(4)
        with m1:
            delta_str = ""
            if res_base and res_base.get("evaluated"):
                diff = res["hit_rate_pct"] - res_base["hit_rate_pct"]
                delta_str = f'<div class="card-metric-sub" style="color:#4ade80;">+{diff:.2f} pp vs Single-Req</div>' if diff >= 0 else f'<div class="card-metric-sub" style="color:#f87171;">{diff:.2f} pp vs Single-Req</div>'
            else:
                delta_str = '<div class="card-metric-sub">Fast tier residency</div>'
            st.markdown(f'<div class="card"><div class="card-metric-title">Fast-Tier Hit Rate</div><div class="card-metric-value">{res["hit_rate_pct"]:.2f}%</div>{delta_str}</div>', unsafe_allow_html=True)
            
        with m2:
            traf_sub = ""
            if res_base and res_base.get("evaluated") and res_base["traffic_gb"] > 0:
                red = ((res_base["traffic_gb"] - res["traffic_gb"]) / res_base["traffic_gb"]) * 100.0
                traf_sub = f'<div class="card-metric-sub" style="color:#4ade80;">{red:.2f}% traffic cut</div>' if red >= 0 else f'<div class="card-metric-sub" style="color:#f87171;">+{abs(red):.2f}% traffic</div>'
            else:
                traf_sub = f'<div class="card-metric-sub">{res["traffic_mb"]:.1f} MB total</div>'
            st.markdown(f'<div class="card"><div class="card-metric-title">CXL Traffic</div><div class="card-metric-value">{res["traffic_gb"]:.2f} GB</div>{traf_sub}</div>', unsafe_allow_html=True)
            
        with m3:
            time_sub = ""
            if res_base and res_base.get("evaluated"):
                saved = res_base["modeled_time_s"] - res["modeled_time_s"]
                time_sub = f'<div class="card-metric-sub" style="color:#4ade80;">Saves {saved:.2f} s</div>' if saved >= 0 else f'<div class="card-metric-sub" style="color:#f87171;">+{abs(saved):.2f} s added</div>'
            else:
                time_sub = f'<div class="card-metric-sub">At {int(bw_in)} GB/s link</div>'
            st.markdown(f'<div class="card"><div class="card-metric-title">Modeled Transfer Time</div><div class="card-metric-value">{res["modeled_time_s"]:.2f} s</div>{time_sub}</div>', unsafe_allow_html=True)

        with m4:
            fast_cap = int(128 * r_in)
            st.markdown(f'<div class="card"><div class="card-metric-title">Fast Memory Quota</div><div class="card-metric-value">{fast_cap} / 128</div><div class="card-metric-sub">{fast_cap * 256 / 1024:.1f} GiB HBM / layer</div></div>', unsafe_allow_html=True)

        # Side-by-Side Comparison Charts
        c_chart1, c_chart2 = st.columns(2)
        with c_chart1:
            st.markdown("#### Scenario Hit Rate Comparison")
            bar_data = [{"Policy": p_in, "Hit Rate (%)": res["hit_rate_pct"]}]
            if res_base and res_base.get("evaluated"):
                bar_data.append({"Policy": "Baseline-3-Single-Request", "Hit Rate (%)": res_base["hit_rate_pct"]})
            bar_df = pd.DataFrame(bar_data)
            fig_hit_comp = px.bar(
                bar_df,
                x="Policy",
                y="Hit Rate (%)",
                color="Policy",
                text="Hit Rate (%)",
                title=f"Hit Rate: {p_in} vs Baseline",
            )
            format_plot(fig_hit_comp, height=320)
            fig_hit_comp.update_traces(texttemplate="%{text:.2f}%", textposition="outside")
            fig_hit_comp.update_layout(showlegend=False)
            st.plotly_chart(fig_hit_comp, use_container_width=True)

        with c_chart2:
            st.markdown("#### Scenario CXL Traffic Comparison")
            traf_data = [{"Policy": p_in, "Traffic (GB)": res["traffic_gb"]}]
            if res_base and res_base.get("evaluated"):
                traf_data.append({"Policy": "Baseline-3-Single-Request", "Traffic (GB)": res_base["traffic_gb"]})
            traf_df = pd.DataFrame(traf_data)
            fig_traf_comp = px.bar(
                traf_df,
                x="Policy",
                y="Traffic (GB)",
                color="Policy",
                text="Traffic (GB)",
                title=f"CXL Parameter Traffic: {p_in} vs Baseline",
            )
            format_plot(fig_traf_comp, height=320)
            fig_traf_comp.update_traces(texttemplate="%{text:.1f} GB", textposition="outside")
            fig_traf_comp.update_layout(showlegend=False)
            st.plotly_chart(fig_traf_comp, use_container_width=True)

        # Evaluation Provenance & Architecture Context Card
        st.markdown(f"""
        <div class="card" style="margin-top: 0.5rem;">
            <div style="font-weight: 700; color: #f8fafc; font-size: 1.05rem; margin-bottom: 0.4rem;">Evaluation Provenance & Architecture Context</div>
            <div style="font-size: 0.9rem; color: #cbd5e1; line-height: 1.6;">
                • <b>Data Lineage:</b> {res['source']}<br/>
                • <b>Workload Profile:</b> {res['workload']}<br/>
                • <b>Operating Regime:</b> Batch Size B={b_in}, Fast Memory Ratio={r_in} ({fast_cap} experts, {fast_cap * 256 / 1024:.1f} GiB per MoE layer)<br/>
                • <b>Modeled Interconnect:</b> {int(bw_in)} GB/s CXL Type-3 Link ($T_{{link}} \\approx V / \\text{{BW}}$)<br/>
                • <b>Notes:</b> {res['notes']}
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Collapsible JSON for reviewers who want to inspect raw records
        with st.expander("🔍 View Raw Benchmark Telemetry (JSON Payload)", expanded=False):
            st.json(res)
    else:
        st.markdown(f"""
        <div class="alert-box alert-warning">
            <b>{res["message"]}</b><br/>
            The requested combination (Workload: <code>{w_in}</code>, B: <code>{b_in}</code>, Ratio: <code>{r_in}</code>, Policy: <code>{p_in}</code>) was not evaluated in the experimental matrix.
            TierMoE does not fabricate synthetic predictions.
        </div>
        """, unsafe_allow_html=True)


# =============================================================================
# PAGE 10: REPRODUCIBILITY & PAPER DOWNLOAD
# =============================================================================
elif nav_choice == "📦 Reproducibility & Paper Download":
    st.markdown('<div class="main-title">Reproducibility & Research Artifacts</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-title">Hardware Specifications, Software Stack, and Complete Submission Paper</div>', unsafe_allow_html=True)

    c1, c2 = st.columns([3, 2])

    with c1:
        st.markdown("### Research Paper Access")
        if paper_path.exists():
            st.success(f"Full paper PDF available: `{paper_path.name}` ({os.path.getsize(paper_path):,} bytes)")
            with open(paper_path, "rb") as f:
                pdf_bytes = f.read()
            st.download_button(
                label="📥 Download Full Research Paper PDF",
                data=pdf_bytes,
                file_name="TierMoE_Final_Research_Paper.pdf",
                mime="application/pdf",
                use_container_width=True,
            )
        else:
            st.warning("Paper PDF not found at `docs/TierMoE_Final_Research_Paper.pdf`.")

        st.markdown("### Execution Environment & Testbed")
        st.markdown("""
        | Parameter | Specification |
        | :--- | :--- |
        | **Model** | `Qwen3-30B-A3B-Instruct-2507` (128 experts, top-8 routing, 48 MoE layers) |
        | **Accelerators** | Dual NVIDIA RTX A6000 (48 GB GDDR6 each, 96 GB aggregate VRAM) |
        | **Host Processor** | AMD EPYC 7763 64-Core Processor (128 threads @ 2.45 GHz) |
        | **Host System Memory** | 512 GB DDR4-3200 ECC Registered |
        | **Operating System** | Ubuntu 22.04.4 LTS (Linux kernel 5.15.0) |
        | **Software Stack** | Python 3.10+, PyTorch 2.4+, Streamlit 1.38+, Plotly 5.24+ |
        | **Authentic Routing Events** | **461,184 decisions** (ShareGPT: 276,816; GSM8K: 184,368) |
        | **CXL Evaluation** | First-order analytical link model + upstream CXLMemSim characterization |
        """)

    with c2:
        st.markdown("### How to Run the Demonstration Locally")
        st.markdown("""
<pre class="code-box">
# 1. Activate your Python environment
source /home/k8s-admin/Vinay/sglang/.venv/bin/activate

# 2. Launch Streamlit
streamlit run demo/app.py
</pre>
        """, unsafe_allow_html=True)

        st.markdown("""
        <div class="alert-box alert-info">
            <b>Demonstration Scope:</b> This demonstration is a presentation layer over existing experimental results.
            It does not re-run full deep learning benchmarks or heavy CXLMemSim simulations at runtime, ensuring instantaneous responsiveness.
        </div>
        """, unsafe_allow_html=True)
