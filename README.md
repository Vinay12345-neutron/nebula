# Nebula-MoE

## Concurrent Batch-Aware Memory Tiering for MoE Inference on CXL-Expanded Systems

Nebula-MoE is a research project for **Astera Labs Nebula 2026** investigating memory management for Mixture-of-Experts (MoE) inference when fast GPU memory is capacity-constrained and a larger, slower CXL-attached memory tier is available.

The central question is:

> **How should MoE expert weights be placed across fast GPU memory and CXL memory when multiple inference requests are served concurrently and compete for limited fast-memory capacity?**

The project studies whether **batch-aware expert placement**, using aggregate expert demand and expert co-activation patterns, can reduce cross-tier memory traffic and improve inference performance compared with static or single-request placement policies.

---

## 1. Motivation

Modern MoE models contain many experts but activate only a small subset for each token.

For example:

```text
                 MoE Router
                     |
             +-------+-------+
             |               |
          Expert 7        Expert 42
```

This sparsity reduces computation, but all expert parameters still have to be stored somewhere.

The fundamental memory trade-off is:

```text
Fast GPU memory
      |
      |  High bandwidth
      |  Low latency
      |  Limited capacity
      |
      v
---------------------------
      |
      |  CXL
      v
CXL-attached memory
      |
      |  Larger capacity
      |  Higher latency
      |  Lower effective bandwidth
      |
```

CXL therefore provides a potential mechanism for expanding the memory available to AI systems.

However, simply putting "hot" experts in fast memory and "cold" experts in CXL is not sufficient as a research contribution: closely related expert offloading, caching, and CXL-MoE systems already exist.

Nebula-MoE therefore focuses on a more specific scenario:

> **Concurrent MoE serving, where multiple requests with different expert-access patterns compete for the same limited fast-memory capacity.**

---

## 2. Problem Statement

### Problem

MoE inference creates a large model-memory footprint while only a subset of experts is active for each token.

GPU memory provides high bandwidth and low latency but has limited capacity. CXL can provide additional memory capacity, but accesses to that tier are more expensive.

Existing placement approaches can exploit expert popularity or activation information to decide which experts should remain in fast memory. However, when multiple requests are served concurrently, their expert working sets can conflict.

For example:

```text
Request A -> E1 E2 E3
Request B -> E3 E4 E7
Request C -> E1 E7 E9
Request D -> E5 E6 E8
```

The system has to make one shared placement decision:

```text
                 Limited HBM
             +----------------+
             | E1 E3 E7 ...   |
             +----------------+
                    |
                    | overflow
                    v
             +----------------+
             | CXL memory     |
             | E2 E4 E5 ...   |
             +----------------+
```

A placement optimized for one request may be poor for the aggregate workload.

The problem becomes:

> **Given a concurrent batch of MoE requests and a finite fast-memory budget, which experts should reside in fast memory and which should reside in CXL memory to minimize expensive cross-tier accesses while maintaining inference performance?**

---

## 3. Research Direction

Nebula-MoE investigates **concurrent, batch-aware memory tiering**.

Instead of independently deciding:

```text
Request -> hot experts -> HBM
```

we analyze the aggregate workload:

```text
Concurrent requests
        |
        v
Expert routing traces
        |
        +----------------+
        |                |
        v                v
 Expert frequency   Expert co-activation
        |                |
        +--------+-------+
                 |
                 v
        Placement optimizer
                 |
          +------+------+
          |             |
          v             v
       Fast tier     CXL tier
         HBM          Memory
```

The placement policy may consider:

- aggregate expert access frequency
- expert co-activation
- overlap between requests
- HBM capacity available for expert weights
- CXL capacity
- migration cost
- workload changes over time
- eventually, KV-cache pressure and CXL bandwidth/latency

The core method will remain intentionally simple initially. More complex signals will only be added if experiments show that they provide measurable benefit.

---

## 4. Research Gap

The broad problem of using CXL as an additional memory tier for AI is already established.

Likewise, the following are existing research areas:

- expert offloading
- expert caching
- expert prefetching
- hot/cold expert placement
- CXL-based LLM memory expansion
- CXL-based MoE systems
- CXL memory pooling
- KV-cache offloading

Therefore, Nebula-MoE does **not** claim novelty from merely placing hot experts in GPU memory and cold experts in CXL memory.

The working research gap is:

> **Existing approaches motivate expert placement primarily around individual or static expert-demand patterns. Nebula-MoE investigates whether placement optimized for the aggregate demand of concurrently served requests can provide better memory utilization and inference performance under constrained fast-memory capacity.**

This gap remains a hypothesis and must be verified against the closest recent literature before being presented as a definitive novelty claim.

---

## 5. Research Questions

### RQ1 — Concurrent serving

**How does concurrent serving change the optimal placement of MoE experts across limited fast GPU memory and CXL memory compared with per-request or single-sequence placement?**

### RQ2 — Aggregate expert demand

**Can aggregate expert-demand information across concurrent requests improve fast-memory residency and reduce CXL parameter traffic compared with single-request placement policies?**

### RQ3 — Expert co-activation

**Does exploiting expert co-activation and overlap between concurrent requests provide additional benefit over simple frequency-based placement?**

### Secondary Research Questions

#### RQ4 — KV-cache pressure

How does changing KV-cache demand affect the amount of fast memory available for expert weights, and can dynamically adjusting the expert/KV allocation improve inference performance?

#### RQ5 — Workload drift

How robust is the placement policy when expert popularity changes over time or the workload composition changes?

#### RQ6 — CXL sensitivity

How does the effectiveness of different placement policies change as CXL latency, bandwidth, and memory capacity vary?

RQ1-RQ3 are the primary project axis. RQ4-RQ6 are secondary and should only be pursued after the core result is solid.

---

## 6. Hypotheses

### H1 — Batch-aware placement

Under concurrent MoE serving with heterogeneous expert demand, a batch-aware expert-placement policy will achieve higher fast-memory expert hit rates and lower CXL parameter traffic than policies derived from individual requests or static global expert popularity.

### H2 — Effect of workload divergence

The advantage of batch-aware placement will increase as concurrent requests exhibit more divergent expert-access patterns and fast-memory capacity becomes more constrained.

### H3 — Co-activation

In workloads with strongly correlated expert access, incorporating expert co-activation information will further reduce cross-tier accesses compared with frequency-only placement.

### H4 — Dynamic KV-cache budget

Accounting for KV-cache growth when determining the fast-memory budget available to expert weights will reduce inference latency compared with maintaining a fixed expert-memory allocation.

### H5 — CXL sensitivity

The performance advantage of intelligent fast/slow memory tiering will depend strongly on the latency and bandwidth characteristics of the CXL tier.

**Important:** These hypotheses are directional and testable. No numerical speedup is assumed before experimentation.

---

## 7. Proposed System

Nebula-MoE is envisioned as a workload-analysis and memory-placement framework.

```text
                    MoE Application
                          |
                          v
                 +----------------+
                 | Nebula Profiler|
                 +-------+--------+
                         |
                  Routing traces
                         |
                         v
                 +----------------+
                 | Workload       |
                 | Analyzer       |
                 +-------+--------+
                         |
              +----------+----------+
              |          |          |
              v          v          v
          Frequency   Overlap   Co-activation
              |          |          |
              +----------+----------+
                         |
                         v
                 +----------------+
                 | Placement      |
                 | Optimizer      |
                 +-------+--------+
                         |
                  HBM/CXL policy
                         |
              +----------+----------+
              |                     |
              v                     v
         Fast GPU memory       CXL memory
```

The eventual system may provide recommendations such as:

- which experts should remain resident in the fast tier
- which experts should be placed in CXL memory
- when experts should be migrated
- how much fast memory should be reserved for experts
- how workload changes affect the optimal placement

The initial implementation should prioritize **analysis and placement policy evaluation** rather than attempting to build a complete production CXL runtime.

---

## 8. Optimization Formulation

Let there be \(N\) experts:

$$
E = \{e_1,e_2,\ldots,e_N\}
$$

For each expert \(e\), define:

- $W_e$: expert memory footprint
- $f_e(B)$: access frequency in concurrent batch $B$
- $x_e \in \{0,1\}$: whether expert $e$ is placed in fast memory

Let the available fast-memory budget for expert weights be:

$$
C_{\text{expert}} =
C_{\text{fast}} -
C_{\text{KV}} -
C_{\text{other}}
$$

The placement must satisfy:

$$
\sum_e x_e W_e \leq C_{\text{expert}}
$$

A simplified objective is to maximize the expected benefit of keeping frequently accessed experts in the fast tier:

$$
\max_x
\sum_e
x_e f_e(B) \cdot
\text{Cost}_{\text{slow}}(e)
$$

subject to the memory-capacity constraint.

The final objective may be extended to incorporate:

- co-activation
- migration cost
- request priority
- CXL bandwidth
- CXL contention
- workload drift

Only extensions that are experimentally justified will be retained.

---

## 9. Baselines

The project should establish strong baselines before claiming a contribution.

### Baseline 0 — Fast-memory-only

All model/expert data is placed in fast GPU memory when capacity permits.

Purpose:

- performance reference
- best-case memory-access behavior
- identify capacity limits/OOM cases

### Baseline 1 — Naive overflow

Fast memory is filled first; remaining experts are placed in the slower tier.

Purpose:

- basic HBM + CXL reference

### Baseline 2 — Static global frequency / LFU

The most frequently accessed experts are kept in fast memory.

Purpose:

- frequency-based placement reference

### Baseline 3 — Activation-aware / predictive placement

Use a relevant existing expert caching/prefetching or activation-aware policy.

Potential systems include approaches such as MoE-Infinity or ProMoE, subject to reproducibility and relevance.

### Baseline 4 — Closest published CXL-MoE method

A faithful reproduction or controlled implementation of the closest recent CXL-MoE approach should be included where feasible.

The exact baseline will be selected after verifying the implementation details of the relevant paper.

### Proposed method

```text
Concurrent aggregate demand
+
expert overlap/co-activation
+
dynamic fast-memory budget
```

---

## 10. Evaluation Metrics

### Memory metrics

- Fast-tier expert residency
- Fast-tier hit rate
- CXL parameter traffic
- Total memory footprint
- Memory utilization
- Migration volume

### Inference metrics

- TTFT — Time to First Token
- TPOT — Time Per Output Token
- End-to-end latency
- P50 latency
- P95 latency
- P99 latency
- Throughput
- Requests per second

### Systems metrics

- CXL bandwidth utilization
- Effective memory bandwidth
- Transfer volume
- Placement-solver overhead
- Migration overhead
- GPU utilization

### Robustness metrics

- Performance vs batch size
- Performance vs HBM capacity
- Performance vs CXL latency
- Performance vs CXL bandwidth
- Performance under workload drift
- Performance under expert-demand divergence

---

## 11. Experimental Methodology

The project will proceed in stages.

### Stage 1 — MoE workload characterization

Run supported MoE models on the RTX A6000 workstation.

Collect:

- expert routing decisions
- expert access frequency
- per-request expert sets
- expert co-activation
- batch composition
- context length
- memory usage

### Stage 2 — Baseline measurements

Implement or reproduce the selected baselines.

Measure:

- expert hit rate
- CXL/slow-tier traffic
- inference latency
- throughput
- memory usage

### Stage 3 — Concurrent workload generation

Construct workloads with:

- different batch sizes
- varying request lengths
- high expert overlap
- low expert overlap
- mixed workload types
- changing expert popularity

### Stage 4 — Placement policy

Implement the batch-aware policy.

Initially use a simple, efficient greedy approach based on marginal utility rather than an expensive exact optimizer.

### Stage 5 — CXL modeling

Evaluate the policy against representative CXL memory configurations.

Model parameters may include:

- memory capacity
- latency
- bandwidth
- topology
- contention

The specific simulation framework will be selected after evaluating available CXL-capable tools.

### Stage 6 — Ablation studies

Determine the contribution of individual components:

```text
Frequency only
      |
      + co-activation
      |
      + concurrency
      |
      + dynamic capacity
      |
      + migration awareness
```

### Stage 7 — Analysis

Determine:

- when the proposed policy helps
- when it does not
- why it helps
- where its overhead dominates
- how sensitive results are to CXL characteristics

---

## 12. Hardware and Software Environment

### Primary development machine

The project will use a remote workstation accessed through SSH:

```text
rtx-a6000-workstation
```

with:

- 2 × NVIDIA RTX A6000
- CUDA
- PyTorch
- Linux
- Python
- C/C++

The workstation is the primary project workspace and compute environment.

### Important hardware limitation

The RTX A6000 does **not** contain CXL memory.

It uses GPU GDDR6 memory.

Therefore, the A6000 cannot be presented as a physical CXL platform.

Instead, the project uses a hybrid methodology:

```text
Real hardware
    |
    +-- MoE inference
    +-- routing traces
    +-- workload characterization
    +-- GPU measurements
    |
    v
CXL-aware simulation/model
    |
    +-- CXL capacity
    +-- latency
    +-- bandwidth
    +-- contention
    +-- memory-tier evaluation
```

This is a deliberate simulation methodology, not a claim of physical CXL validation.

---

## 13. CXL Modeling Strategy

The project does not require physical CXL hardware.

The initial experiments may use a simplified memory-tier model for rapid development.

For stronger system-level results, the project will investigate CXL-capable simulation frameworks such as:

- gem5
- SystemC
- DRAMSim3
- QEMU with CXL support
- other validated/open CXL simulators where appropriate

The final simulator will be chosen based on:

1. CXL modeling fidelity
2. support for the required memory hierarchy
3. ability to model latency/bandwidth
4. ability to represent contention
5. integration difficulty
6. reproducibility

### Important limitation

A NUMA memory + artificial latency model is **not equivalent to physical CXL**.

Such a model may be used for early experiments, but final claims must clearly distinguish:

- real GPU measurements
- simulated CXL results
- calibrated/model-based results

Where possible, simulation parameters should be grounded in published measurements from real CXL systems.

---

## 14. Models and Workloads

Candidate MoE workloads include open-source models such as:

- Qwen/Qwen3-30B-A3B-Instruct-2507 (128 total experts, 8 active per token)
- Qwen/Qwen3-30B-A3B-Thinking-2507-FP8 (FP8 quantized, 128 total experts, 8 active per token)
- other open-source MoE models that fit the available hardware or can be evaluated using appropriate quantization/configuration

### Model-scale limitation

The available 2 × RTX A6000 setup does not reproduce the memory behavior of the largest frontier MoE systems at full precision.

Therefore:

- model-scale limitations will be explicitly reported
- multiple expert-count configurations should be evaluated where possible
- conclusions should focus on the studied workload characteristics rather than claiming universal frontier-model validity

---

## 15. Key Experimental Variables

### Workload variables

- batch size
- number of concurrent requests
- prompt length
- generation length
- expert overlap
- expert divergence
- workload composition
- expert popularity distribution

### Memory variables

- fast-memory capacity
- expert-memory budget
- KV-cache budget
- CXL capacity
- expert size

### CXL variables

- latency
- bandwidth
- capacity
- contention
- topology, where supported by the simulator

---

## 16. Ablation Plan

The proposed system should be evaluated incrementally.

### A0 — Static placement

Global expert popularity only.

### A1 — Batch aggregation

Aggregate expert demand across concurrent requests.

### A2 — Co-activation

Add expert co-activation information.

### A3 — Dynamic fast-memory budget

Account for changing KV-cache pressure.

### A4 — Migration awareness

Include the cost of moving experts between tiers.

Only include later components if earlier experiments establish a meaningful need for them.

---

## 17. Expected Contributions

The project aims to produce:

### 1. Workload characterization

A study of how expert-access patterns change under concurrent MoE serving.

### 2. Memory-tiering analysis

A systematic comparison of fast-memory-only, naive overflow, frequency-based, existing activation-aware, and proposed policies.

### 3. Batch-aware placement policy

A memory-placement strategy based on aggregate concurrent expert demand.

### 4. CXL sensitivity study

Characterization of how latency, bandwidth, capacity, and contention affect MoE memory tiering.

### 5. Interactive visualization

A dashboard showing:

- expert popularity
- co-activation
- HBM residency
- CXL residency
- CXL traffic
- latency
- throughput
- placement changes

### 6. Architecture recommendations

Guidance on when CXL memory tiering is useful for MoE inference and when it is unlikely to help.

---

## 18. Risks and Mitigation

| Risk | Severity | Mitigation |
|---|---|---|
| No physical CXL hardware | High | Use CXL-aware simulation/modeling and clearly distinguish simulation from real hardware |
| Closely related CXL-MoE work already exists | High | Explicitly compare against closest work and focus novelty on verified gaps |
| Model-scale mismatch | Medium | Evaluate multiple feasible MoE configurations and avoid unsupported frontier-scale claims |
| High expert divergence | High | Treat divergence as an important evaluation regime; determine where no placement policy can avoid CXL traffic |
| Placement overhead | Medium | Begin with a near-linear greedy policy and measure its runtime |
| Host/device transfer bottlenecks | Medium | Measure transfer overhead and investigate asynchronous overlap if necessary |
| Scope creep | High | RQ1-RQ3 are the must-deliver core; RQ4-RQ6 are secondary |
| Simulator fidelity | High | Ground parameters in published CXL measurements and cross-check models where possible |

---

## 19. What We Are NOT Doing

To keep the project scientifically focused, the initial scope does **not** include:

- inventing a new CXL protocol
- building physical CXL hardware
- implementing an NDP accelerator
- assuming the RTX A6000 is a CXL device
- claiming that hot/cold expert placement itself is novel
- building a complete production-grade CXL runtime
- implementing multiple independent optimization algorithms simultaneously
- optimizing every possible memory consumer at once
- claiming arbitrary performance improvements before experiments

These may appear in related literature or future work, but they are not required for the core Nebula-MoE contribution.

---

## 20. Project Architecture

```text
                    +-----------------------+
                    |   MoE Inference App   |
                    +-----------+-----------+
                                |
                                v
                    +-----------------------+
                    |   Nebula Profiler     |
                    |                       |
                    | Routing / Memory Data |
                    +-----------+-----------+
                                |
                                v
                    +-----------------------+
                    | Workload Analyzer      |
                    |                       |
                    | Frequency             |
                    | Overlap               |
                    | Co-activation         |
                    | Batch composition     |
                    +-----------+-----------+
                                |
                                v
                    +-----------------------+
                    | Placement Optimizer    |
                    +-----------+-----------+
                                |
                  +-------------+-------------+
                  |                           |
                  v                           v
          +---------------+           +---------------+
          | Fast GPU      |           | CXL Memory    |
          | Memory        |           | Tier          |
          |               |           |               |
          | Hot experts   |           | Other experts |
          +---------------+           +---------------+
                                |
                                v
                    +-----------------------+
                    | Performance Analysis   |
                    |                       |
                    | Hit rate              |
                    | CXL traffic           |
                    | Latency               |
                    | Throughput            |
                    +-----------+-----------+
                                |
                                v
                    +-----------------------+
                    | Dashboard / Report     |
                    +-----------------------+
```

---

## 21. Proposed Repository Structure

```text
nebula-moe/
├── README.md
│
├── docs/
│   ├── problem_statement.md
│   ├── research_questions.md
│   ├── literature_review.md
│   ├── methodology.md
│   └── architecture.md
│
├── configs/
│   ├── models/
│   ├── workloads/
│   └── cxl/
│
├── src/
│   ├── profiler/
│   ├── workload/
│   ├── placement/
│   ├── simulator/
│   └── evaluation/
│
├── experiments/
│   ├── baselines/
│   ├── concurrency/
│   ├── coactivation/
│   ├── kv_pressure/
│   └── cxl_sensitivity/
│
├── scripts/
│   ├── setup/
│   ├── run/
│   └── analysis/
│
├── results/
│   ├── raw/
│   ├── processed/
│   └── figures/
│
├── dashboard/
│
├── tests/
│
└── requirements.txt
```

---

## 22. Development Workflow

The project is developed primarily on the remote A6000 workstation.

```text
Laptop
   |
   | SSH
   v
rtx-a6000-workstation
   |
   +-- Git repository
   +-- PyTorch
   +-- CUDA
   +-- MoE models
   +-- experiments
   +-- simulators
   +-- results
```

Antigravity/VS Code can be used over SSH for implementation.

The A6000 workstation is the source of truth for:

- code
- models
- experiments
- results
- simulation artifacts

---

## 23. Recommended Development Phases

### Phase 0 — Prerequisites

Learn:

- GPU memory
- GDDR/HBM
- memory bandwidth
- latency
- MoE
- expert routing
- KV cache
- batching
- memory tiering
- CXL
- CXL Type-3 memory
- CXL pooling
- CXL vs NDP

### Phase 1 — Literature

Read and understand the closest work on:

- MoE expert caching/offloading
- CXL + LLM inference
- CXL + MoE
- CXL memory pooling
- CXL memory characterization

### Phase 2 — MoE baseline

Run an open-source MoE model on the A6000 workstation.

Verify:

```text
model loads
        |
expert routing works
        |
routing traces collected
        |
memory usage measured
```

### Phase 3 — Baselines

Implement:

```text
HBM-only
Naive overflow
LFU/frequency
Existing activation-aware policy
Closest CXL-MoE baseline
```

### Phase 4 — Concurrent workloads

Introduce:

- multiple requests
- different batch sizes
- different expert overlap
- different workload distributions

### Phase 5 — Nebula placement policy

Implement aggregate-demand placement.

Then add co-activation only if justified.

### Phase 6 — CXL simulation

Introduce the CXL memory model and sweep:

- latency
- bandwidth
- capacity
- contention

### Phase 7 — Ablations

Determine which components actually matter.

### Phase 8 — Final evaluation

Generate:

- tables
- plots
- dashboard
- architecture diagrams
- report
- demo video

---

## 24. Success Criteria

The project should not be considered successful merely because the proposed method is faster.

A strong result would establish:

1. Concurrent serving creates a measurable expert-placement problem.
2. Existing single-request/static policies degrade under realistic concurrent workloads.
3. Aggregate batch information provides measurable benefit.
4. Co-activation either improves the policy or is shown not to be necessary.
5. The proposed policy has acceptable computational overhead.
6. The results remain meaningful under a range of CXL latency/bandwidth configurations.
7. The conclusions are supported by strong baselines and ablations.

A negative result can also be scientifically useful if it demonstrates:

> **Under the tested conditions, simple frequency-based placement is already sufficient.**

The objective is to discover and quantify the real systems behavior, not to manufacture a positive result.

---

## 25. Deliverables

The final Nebula submission is expected to include:

- HBM + CXL memory architecture model
- CXL-based Transformer/MoE workload analysis where applicable
- bandwidth, latency, and scalability evaluation
- memory-tiering strategy
- expert-placement strategy
- CXL memory expansion/pooling analysis where relevant
- HBM-only vs HBM+CXL evaluation
- simulation framework
- interactive dashboard/demo
- final architecture recommendations
- 10–12 page final report
- demo video

---

## 26. Final Research Position

The project should be framed conservatively.

We are **not** claiming:

> "CXL makes MoE inference faster."

We are investigating:

> **Under what workload and memory conditions does intelligent placement of MoE expert weights across fast GPU memory and CXL memory improve inference performance, and can concurrent batch-aware placement outperform existing single-request or static policies?**

The ultimate goal is to determine whether **workload-aware memory management** can make CXL a useful extension of the memory hierarchy for MoE inference.

---

## 27. Current Status

### Completed

- [x] Astera Nebula problem statement analyzed
- [x] Initial project direction selected
- [x] Literature-gap exploration performed
- [x] Primary research questions defined
- [x] Initial hypotheses defined
- [x] Baseline taxonomy defined
- [x] Experimental risks identified
- [x] A6000 + simulated CXL methodology established

### In progress

- [ ] Verify closest literature and research gap
- [ ] Learn required CXL/MoE fundamentals
- [ ] Select MoE workload/model
- [ ] Establish first inference baseline
- [ ] Collect expert-routing traces

### Planned

- [ ] Reproduce selected baselines
- [ ] Build concurrent workload generator
- [ ] Implement batch-aware placement
- [ ] Add co-activation analysis
- [ ] Integrate CXL memory simulation
- [ ] Run ablations
- [ ] Build dashboard
- [ ] Prepare final report
- [ ] Prepare demo video

---

## 28. Guiding Principle

> **Do not optimize what we have not measured.**

The project should progress from:

```text
Understand
   ↓
Measure
   ↓
Reproduce
   ↓
Characterize
   ↓
Identify failure
   ↓
Design
   ↓
Evaluate
   ↓
Conclude
```

Rather than:

```text
Invent algorithm
   ↓
Assume it is novel
   ↓
Build complicated system
   ↓
Find numbers supporting it
```

The goal of Nebula-MoE is not merely to build a system.

It is to produce a **credible, reproducible systems research result** that explains when and why CXL-based memory tiering can help MoE inference.
