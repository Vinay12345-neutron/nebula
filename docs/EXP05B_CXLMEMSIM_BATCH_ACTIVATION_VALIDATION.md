# EXP-05B CXLMemSim Batch Activation Validation

**Status:** Empirical benchmark complete  
**Benchmark:** [`calibration/batch_activation_validation.cpp`](file:///home/k8s-admin/Vinay/nebula/calibration/batch_activation_validation.cpp) — linked against upstream `CXLMemSim/src/cxlendpoint.cpp`  
**Config:** BW=32 GB/s, lat=300 ns, `INITIAL_CREDITS=2`, `MAX_QUEUE_SIZE=64`  
**N per expert:** 4,096 cache lines (256 KiB representative block)  
**Arrival interval:** Δt = 2 ns (physical link rate = 64 bytes / 32 GB/s)  
**T0 comparison baseline:** 11,438 ns (from stream-scaling calibration, N=64..4096)  
**Date:** September 13, 2026  

---

## 1. Question Under Investigation

For K expert transfers in one TierMoE batch step, which model is supported by CXLMemSim?

| Model | Formula |
| :--- | :--- |
| A | $T = V_{\text{step}}/\text{BW}$ |
| B | $T = V_{\text{step}}/\text{BW} + T_0$ |
| C | $T = V_{\text{step}}/\text{BW} + K \times T_0$ |

where $V_{\text{step}} = K \times N \times 64$ bytes, $T_0 = 11{,}438$ ns.

The key distinction: does CXLMemSim incur $T_0$ **once per shared burst** (Model B), or **once per expert transfer** (Model C)?

---

## 2. Experimental Design

Four scheduling modes were measured for K = 1, 2, 4, 8, 16, 32:

| Mode | CXLMemExpander instances | Request structure | Physical meaning |
| :--- | :--- | :--- | :--- |
| **CONCAT** | 1 | K×N requests, timestamps 0, 2, 4, … ns | K experts as one contiguous link burst |
| **RR** | 1 | K×N requests, round-robin interleaved | K experts multiplexed at cacheline granularity |
| **CHUNKED** | 1 | N-line chunks per expert, sequential timestamps | K experts in chunks on shared link |
| **SEQUENTIAL** | K (fresh per expert) | N requests per expander, global time forwarded | K independent link activations (cold-start each time) |

The `SEQUENTIAL` mode is the critical control: it is the only configuration that incurs K separate `CXLMemExpander` cold starts, representing the hypothesis that each expert transfer is an independent link activation.

---

## 3. Full Benchmark Data

### Part 3A — CONCAT

```
      Mode   K  Total_N  Accept  Reject  PeakQ Makespan(ns)   Ideal(ns)    Ovhd(ns)   Ovhd/T0   ErrB(ns)   ErrC(ns) CPU(ms)
    CONCAT   1     4096     108    3988     66        19639        8192       11447       1.0          9          9     0.2
    CONCAT   2     8192     152    8040     66        27933       16384       11549       1.0        111     -11327     0.4
    CONCAT   4    16384     238   16146     66        44144       32768       11376       1.0        -62     -34376     0.8
    CONCAT   8    32768     412   32356     66        76943       65536       11407       1.0        -31     -80097     1.6
    CONCAT  16    65536     760   64776     66       142541      131072       11469       1.0         31    -171539     3.1
    CONCAT  32   131072    1456  129616     66       273737      262144       11593       1.0        155    -354423     6.3
```

### Part 3B — RR

```
        RR   1     4096     108    3988     66        19639        8192       11447       1.0          9          9     0.2
        RR   2     8192     152    8040     66        27933       16384       11549       1.0        111     -11327     0.4
        RR   4    16384     238   16146     66        44144       32768       11376       1.0        -62     -34376     0.8
        RR   8    32768     412   32356     66        76943       65536       11407       1.0        -31     -80097     1.7
        RR  16    65536     760   64776     66       142541      131072       11469       1.0         31    -171539     3.3
        RR  32   131072    1456  129616     66       273737      262144       11593       1.0        155    -354423     6.4
```

### Part 3C — CHUNKED

```
   CHUNKED   1     4096     108    3988     66        19639        8192       11447       1.0          9          9     0.2
   CHUNKED   2     8192     152    8040     66        27933       16384       11549       1.0        111     -11327     0.4
   CHUNKED   4    16384     238   16146     66        44144       32768       11376       1.0        -62     -34376     0.8
   CHUNKED   8    32768     412   32356     66        76943       65536       11407       1.0        -31     -80097     1.6
   CHUNKED  16    65536     760   64776     66       142541      131072       11469       1.0         31    -171539     3.1
   CHUNKED  32   131072    1456  129616     66       273737      262144       11593       1.0        155    -354423     6.2
```

### Part 3D — SEQUENTIAL (K independent activations)

```
SEQUENTIAL   1     4096     108    3988     66        19662        8192       11470       1.0         32         32     0.1
SEQUENTIAL   2     8192     216    7976     66        39324       16384       22940       2.0      11502         64     0.3
SEQUENTIAL   4    16384     432   15952     66        78648       32768       45880       4.0      34442        128     0.4
SEQUENTIAL   8    32768     864   31904     66       157296       65536       91760       8.0      80322        256     0.9
SEQUENTIAL  16    65536    1728   63808     66       314592      131072      183520      16.0     172082        512     1.8
SEQUENTIAL  32   131072    3456  127616     66       629184      262144      367040      32.1     355602       1024     3.6
```

---

## 4. Part 7 — The Critical Mathematical Test

```
           K   CONCAT_Ovhd  CONCAT/T0    RR_Ovhd    RR/T0  CHUNKED_Ovhd  CHUNKED/T0   SEQ_Ovhd   SEQ/T0  SEQ/CONCAT
           1         11447        1.0      11447      1.0         11447         1.0       11470      1.0         1.0
           2         11549        1.0      11549      1.0         11549         1.0       22940      2.0         2.0
           4         11376        1.0      11376      1.0         11376         1.0       45880      4.0         4.0
           8         11407        1.0      11407      1.0         11407         1.0       91760      8.0         8.0
          16         11469        1.0      11469      1.0         11469         1.0      183520     16.0        16.0
          32         11593        1.0      11593      1.0         11593         1.0      367040     32.1        31.7
```

---

## 5. Part 8 — Model Prediction Errors

### CONCAT / RR / CHUNKED (identical results)

| K | Makespan(ns) | ErrB(ns) | ErrB(%) | ErrC(ns) | ErrC(%) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | 19,639 | **+9** | **0.0%** | +9 | 0.0% |
| 2 | 27,933 | **+111** | **0.4%** | −11,327 | −40.6% |
| 4 | 44,144 | **−62** | **−0.1%** | −34,376 | −77.9% |
| 8 | 76,943 | **−31** | **0.0%** | −80,097 | −104.1% |
| 16 | 142,541 | **+31** | **0.0%** | −171,539 | −120.3% |
| 32 | 273,737 | **+155** | **0.1%** | −354,423 | −129.5% |

### SEQUENTIAL

| K | Makespan(ns) | ErrB(ns) | ErrB(%) | ErrC(ns) | ErrC(%) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | 19,662 | +32 | 0.2% | **+32** | **0.2%** |
| 2 | 39,324 | +11,502 | 29.2% | **+64** | **0.2%** |
| 4 | 78,648 | +34,442 | 43.8% | **+128** | **0.2%** |
| 8 | 157,296 | +80,322 | 51.1% | **+256** | **0.2%** |
| 16 | 314,592 | +172,082 | 54.7% | **+512** | **0.2%** |
| 32 | 629,184 | +355,602 | 56.5% | **+1,024** | **0.2%** |

---

## 6. Findings

### Finding 1: CONCAT = RR = CHUNKED (byte-identical results)

All three shared-expander modes produce **identical makespan at every K**. The CXLMemSim queue is completely insensitive to stream interleaving pattern (TID, round-robin, chunked, or concatenated). This reconfirms the result from Part 4 of the stream-scaling study: **CXLMemSim's queue implementation is insensitive to stream identity under this configuration.**

> [!NOTE]
> This does NOT imply real CXL hardware has no QoS or stream arbitration. It reflects that `CXLMemExpander::request_queue_` is an unpartitioned FIFO and TID is metadata only.

### Finding 2: Shared-Expander Overhead Is Constant at T0 Regardless of K

For CONCAT/RR/CHUNKED, the overhead $T_{\text{overhead}} = T_{\text{makespan}} - T_{\text{ideal}}$ is:

| K | Overhead (ns) | Ratio to T0 |
| :--- | :--- | :--- |
| 1 | 11,447 | 1.001 |
| 2 | 11,549 | 1.010 |
| 4 | 11,376 | 0.995 |
| 8 | 11,407 | 0.998 |
| 16 | 11,469 | 1.003 |
| 32 | 11,593 | 1.014 |

**Mean overhead = 11,473 ns. Std dev = ±83 ns (0.72% of T0). Range = [11,376, 11,593] ns.**

The overhead is constant to within ±1.4% across K=1..32. **This is Model B behavior.**

### Finding 3: Sequential-Activation Overhead Scales Exactly as K × T0

For SEQUENTIAL mode, overhead = $K \times 11{,}470$ ns (K=1 baseline), scaling with ratio:

| K | SEQ Overhead (ns) | SEQ/T0 | SEQ/CONCAT |
| :--- | :--- | :--- | :--- |
| 1 | 11,470 | 1.003 | 1.00 |
| 2 | 22,940 | 2.006 | 1.99 |
| 4 | 45,880 | 4.012 | 4.03 |
| 8 | 91,760 | 8.023 | 8.04 |
| 16 | 183,520 | 16.047 | 16.00 |
| 32 | 367,040 | 32.093 | 31.7 |

**Model C (V/BW + K×T0) fits SEQUENTIAL with ErrC ≤ 1,024 ns (0.16% relative error). This confirms that K independent cold-start activations each pay T0.**

### Finding 4: Model B Error ≤ 155 ns for Shared Burst (K=1..32)

For the shared-expander runs (CONCAT/RR/CHUNKED):
- **Model A error** (no correction): 11,376 to 11,593 ns (8–58% relative, decreasing with K)
- **Model B error** (single T0): −62 to +155 ns (**max 0.4% relative**)
- **Model C error** (K×T0): −354,423 to +9 ns (up to −130% for K>1)

Model B is the only model consistent with shared-expander CXLMemSim behavior across all K.

### Finding 5: The Appropriate Model Depends on the Physical Topology

| TierMoE scenario | Correct model |
| :--- | :--- |
| K experts in one batch step, single CXL link, no link idle gap | **Model B**: $T = V_{\text{step}}/\text{BW} + T_0$ |
| K experts transferred serially with link idle between them | **Model C**: $T = K \times (S/\text{BW} + T_0)$ |
| K batch steps each with one or more expert transfers | **Model B per step**: $T_{\text{total}} = V_{\text{total}}/\text{BW} + N_{\text{steps}} \times T_0$ |

For TierMoE inference, expert fetches within a batch step share a single CXL link without idle gaps. This corresponds to the shared-expander scenario (CONCAT/RR/CHUNKED). **Model B applies at the batch-step level.**

---

## 7. T0 Numerical Verification

From the benchmark data, the empirical T0 values (CONCAT, K=1..32):

| K | Measured T0_empirical (ns) | Deviation from calibrated T0=11438 ns |
| :--- | :--- | :--- |
| 1 | 11,447 | +9 (+0.08%) |
| 2 | 11,549 | +111 (+0.97%) |
| 4 | 11,376 | −62 (−0.54%) |
| 8 | 11,407 | −31 (−0.27%) |
| 16 | 11,469 | +31 (+0.27%) |
| 32 | 11,593 | +155 (+1.35%) |

All measurements are within ±1.35% of the calibrated value. The variation is consistent with the ±68 ns std dev observed in the stream-scaling study. **No systematic drift with K is observed** — confirming the overhead is a property of one queue activation, not of stream count.

---

## 8. Scope Limitations

> [!WARNING]
> The following caveats apply to all conclusions in this report:

1. **CXLMemSim, not real hardware.** These measurements characterize `CXLMemExpander`'s software queue model (INITIAL_CREDITS=2, MAX_QUEUE_SIZE=64). Real CXL Gen 2/3 hardware may have different credit counts, queue depths, and scheduler behavior.

2. **Representative block only.** N=4,096 cache lines (256 KiB) per expert is used, not the full 256 MiB (4,194,304 cache lines). The 1/N convergence law (validated in the stream-scaling study to ≤0.14% error at 16 MiB) justifies this extrapolation.

3. **Single expander topology.** All shared-mode experiments use one `CXLMemExpander` instance. A real CXL topology might have switches, multiple expanders, or tiered queues.

4. **BW=32 GB/s, lat=300 ns only.** The T0=11,438 ns value was calibrated and validated at this configuration. Generalization to BW=16/64 requires separate calibration.

5. **CXLMemSim's TID-blindness is a simulator property.** The conclusion that K has no effect is specific to CXLMemSim's queue implementation and should not be presented as physical CXL behavior.

---

## 9. Decision

### OPTION 1: BATCH-LEVEL T0 SUPPORTED

The evidence is sufficient to implement:

$$T_{\text{total}} = \frac{V_{\text{total}}}{\text{BW}} + N_{\text{steps,active}} \times T_0(\text{BW})$$

with the following explicit calibration-scope disclaimer required in all documentation.

**Evidence:**
- Shared-expander overhead is constant at T0 ± 1.35% across K=1..32 (24 measurements total across 3 modes)
- Model B maximum error: 155 ns (0.06% of largest tested makespan)
- Model C maximum error at K=8: 80,097 ns (104% of makespan) — Model C is **strongly rejected** for shared-link scenarios
- Sequential mode confirms exactly K×T0 behavior when K activations are independent — this is the correct model for idle-gap transfers

**The key physical argument:** Within one batch step, K expert fetches share one CXL link continuously. The link does not go idle between experts. This is identical to the CONCAT experiment. CXLMemSim's queue model exhibits exactly one T0 overhead for this scenario, regardless of K from 1 to 32.

---

## 10. Exact Paper/Report Wording

### For the main model claim:

> "We model the CXL transfer time for each batch step as $T_{\text{step}} = V_{\text{step}} / \text{BW} + T_0$, where $V_{\text{step}}$ is the total bytes fetched (expert blocks that are cache misses or promotions) and $T_0$ is the CXLMemSim-calibrated queue startup overhead per link activation. $T_0 = 11.44$ μs was empirically derived from CXLMemSim's `insert()`/`process_queued_requests()` queue path at BW=32 GB/s and read latency=300 ns. We validated that $T_0$ is constant with respect to the number of concurrent expert fetches K (K=1..32, max deviation ±1.35%) when all fetches share a single CXL endpoint — confirming that K experts within one batch step incur a single link-activation overhead."

### For the aggregate total:

> "Total CXL transfer time across the inference trace is $T_{\text{total}} = V_{\text{total}} / \text{BW} + N_{\text{active}} \times T_0$, where $N_{\text{active}}$ is the number of batch steps with at least one expert fetch. At the scales tested (V_total ≈ 1.6–2.8 TiB), the $T_0$ correction contributes less than 0.005% of total time and is negligible."

### For calibration scope:

> "This model is calibrated for BW=32 GB/s and CXL read latency=300 ns. Application to the BW=16 and BW=64 GB/s sensitivity conditions uses $V/\text{BW}$ only, as the $T_0$ correction is negligible at those scales."

---

## 11. Prohibited Claims

The following statements **must not appear** in any paper, report, or code comment:

- ~~"Full CXLMemSim simulation of 256 MiB expert transfers"~~ — the simulator uses representative 256 KiB blocks with extrapolation
- ~~"Real CXL hardware validated"~~ — these are CXLMemSim model measurements
- ~~"Physical CXL validated"~~ — same
- ~~"K concurrent streams are serialized with K startup overheads"~~ — the data shows one overhead for shared-link concurrent fetches
- ~~"CXLMemSim confirms CXL has no QoS between streams"~~ — this is a property of the CXLMemSim implementation, not the CXL specification
- ~~"T0 = 11.44 μs is valid for BW=16 or BW=64"~~ — uncalibrated at those bandwidths

---

## Appendix: Benchmark Source and Build

- **Source:** [`calibration/batch_activation_validation.cpp`](file:///home/k8s-admin/Vinay/nebula/calibration/batch_activation_validation.cpp)
- **Upstream CXLMemSim:** [`/home/k8s-admin/Vinay/CXLMemSim/src/cxlendpoint.cpp`](file:///home/k8s-admin/Vinay/CXLMemSim/src/cxlendpoint.cpp) — **UNMODIFIED**
- **Build:**
  ```
  g++ -std=c++20 -O3 -Wno-subobject-linkage \
      -I calibration/stub_includes \
      -I /home/k8s-admin/Vinay/CXLMemSim/include \
      calibration/batch_activation_validation.cpp \
      /home/k8s-admin/Vinay/CXLMemSim/src/cxlendpoint.cpp \
      -o calibration/batch_activation
  ```
- **CoherencyEngine stub:** Returns `{0.0, SHARED, true, 0}` — same as all prior calibration binaries; only needed to link `RemoteCXLExpander`, which is not exercised here.

*(Per instructions, stopping here. Implementation awaits review.)*
