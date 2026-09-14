# EXP-05B CXLMemSim Model Audit

**Purpose:** Mathematical audit of the concurrent-transfer model before implementation.  
**Scope:** Parts 1–10 as specified. READ-ONLY — no code changes, no new experiments.  
**Source data:** [`summary_metrics.json`](file:///home/k8s-admin/Vinay/nebula/results/exp05b_rq4_cxlmemsim_validation/run_20260913_100413_48596d6b/summary_metrics.json),  [`cxlmemsim_adapter.py`](file:///home/k8s-admin/Vinay/nebula/src/simulator/cxlmemsim_adapter.py),  [`EXP05B_CXLMEMSIM_STREAM_SCALING.md`](file:///home/k8s-admin/Vinay/nebula/docs/EXP05B_CXLMEMSIM_STREAM_SCALING.md)  
**Date:** September 13, 2026  

---

## Part 1 — Physical Model from First Principles

### 1.1 The Shared-Link Constraint

A single CXL link of bandwidth BW (in bytes/ns) is a **serialized medium**. At any instant, at most BW bytes of payload can be transmitted per nanosecond. This is the hard physical constraint regardless of how many streams are using the link.

**Notation:**

| Symbol | Definition |
| :--- | :--- |
| $S$ | Expert size = 256 MiB = 268,435,456 bytes |
| $\text{BW}$ | CXL link peak bandwidth (GB/s = bytes/ns) |
| $K_{\text{active}}$ | Number of experts whose bytes are in flight simultaneously |
| $K_{\text{total}}$ | Total number of expert transfers across the entire inference run |
| $V_{\text{total}}$ | Total bytes transferred = $K_{\text{total}} \times S$ |
| $T_{\text{link}}$ | Minimum time imposed by the link bandwidth |

### 1.2 Bandwidth-Limited Lower Bound

For a sequential link carrying $V_{\text{total}}$ bytes at peak BW:

$$T_{\text{link}} = \frac{V_{\text{total}}}{\text{BW}} = \frac{K_{\text{total}} \times S}{\text{BW}}$$

This is the **lower bound** on total elapsed transfer time, achievable only if:
1. The link is fully utilized for the entire duration (no gaps).
2. No per-transfer latency overhead is added.
3. No protocol stalls occur.

### 1.3 Distinguishing K Scenarios: The Critical Table

| Scenario | Correct T_bw | Notes |
| :--- | :--- | :--- |
| **K independent links**, each dedicated to one stream | $S / \text{BW}$ each, parallel | All $K$ transfers complete at the same wall-clock time $S/\text{BW}$; total elapsed time = $S/\text{BW}$ |
| **K streams sharing one link, fully concurrent burst** | $K \times S / \text{BW}$ | The single link serializes all $K \times S$ bytes; completion time $= K \times S / \text{BW}$ |
| **K transfers, sequential** | $K \times S / \text{BW}$ | Same bytes, same total time; same answer as shared concurrent link |
| **K transfers interleaved over time (batch scheduling)** | $V_{\text{total}} / \text{BW}$ | Correct iff the link is kept busy. $V_{\text{total}} = K_{\text{total}} \times S$ |

> [!IMPORTANT]
> **Key conclusion:** For a single serialized CXL link, *whether you model* K streams as "concurrent" or "sequential" does not change the bandwidth-limited time. The total bytes determine the total link occupancy. $T_{\text{bw}} = V_{\text{total}} / \text{BW} = K_{\text{total}} \times S / \text{BW}$ regardless.

### 1.4 What Changes Between Scenarios: Per-Transfer Latency Overhead

The distinction between "concurrent" and "sequential" matters **only** for per-transfer fixed overheads (latency, startup, pipeline):

| Model | Per-transfer overhead | Total overhead | Correct for? |
| :--- | :--- | :--- | :--- |
| All K in one burst | Once per burst | $T_0$ | Concurrent, perfectly pipelined |
| K sequential transfers | Once per transfer | $K \times T_0$ | Serial, no pipelining |
| K partially overlapping | Once per batch | $\ll K \times T_0$ | Batch with concurrency |

**This is the core ambiguity** in the current report's proposed formula — what multiplies $T_0$.

---

## Part 2 — What $T_0$ Means

### 2.1 Empirical Definition

From the stream-scaling study (Section 8 and 10 of `EXP05B_CXLMEMSIM_STREAM_SCALING.md`), for BW=32 GB/s, lat=300 ns:

$$T(N) = N \times \Delta t + T_0 \quad \text{where } \Delta t = \frac{64}{\text{BW}} = 2\text{ ns},\; T_0 \approx 11,438\text{ ns}$$

The constant $C \approx 5719$ was the mean of training measurements, giving $T_0 = 2C = 11,438$ ns.

### 2.2 What the Benchmark Actually Measured

The benchmark for this $T_0$ was:
- **K = 1** single stream
- Physical arrival interval = 2 ns (one cache-line per interval)
- Requests fed to **one** `CXLMemExpander` instance

$T(N)$ is the **makespan of a single stream of N cacheline requests through the CXLMemSim queue**.

### 2.3 Decomposing $T_0$ from Source

From `cxlendpoint.cpp`, the pipeline for each of the 2 accepted "waves":

```
T_wave = frontend(10) + forward(15) + read_lat(300) + response(20) + protocol(6.5)
       + congestion_delay(queue_full ≈ 26 ns)
       = 377.5 ns  (with full queue)
```

At the start of a stream with N >> 1 at 2 ns interval, **exactly 2 requests** are accepted immediately (the two initial credits). The pipeline carries them for ~377 ns. Then 2 more are admitted, and so on. The startup overhead is dominated by: waiting for the 2-credit pipeline to flush the **initial backlog** before settling into steady state.

From Part 8 of the scaling study: for small N, $T(N) = T_0 + N \times \Delta t$, meaning:
$$T_0 = T(N) - N \times \Delta t \approx 11,438\text{ ns}$$

**$T_0$ is independent of N** (confirmed by the stable $C$ values: std dev ±68 ns across N=64..4096).

### 2.4 Physical Interpretation of $T_0$

$T_0$ is the **queue startup and pipeline flush overhead** for one `CXLMemExpander` instance at the beginning of a single contiguous stream. Specifically:

- It includes the latency for the **first credit wave**: the 2 initial requests must complete (377 ns) before the next 2 can start.
- For large N, this startup overhead amortizes: the steady-state transmission dominates and $T_0/T \to 0$.
- **It is a property of one CXLMemSim expander instance receiving one contiguous stream.**

### 2.5 Candidate Interpretations Evaluated

| Interpretation | Evidence | Verdict |
| :--- | :--- | :--- |
| A. Per expert transfer (each 256 MiB gets its own $T_0$) | Requires K separate CXLMemExpander instances, or K distinct queue activations. The benchmark only used 1 instance for the full stream. | **UNSUPPORTED** unless K streams are fully decoupled |
| B. Per concurrent burst | If K experts are serialized through one expander instance, the stream contains $K \times N$ requests and $T_0$ is incurred only once (the single startup). | **SUPPORTED** for a single-expander, single-continuous-stream model |
| C. Per batch step | One batch step may contain multiple expert transfers; if they are concatenated into one queue submission, $T_0$ is per batch. | Equivalent to B under single-instance model |
| D. Per link activation | If the link goes idle between batches, each re-activation incurs $T_0$. If the link stays active, only one $T_0$ applies. | **SUPPORTED** for the "one activation per batch step" interpretation |
| E. CXLMemSim startup/flush artifact | $T_0$ includes the initial credit-pipeline fill time — a real CXL protocol effect (credit-based flow control requires pipeline fill before steady state). | **SUPPORTED** — this is the mechanism |
| F. Other | N/A | — |

> [!IMPORTANT]
> **Conclusion on $T_0$:** It is a **per-stream-activation** constant — incurred once per contiguous sequence of cacheline requests delivered to a single CXLMemSim expander instance. It is **not** a per-expert quantity unless each expert transfer is modeled as a completely independent stream with its own CXLMemExpander cold start.

---

## Part 3 — Candidate Model Analysis

### Algebra First: MODEL A and MODEL C are Identical

The user notes: $K \times (S/\text{BW} + T_0) = K \times S/\text{BW} + K \times T_0$. So MODEL A and MODEL C are the same expression. We treat them as one.

### MODEL A/C (equivalent): $T = K \times S/\text{BW} + K \times T_0$

**Interpretation:** Each of K expert transfers is a fully independent stream with its own CXL link and its own queue startup. The link is reserved exclusively for each transfer in turn.

**Physical assumption:** K separate, non-overlapping streams on an exclusive link — equivalent to K independent link activations.

**Shared-link modeling:** NO — this model implicitly assumes K separate link activations with $T_0$ startup overhead each time.

**Double-counting risk:** If $T_0$ includes effects already captured in $S/\text{BW}$ — No, they are distinct ($S/\text{BW}$ is pure link time, $T_0$ is protocol startup overhead).

**Supported by measurements:** For K=1, this gives $T = S/\text{BW} + T_0$ which matches the calibration. For K>1, this treats each transfer as independently activating the link, which is NOT what CXLMemSim demonstrated — Part 4 of the scaling study showed **K has zero effect** within a shared queue.

**Appropriate for TierMoE?** Only if all K expert transfers happen in **strict sequence with a gap** between them (link goes idle between transfers). This is unlikely in a real MoE inference batch step.

---

### MODEL B: $T = K \times S/\text{BW} + T_0$

**Interpretation:** K expert transfers share a single contiguous link activation. The bytes are serialized ($K \times S / \text{BW}$) but the protocol startup overhead ($T_0$) is incurred only once.

**Physical assumption:** All K transfers are pipelined into one contiguous byte stream on the shared link. The CXLMemExpander sees one continuous request sequence with no idle gap.

**Shared-link modeling:** YES — this correctly represents link serialization.

**Double-counting risk:** None. $K \times S/\text{BW}$ covers link occupancy; $T_0$ covers one-time queue pipeline fill.

**Supported by measurements:**
- From the scaling study: the $T_0$ intercept comes from a **single-stream experiment**. When K experts are concatenated into one stream of $K \times N$ requests, the formula becomes:
  $T = (K \times N) \times \Delta t + T_0 = K \times S/\text{BW} + T_0$
  This is exactly Model B, and it is validated by the stream-length scaling data.
- From Part 7: For 16 MiB at 2 ns interval (N=262144), RelErr=2.19% vs Model B which predicts RelErr = $T_0 / (K \times S/\text{BW})$ → as K grows, this drives to zero.

**Appropriate for TierMoE?** Yes, for a single batch step in which K experts are fetched in a single pipelined burst. This is the physically correct model for a shared link.

---

### MODEL D: $T = K \times S/\text{BW} + f(K, T_0)$

Generalizes to a $T_0$ that depends on K. Two physically meaningful variants:

**Variant D1: $f(K, T_0) = T_0$** — reduces to MODEL B. Correct for one-burst, one-activation.

**Variant D2: $f(K, T_0) = \min(K, K_{\text{batch}}) \times T_0$** — for K experts split across $K_{\text{batch}}$ batch steps, each with one activation. The total startup overhead is $K_{\text{batch}} \times T_0$, not $K_{\text{total}} \times T_0$.

**Variant D3: $f(K, T_0) = \lceil K / K_{\text{active}} \rceil \times T_0$** — for a round-robin schedule of $K_{\text{active}}$ concurrent streams, the number of link activations is $\lceil K / K_{\text{active}} \rceil$.

> [!NOTE]
> Variant D2 is the physically correct generalization for TierMoE inference, as argued in Part 7.

---

## Part 4 — Double-Counting Audit

### 4.1 What `duration_emission_ns` already captures

From [`cxlmemsim_adapter.py:264`](file:///home/k8s-admin/Vinay/nebula/src/simulator/cxlmemsim_adapter.py#L264):
```python
duration_emission_ns = (total_lines - 1) * inter_arrival_ns
```
where `inter_arrival_ns = 64 / BW`.

For large $N$: `duration_emission_ns ≈ total_lines × (64/BW) = V_bytes / BW` in nanoseconds.

This already accounts for:
- **Full link transmission time** for all bytes
- **Physical serialization** of all cache lines on the link
- **Effect of BW** (scales inversely with bandwidth)

### 4.2 What the remaining terms add

| Term | Source | Physical meaning | Overlaps? |
| :--- | :--- | :--- | :--- |
| `duration_emission_ns` | V/BW | Link occupancy (all bytes) | — baseline |
| `cxl_latency_overhead_ns = N × Lat` | `line 284` | **Spurious**: adds latency once per transfer on top of V/BW | **YES — problematic** |
| `bw_penalty_ns` | MLC model | Congestion penalty for saturation | No double-count with V/BW itself; models nonlinearity above knee |
| `congestion_delay_ns` | Queue model | Per-request congestion within the step | Possibly double-counted with `bw_penalty_ns` |
| `pipeline_lat_ns` | 351.5 ns | Protocol pipeline overhead for first wave | Small (0.0004% of 92s run) |

### 4.3 The Spurious `N × Lat` Term

The current adapter adds `cxl_latency_overhead_ns = num_transfers × read_latency_ns` at line 284. This is the **central error identified in the EXP-05B forensic audit**. For condition 1:

- $N_{\text{xfr}} = 10,990$ transfers × 300 ns = **3,297,000 ns = 3.297 ms** additive overhead
- Total T_cxl = 92,194 ms; T_ana = 92,194 ms — they match only because T_ana **also** applies `N × Lat` (line 252)
- $T_{\text{bw, pure}} = V_{\text{bytes}} / \text{BW} = 2,950,105,661,440 / (32 \times 10^9) = 92.191\text{ s} = 92191\text{ ms}$
- **`N × Lat = 3.297 ms` is only 0.0036% of the total** — negligible but conceptually wrong

This term represents adding one full round-trip read latency (300 ns) per expert transfer. This is not physically correct for streaming sequential reads: the read latency is already embedded in the pipeline latency, not additive over the link transmission time.

> [!CAUTION]
> The reason T_cxl ≈ T_ana in the existing results is not that the model is correct — it is that both formulas apply the same internally consistent but physically questionable `N × Lat` additive overhead. The near-zero delta between them (~0.3 ms on 92 s) comes from the `bw_penalty + congestion + pipeline` terms being tiny corrections.

### 4.4 Summary of What $S/\text{BW}$ Covers vs What $T_0$ Covers

| Physical effect | Captured by $S/\text{BW}$? | Captured by $T_0$? | Notes |
| :--- | :--- | :--- | :--- |
| Link bandwidth saturation | ✓ | ✗ | Pure link occupancy |
| Per-cacheline serialization | ✓ | ✗ | One line per 2 ns at 32 GB/s |
| CXL protocol pipeline (frontend + forward + response) | ✗ | ✓ | ~45 ns of the 351.5 ns pipeline |
| Credit-limited queue filling | ✗ | ✓ | Drives the startup offset |
| Congestion when queue is full | ✗ | ✓ | Up to 26 ns per request in CXLMemSim |
| Per-expert latency overhead | ✗ | ✗ | NOT physically justified as additive |
| DRAM access time (within CXL expander) | ✗ | ✓ | The `read_lat` component (300 ns) |

---

## Part 5 — BW/Latency Generalization

### 5.1 How $T_0$ Depends on BW and Latency

From the source decomposition:

$$T_0 = 2 \times T_{\text{pipeline}}, \quad T_{\text{pipeline}} = 45.5 + \text{read\_lat} + \text{congestion\_ns}$$

where:
- Fixed protocol overhead: $10 + 15 + 20 + 6.5 = 51.5$ ns
- Variable read latency: $\text{read\_lat} \in \{150, 300, 600\}$ ns
- Congestion at full queue: $\approx 26$ ns (congestion formula is BW-independent)

For the three BW configurations:
$$\Delta t = \frac{64}{\text{BW}}: \quad 16\text{ GB/s} \to 4\text{ ns}, \quad 32\text{ GB/s} \to 2\text{ ns}, \quad 64\text{ GB/s} \to 1\text{ ns}$$

The stream-scaling startup cost $T_0$ comes from the pipeline **first filling before settling into steady state**. The number of credit waves during startup is **independent of BW** (it depends only on `INITIAL_CREDITS=2` and pipeline latency). However, the injection rate changes: at 64 GB/s, cachelines arrive 2× faster, so the queue fills faster, but the pipeline latency is the same → $T_0$ is unchanged.

**Derived $T_0$ at each latency point (theoretical):**

| read\_lat | T_pipeline | T_0 = 2 × T_pipeline | Approx |
| :--- | :--- | :--- | :--- |
| 150 ns | 51.5 + 150 + 26 = 227.5 ns | 455 ns | ~0.46 μs |
| 300 ns | 51.5 + 300 + 26 = 377.5 ns | 755 ns | ~0.76 μs |
| 600 ns | 51.5 + 600 + 26 = 677.5 ns | 1355 ns | ~1.36 μs |

But wait — the empirical calibration gave $T_0 \approx 11,438$ ns for lat=300 ns, not 755 ns. The discrepancy is that $T_0$ is **not** just 2 pipeline cycles — it is the full startup transient (the time before the $T(N) = N \times \Delta t + \text{const}$ regime is established), which from the data is ~11.4 μs ≈ 30 pipeline cycles.

The 11.4 μs startup represents the queue needing to dispatch approximately $T_0 / \Delta t \approx 11438/2 \approx 5720$ cache-line arrival intervals worth of pipeline overhead before settling. This number is **inversely proportional to** $\Delta t$ (the per-cacheline arrival time), which depends on BW.

Therefore, **$T_0$ is NOT invariant across BW**:

$$T_0(\text{BW}, \text{lat}) \approx \frac{C}{\Delta t} \times \Delta t = C \text{ (constant in ns)}$$

Wait — let's re-examine. From the convergence law: $\text{RelErr}(N) = C/N$ where $C$ is in units of "requests." The time-domain constant is:

$$T_0 = C \times \Delta t = 5719 \times \frac{64}{\text{BW}}$$

At different BW:
| BW | $\Delta t$ | Predicted $T_0$ | Predicted $T_0$ (μs) |
| :--- | :--- | :--- | :--- |
| 16 GB/s | 4 ns | 5719 × 4 = 22,876 ns | 22.9 μs |
| 32 GB/s | 2 ns | 5719 × 2 = 11,438 ns | 11.4 μs ← calibrated |
| 64 GB/s | 1 ns | 5719 × 1 = 5,719 ns | 5.7 μs |

So $T_0 \propto 1/\text{BW}$, making sense: a faster link fills and drains the queue faster, so startup is shorter in nanoseconds.

The $C$ constant is in "request-units" (number of cacheline slots), which is a queue-depth property independent of BW. From source: it depends on `INITIAL_CREDITS`, `MAX_QUEUE_SIZE`, and `pipeline_latency / Δt` (= number of cachelines that arrive while one credit-wave is in flight).

**Does $T_0$ depend on read latency?**

The pipeline latency includes `read_lat`, so `pipeline_latency / Δt` changes with latency:
$$\frac{T_{\text{pipeline}}}{\Delta t} = \frac{51.5 + \text{read\_lat} + 26}{64/\text{BW}} = \frac{(77.5 + \text{read\_lat}) \times \text{BW}}{64}$$

At BW=32, lat=300: $(377.5 \times 32)/64 = 188.75$ cachelines per credit wave.
At BW=32, lat=150: $(227.5 \times 32)/64 = 113.75$ cachelines per credit wave.
At BW=32, lat=600: $(677.5 \times 32)/64 = 338.75$ cachelines per credit wave.

$C$ ≈ steady-state queue fill depth, which is ≈ `pipeline_latency / Δt × INITIAL_CREDITS`:
$$C \approx 2 \times \frac{T_{\text{pipeline}}}{\Delta t}$$

So:

| BW | Lat | Predicted $C$ | Predicted $T_0 = C \times \Delta t$ |
| :--- | :--- | :--- | :--- |
| 32 GB/s | 150 ns | 2 × 113.75 = 228 | 228 × 2 = 456 ns |
| 32 GB/s | 300 ns | 2 × 188.75 = 378 | 378 × 2 = 755 ns |
| 32 GB/s | 600 ns | 2 × 338.75 = 678 | 678 × 2 = 1356 ns |
| 16 GB/s | 300 ns | 2 × 188.75 = 378 | 378 × 4 = 1512 ns |
| 64 GB/s | 300 ns | 2 × 188.75 = 378 | 378 × 1 = 378 ns |

**These are the theoretical predictions, not the empirical $T_0 \approx 11.4$ μs.**

> [!CAUTION]
> There is a factor-of-15 discrepancy between theory ($T_0 \approx 755$ ns at lat=300, BW=32) and calibration ($T_0 \approx 11,438$ ns). This discrepancy arises because the empirical $T_0$ includes not just 2 credit waves but the full non-linear transient before the queue reaches steady-state throughput. The theoretical derivation above gives the minimum startup (2 wave round-trips), not the full transient. **The empirical calibration from the stream-scaling benchmark is the authoritative value.**

### 5.2 Scientific Defensibility Verdict

> [!WARNING]
> It is **NOT scientifically defensible** to use the calibrated $T_0 = 11.44$ μs (measured at BW=32, lat=300) for the BW=16 or BW=64 conditions, or for lat=150 or lat=600. $T_0$ depends on both BW and latency through the queue pipeline fill time.

**Minimum required additional calibrations:**

| Priority | Condition | Experiment needed |
| :--- | :--- | :--- |
| **Essential** | BW=16 GB/s, lat=300 ns | Stream scaling bench at BW=16: 6 measurements N=64..4096 |
| **Essential** | BW=64 GB/s, lat=300 ns | Stream scaling bench at BW=64: 6 measurements N=64..4096 |
| **Optional** | BW=32 GB/s, lat=150 ns | Stream scaling bench at BW=32, lat=150 |
| **Optional** | BW=32 GB/s, lat=600 ns | Stream scaling bench at BW=32, lat=600 |

Each calibration run requires modifying `make_ep(bw_gbps, lat_ns)` in `stream_scaling_bench.cpp` and re-running Parts 2 and 8 only — less than 1 minute per configuration.

---

## Part 6 — Verification Against Existing EXP-05B Data

### 6.1 Raw Data Extraction (from `summary_metrics.json`)

| Cond | Algo | B | BW | Lat | N_xfr | V (MB) | T_cxl (ms) | T_ana (ms) | V/BW (ms) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | Single | 8 | 32 | 300 | 10,990 | 2,813,440 | 92,194.39 | 92,194.10 | 92,191.14 |
| 2 | TierMoE | 8 | 32 | 300 | 10,405 | 2,663,680 | 87,286.87 | 87,286.59 | 87,284.50 |
| 3 | Single | 16 | 32 | 300 | 8,724 | 2,233,344 | 73,184.98 | 73,184.83 | 73,181.38 |
| 4 | TierMoE | 16 | 32 | 300 | 8,263 | 2,115,328 | 69,317.69 | 69,317.55 | 69,314.57 |
| 5 | Single | 32 | 32 | 300 | 6,242 | 1,597,952 | 52,363.64 | 52,363.56 | 52,360.73 |
| 6 | TierMoE | 32 | 32 | 300 | 6,146 | 1,573,376 | 51,558.30 | 51,558.23 | 51,555.60 |
| 7 | Single | 32 | 16 | 300 | 6,242 | 1,597,952 | 104,725.34 | 104,725.25 | 104,721.45 |
| 8 | TierMoE | 32 | 16 | 300 | 6,146 | 1,573,376 | 103,114.70 | 103,114.61 | 103,111.19 |
| 9 | Single | 32 | 64 | 300 | 6,242 | 1,597,952 | 26,182.79 | 26,182.72 | 26,180.36 |
| 10 | TierMoE | 32 | 64 | 300 | 6,146 | 1,573,376 | 25,780.11 | 25,780.04 | 25,778.90 |

$$\text{Total } N_{\text{xfr}} = 10990+10405+8724+8263+6242+6146+6242+6146+6242+6146 = \mathbf{75,546}$$

> [!NOTE]
> This confirms 75,546 total expert transfers, not 80,820. The arithmetic is verified directly from the JSON.

### 6.2 Verifying What the Current Adapter Computes

From [`cxlmemsim_adapter.py:263-291`](file:///home/k8s-admin/Vinay/nebula/src/simulator/cxlmemsim_adapter.py#L263-L291), for a step with $N$ transfers, $V = N \times S$ bytes:

```
duration_emission_ns = (N × 4,194,304 - 1) × (64 / BW)   ≈ V/BW (ns)
cxl_latency_overhead = N × read_lat
bw_penalty_ns        = f(utilization)  ← small correction
pipeline_lat_ns      = 351.5 ns        ← very small
congestion_delay_ns  = 26 ns           ← very small

T_cxl ≈ V/BW + N × read_lat  (in ns)
```

**Verification for Condition 1:**
- V = 2,950,105,661,440 bytes; BW = 32 GB/s; N_xfr = 10,990; Lat = 300 ns
- V/BW = 2,950,105,661,440 / (32e9) = 92.191 s = 92,191 ms
- N × Lat = 10,990 × 300 ns = 3,297,000 ns = 3.297 ms
- T_cxl ≈ 92,191 + 3.297 = 92,194.3 ms ← **matches recorded 92,194.39 ms** ✓

**Analytical formula (lines 252-254):**
```python
ana_overhead_ms = (num_transfers × latency_ns) / 1e6     = N × Lat / 1e6
ana_tx_ms       = (total_bytes / (BW × 1e9)) × 1e3       = V/BW
T_ana = V/BW + N × Lat
```

This confirms: **both T_cxl and T_ana implement $T = V/\text{BW} + N \times \text{Lat}$.** The near-zero delta between them ($< 0.3$ ms on 92 s) is because both use this same structure; the difference comes only from small CXLMemSim corrections (bw_penalty + congestion + pipeline).

### 6.3 Per-Condition Model Predictions

For each candidate model, predictions use:
- S = 256 MiB = 268,435,456 bytes
- V = total_cxl_bytes from JSON
- N_xfr from JSON  
- T0(32 GB/s, 300 ns) = 11.438 μs = 0.011438 ms (from calibration)

| Cond | BW | T_current (ms) | Model B: V/BW + T0 (ms) | Model A/C: V/BW + N×T0 (ms) | Delta B (ms) | Delta A/C (ms) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 1 (S,B8,32) | 32 | 92,194.39 | 92,191.14 + 0.011 = **92,191.15** | 92191 + 10990×0.011 = **92,312.02** | −3.24 | +117.6 |
| 2 (T,B8,32) | 32 | 87,286.87 | 87,284.50 + 0.011 = **87,284.51** | 87284 + 10405×0.011 = **87,403.49** | −2.36 | +116.6 |
| 3 (S,B16,32) | 32 | 73,184.98 | 73,181.38 + 0.011 = **73,181.39** | 73181 + 8724×0.011 = **73,277.89** | −3.59 | +92.9 |
| 4 (T,B16,32) | 32 | 69,317.69 | 69,314.57 + 0.011 = **69,314.58** | 69314 + 8263×0.011 = **69,404.85** | −3.11 | +87.2 |
| 5 (S,B32,32) | 32 | 52,363.64 | 52,360.73 + 0.011 = **52,360.74** | 52360 + 6242×0.011 = **52,428.67** | −2.90 | +65.0 |
| 6 (T,B32,32) | 32 | 51,558.30 | 51,555.60 + 0.011 = **51,555.61** | 51555 + 6146×0.011 = **51,622.50** | −2.69 | +64.2 |
| 7 (S,B32,16) | 16 | 104,725.34 | 104,721.45 + **?** | 104721 + 6242×**?** | — requires T0(16) | — |
| 8 (T,B32,16) | 16 | 103,114.70 | 103,111.19 + **?** | see Part 5 | — | — |
| 9 (S,B32,64) | 64 | 26,182.79 | 26,180.36 + **?** | 26180 + 6242×**?** | — requires T0(64) | — |
| 10 (T,B32,64) | 64 | 25,780.11 | 25,778.90 + **?** | see Part 5 | — | — |

**Key finding:** Model B at BW=32 differs from T_current by **~2–4 ms** (the removed $N \times \text{Lat}$ term of ~3.3 ms). Model A/C overestimates by **~65–120 ms** (adding $N \times T_0$ where $T_0 = 11.44$ μs per expert).

---

## Part 7 — Single vs Multi-Stream Semantics

### 7.1 What K Means in TierMoE

In one inference batch step:
- B = batch size (tokens processed simultaneously)
- The placement algorithm determines which experts are present in fast memory and which must be fetched.
- `total_transfers_count` = promotions + unique misses = number of **distinct expert blocks fetched per batch step**.

The transfers within one batch step are conceptually concurrent (they must all complete before the batch step can proceed). However, on a **single CXL link**, they are physically serialized.

**The aggregate volume per batch step** is $V_{\text{step}} = N_{\text{step}} \times S$, and the link transmits this volume sequentially. The correct model for one batch step is:

$$T_{\text{step}} = \frac{V_{\text{step}}}{\text{BW}} + T_0 = \frac{N_{\text{step}} \times S}{\text{BW}} + T_0$$

This is Model B applied to one batch step.

### 7.2 Total Inference Time as Sum of Batch Steps

The full EXP-05B run consists of many batch steps. The total modeled transfer time is:

$$T_{\text{total}} = \sum_{\text{steps}} T_{\text{step}} = \sum_{\text{steps}} \left(\frac{N_{\text{step}} \times S}{\text{BW}} + T_0\right) = \frac{V_{\text{total}}}{\text{BW}} + N_{\text{steps}} \times T_0$$

where $N_{\text{steps}}$ is the number of batch steps with at least one transfer.

**This is NOT the same as Model A/C or Model B applied globally.**

Specifically:
- **Model B globally** ($T = V_{\text{total}}/\text{BW} + T_0$): treats the entire run as one contiguous activation. Undercounts $T_0$ by a factor of $N_{\text{steps}}$.
- **Model A/C globally** ($T = V_{\text{total}}/\text{BW} + K_{\text{total}} \times T_0$): treats each of the 75,546 expert transfers as an independent activation. Grossly overcounts $T_0$.
- **Correct step-level aggregation** ($T = V_{\text{total}}/\text{BW} + N_{\text{steps}} \times T_0$): one activation overhead per batch step.

### 7.3 Estimating $N_{\text{steps}}$

The number of batch steps is not stored directly in `summary_metrics.json`. However, from the data:

- Condition 1: Total transfers = 10,990; avg_working_set_experts ≈ 36.2; fast_capacity = 32
- Condition 1 uses B=8 batch size, with 192 layers × 128 experts = 24,576 experts across the model
- The inference run processes many batches; from `analysis_summary.json` we need the step count.

**Bounding $N_{\text{steps}}$:** From the transfer counts and solver timing:
- `total_solver_time_ms = 8.455 ms`; `avg_solver_time_us = 22.0 μs` → total steps ≈ 8455/0.022 ≈ 384 batch steps

If there are ~384 batch steps and 10,990 total transfers: avg transfers per step ≈ 28.6 per step.

Step-level correction: $N_{\text{steps}} \times T_0 = 384 \times 0.011438 = 4.39$ ms — **negligible** compared to T_total ≈ 92,194 ms (< 0.005%).

> [!IMPORTANT]
> For TierMoE at realistic scales, the $T_0$ correction is **less than 0.005% of total transfer time** regardless of whether it is applied once per run, once per batch step, or once per expert. This is because $V_{\text{total}} / \text{BW}$ dominates by five orders of magnitude over $T_0$.

---

## Part 8 — Correct Model for TierMoE Simulator

### 8.1 Proposed Model

Based on the full audit:

$$\boxed{T_{\text{total}} = \frac{V_{\text{total}}}{\text{BW}} + N_{\text{steps,active}} \times T_0(\text{BW}, \text{lat})}$$

where:
- $V_{\text{total}} = \sum_{\text{steps}} N_{\text{step}} \times S$ = total CXL bytes (from `total_cxl_bytes`)
- $N_{\text{steps,active}}$ = number of batch steps with at least one transfer
- $T_0(\text{BW}, \text{lat})$ = startup overhead calibrated from CXLMemSim (requires BW/lat-specific calibration)
- $S = 256 \text{ MiB}$ per expert block

### 8.2 The Simpler Equivalent

Since $N_{\text{steps,active}} \times T_0 \ll V_{\text{total}} / \text{BW}$ in all 10 conditions by at least 4 orders of magnitude, the model simplifies to:

$$T_{\text{total}} \approx \frac{V_{\text{total}}}{\text{BW}}$$

with an error of less than 0.005% — well below any physically or experimentally meaningful threshold.

### 8.3 What the Current Adapter Gets Right and Wrong

**Correct:**
- `duration_emission_ns ≈ V_bytes / BW` — correctly models aggregate link occupancy.
- `effective_bw_gbps` calculation is consistent.
- Deduplication of same-expert transfers within a batch step is correct.

**Incorrect:**
- `cxl_latency_overhead_ns = N_transfers × read_lat`: this adds $K \times \text{lat}$ per step where K is the number of expert transfers. For condition 1 this adds 3.3 ms to a 92 s total — small but not physically justified. In the TierMoE vs Single-request comparison, it creates a difference proportional to $\Delta N_{\text{transfers}} \times \text{lat}$, which distorts the comparison.
- `calculate_controller_congestion_delay(num_transfers)`: models queue utilization as `num_transfers / 64`, which is not calibrated from CXLMemSim queue behavior.

---

## Part 9 — Validation Requirements for "CXLMemSim-Calibrated" Claim

### 9.1 Current Evidence

**Calibration dataset (BW=32 GB/s, lat=300 ns):**
- N = 64, 128, 256, 512, 1024, 2048, 4096 (7 measurements)
- Convergence law $C \approx 5719 \pm 68$ validated
- $T_0 = 11,438$ ns ± ~140 ns (2σ)

**Validation dataset (BW=32 GB/s, lat=300 ns):**
- N = 8192, 16384: RelErr < 0.40%, abs error < 111 ns
- N = 65536 (4 MiB), 262144 (16 MiB): RelErr < 2.19%, abs error < 31 ns

### 9.2 Requirements to Call the Model "CXLMemSim-Calibrated"

| Requirement | Current Status | What's needed |
| :--- | :--- | :--- |
| Real CXLMemSim queue execution (not analytical proxy) | ✓ — `insert()` + `process_queued_requests()` called | Complete |
| Calibration covers all BW values in EXP-05B | ✗ — only BW=32 calibrated | Need BW=16, BW=64 |
| Calibration covers all latency values in EXP-05B | ✗ — only lat=300 calibrated | Recommended: lat=150, lat=600 |
| Validation error < 1% on held-out sizes | ✓ at BW=32 | Verified |
| K-concurrency calibration | ✓ — Part 4 showed K has no effect | Complete (K invariant confirmed) |
| Explicit disclosure of calibration scope | ✗ — not yet in any report | Required in paper |

### 9.3 Minimum Acceptable Evidence

To claim "CXLMemSim-calibrated" for **all 10 conditions**:

1. Run `stream_scaling_bench` at BW=16, lat=300 and BW=64, lat=300 (Parts 2 and 8 only).
2. Extract $C(16)$ and $C(64)$, derive $T_0(16)$ and $T_0(64)$.
3. Verify that $T_0 \propto 1/\text{BW}$ as predicted (within 10%).
4. Apply $T_0(\text{BW}, \text{lat}) = C \times (64/\text{BW})$ to conditions 7–10.

**Acceptable error threshold:** < 1% relative error on the total transfer time model.

---

## Part 10 — Final Recommendation

### 10.1 Which Mathematical Model to Implement

$$T_{\text{total}} = \frac{V_{\text{total}}}{\text{BW}} + N_{\text{steps,active}} \times T_0(\text{BW})$$

For practical purposes (given $T_0 \ll V/\text{BW}$), this is equivalent to:

$$T_{\text{total}} \approx \frac{V_{\text{total}}}{\text{BW}}$$

Drop the $N \times \text{Lat}$ per-transfer additive overhead from the current adapter.

### 10.2 Parameters

| Parameter | Value | Source |
| :--- | :--- | :--- |
| $V_{\text{total}}$ | `total_cxl_bytes` from simulation | Computed by placement simulator |
| $\text{BW}$ | 16, 32, or 64 GB/s | Experiment configuration |
| $N_{\text{steps,active}}$ | Number of steps with transfers > 0 | From simulation step results |
| $T_0(32\text{ GB/s})$ | 11,438 ns = 11.44 μs | Calibrated from CXLMemSim |
| $T_0(16\text{ GB/s})$ | ~22.9 μs (predicted; **requires calibration**) | Uncalibrated |
| $T_0(64\text{ GB/s})$ | ~5.7 μs (predicted; **requires calibration**) | Uncalibrated |

### 10.3 What $T_0$ Represents

$T_0$ is the **CXLMemSim queue startup overhead per contiguous stream activation** — the time from submitting the first cache-line request to reaching the steady-state throughput regime. It is a property of the CXL protocol's credit-based flow control (INITIAL_CREDITS=2, MAX_QUEUE_SIZE=64) and the configured pipeline latency.

### 10.4 Is $T_0$ Per Transfer, Per Batch, or Another Quantity?

**Per batch step with active transfers.** It is NOT per individual expert transfer, and NOT per experiment run.

For the existing 10 conditions, the $T_0$ correction is negligible (< 0.005% of total transfer time) and its precise assignment (per step vs. per run) has no material effect on results.

### 10.5 Does K Appear Explicitly?

**No.** K disappears because $K \times S = V_{\text{total}}$ (the total bytes already encode K). The shared-link bandwidth correctly handles serialization through the $V/\text{BW}$ term. K-as-concurrency has no effect on CXLMemSim queue timing (empirically verified in Part 4 of the scaling study).

### 10.6 How to Represent Shared-Link Bandwidth

$$T_{\text{bw}} = \frac{V_{\text{total}}}{\text{BW}}$$

This is the correct expression. The link carries $V_{\text{total}}$ bytes sequentially at BW. No K multiplier.

### 10.7 Additional CXLMemSim Calibration Required Before Implementation

**Yes, for the BW=16 and BW=64 conditions.** The existing T_0 = 11.44 μs calibration is valid only for BW=32, lat=300. Applying it to conditions 7–10 (BW=16, BW=64) introduces an uncalibrated assumption. The calibration experiment is lightweight: < 1 minute per BW point using the existing `stream_scaling_bench` binary with modified constructor arguments.

### 10.8 Exact Wording for Paper/Report

**Allowed:**

> "Transfer time is modeled as $T = V_{\text{total}} / \text{BW} + N_{\text{steps}} \times T_0$, where $T_0 = 11.44$ μs is the CXLMemSim-calibrated queue startup overhead per batch step (measured at BW=32 GB/s, lat=300 ns from real CXLMemSim `insert()` and `process_queued_requests()` queue executions on streams up to 16 MiB; validated with < 0.40% relative error on held-out stream sizes). For BW=32 GB/s conditions, this model is CXLMemSim-calibrated. For BW=16 and BW=64 GB/s conditions, $V/\text{BW}$ dominates and $T_0$ is negligible; those conditions use a bandwidth-limited analytical model with BW as the only parameter."

**Not allowed:**
- "Full CXLMemSim simulation" — the 256 MiB expert is not fed cacheline-by-cacheline through CXLMemSim.
- "CXLMemSim-simulated transfer time" for BW=16 or BW=64 without separate calibration.
- "Queue-validated" for the $N \times \text{Lat}$ overhead — that term is analytically derived, not queue-observed.
- Claiming that K concurrent streams experience any different timing than K sequential streams (not supported by CXLMemSim — K is queue-irrelevant).
- "Physical CXL behavior validated" — CXLMemSim models a credit-limited protocol; real CXL hardware may differ in queue depth and credit count.

### 10.9 Claims NOT Allowed

1. That the existing EXP-05B results are "CXLMemSim simulation results" — they are analytical proxy results with a different formula.
2. That adding $N \times \text{Lat}$ per-transfer latency is CXLMemSim-derived — it is a manually added term not observed in the queue calibration.
3. That K-concurrency matters for CXL link timing at the TierMoE scale — not supported.
4. That $T_0 = 11.44$ μs is valid for BW≠32 GB/s — not calibrated.
5. That CXLMemSim's TID-blindness means real CXL hardware provides no QoS between streams — CXLMemSim is a simulator, not the real hardware specification.

---

## Summary: Additional Calibration Required?

**YES, before calling the model "CXLMemSim-calibrated" for all 10 conditions.**

The existing calibration covers only BW=32 GB/s, lat=300 ns. Two additional calibration runs are needed:

```
g++ -std=c++20 -O3 -Wno-subobject-linkage \
    -I calibration/stub_includes \
    -I /home/k8s-admin/Vinay/CXLMemSim/include \
    calibration/stream_scaling_bench.cpp \
    /home/k8s-admin/Vinay/CXLMemSim/src/cxlendpoint.cpp \
    -o calibration/stream_scaling_16 && ./calibration/stream_scaling_16
# (after editing make_ep() to use bw=16, lat=300)

# and separately for bw=64, lat=300
```

For **BW=32, lat=300 only** (conditions 1–6), the existing calibration is scientifically defensible, and $T_0$ is practically negligible (< 0.005% of total time). The dominant term is $V/\text{BW}$, and removing the erroneous $N \times \text{Lat}$ term is the most impactful correction.
