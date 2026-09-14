/*
 * EXP-05B Stage B: Stream Scaling Benchmark — CXLMemSim Queue Path
 *
 * Investigates:
 *  Part 1: Queue behavior driving factors (documented via source study)
 *  Part 2: Stream length scaling (64 to 16384 requests)
 *  Part 3: Arrival-interval sweep (1024 requests at 0..1000 ns spacing)
 *  Part 4: Multi-stream experiment (K=1..32, total=4096 requests)
 *  Part 5: Address effect (sequential, formula-mapped, random)
 *  Part 6: Occupation O(N^2) investigation
 *  Part 7: Block-size scaling (64 KiB to 64 MiB via insert/process)
 *
 * Compile:
 *  g++ -std=c++20 -O3 -Wno-subobject-linkage \
 *      -I calibration/stub_includes \
 *      -I /home/k8s-admin/Vinay/CXLMemSim/include \
 *      calibration/stream_scaling_bench.cpp \
 *      /home/k8s-admin/Vinay/CXLMemSim/src/cxlendpoint.cpp \
 *      -o calibration/stream_scaling && ./calibration/stream_scaling
 *
 * RESTRICTIONS: DO NOT modify upstream CXLMemSim.
 */

#define SPDLOG_ACTIVE_LEVEL SPDLOG_LEVEL_OFF
#include <algorithm>
#include "cxlendpoint.h"
#include "coherency_engine.h"
#include <iostream>
#include <iomanip>
#include <vector>
#include <tuple>
#include <cstdint>
#include <cassert>
#include <chrono>
#include <cmath>
#include <numeric>
#include <random>

// Stub for RemoteCXLExpander linker dependency
CoherencyResponse CoherencyEngine::process_read(const CoherencyRequest &) {
    return CoherencyResponse{0.0, MHSLDCacheState::SHARED, true, 0};
}

// ============================================================================
// HELPERS
// ============================================================================

static void section(const std::string &title) {
    std::cout << "\n" << std::string(78, '=') << "\n";
    std::cout << "  " << title << "\n";
    std::cout << std::string(78, '=') << "\n";
}

static void subsection(const std::string &title) {
    std::cout << "\n" << std::string(60, '-') << "\n";
    std::cout << "  " << title << "\n";
    std::cout << std::string(60, '-') << "\n";
}

static BandwidthModelConfig make_cfg(double bw_gbps = 32.0, double lat_ns = 300.0) {
    BandwidthModelConfig cfg;
    cfg.read_peak_gbps = bw_gbps;
    cfg.write_peak_gbps = bw_gbps;
    cfg.knee_utilization = 0.80;
    cfg.saturation_utilization = 0.98;
    cfg.low_utilization_slope = 0.05;
    cfg.max_penalty_ns = 5000.0;
    cfg.min_window_ns = 100000;
    cfg.calibrated_from_mlc = true;
    (void)lat_ns;
    return cfg;
}

// Create a fresh expander on the heap.
// CXLMemExpander is non-movable (contains std::mutex, std::shared_mutex, std::atomic).
static std::unique_ptr<CXLMemExpander> make_ep(double bw_gbps = 32.0, double lat_ns = 300.0) {
    int bw  = static_cast<int>(bw_gbps);
    int lat = static_cast<int>(lat_ns);
    auto ep = std::make_unique<CXLMemExpander>(bw, bw, lat, lat, 0, 1024 * 1024); // id=0
    ep->configure_bandwidth_model(make_cfg(bw_gbps, lat_ns));
    return ep;
}

// Event-driven drain: advance simulation time to next completion event
struct ReqStat {
    uint64_t submit_time;
    uint64_t issue_time;
    uint64_t complete_time;
    double   latency_ns;  // complete - submit
    bool     accepted;
};

struct StreamResult {
    size_t   total_submitted;
    size_t   accepted;
    size_t   rejected;
    size_t   peak_queue_depth;
    size_t   credit_waves;         // wave = event where next pair gets issued
    uint64_t makespan_ns;
    double   avg_lat_ns;
    double   p50_lat_ns;
    double   p95_lat_ns;
    double   p99_lat_ns;
    double   cpu_ms;               // wall-clock CPU time for this simulation
    double   ideal_ns;             // bytes / BW (theoretical link time)
    double   relative_error;       // (makespan - ideal) / ideal
    size_t   occupation_size;      // ep.occupation.size() after run
};

// Returns sorted latencies for percentile computation
static StreamResult run_stream(
        size_t N,
        uint64_t arrival_interval_ns,   // 0 = all-at-once
        size_t K,                        // number of concurrent streams
        bool round_robin,                // true=interleave, false=chunked
        uint64_t base_addr,             // base address for stream 0
        uint64_t addr_stride,           // stride between streams; 0=same as sequential within stream
        bool random_addresses,
        double bw_gbps = 32.0,
        double lat_ns  = 300.0) {

    // --- create expander (heap-allocated; CXLMemExpander is non-movable) ---
    auto ep = make_ep(bw_gbps, lat_ns);

    auto wall_start = std::chrono::high_resolution_clock::now();

    const size_t cacheline = 64;
    const size_t reqs_per_stream = N / std::max(K, (size_t)1);

    std::mt19937_64 rng(42);
    std::uniform_int_distribution<uint64_t> rand_addr(1ULL << 30, 1ULL << 32);

    size_t accepted = 0, rejected = 0, peak_q = 0, waves = 0;
    std::vector<double> completed_latencies;

    // Build injection order
    // Each entry: (timestamp_ns, stream_id, cacheline_index, phys_addr)
    struct Req { uint64_t ts; size_t sid; size_t lidx; uint64_t addr; };
    std::vector<Req> schedule;
    schedule.reserve(N);

    if (round_robin) {
        for (size_t l = 0; l < reqs_per_stream; ++l) {
            for (size_t s = 0; s < K; ++s) {
                uint64_t ts = (arrival_interval_ns == 0) ? 0 :
                    static_cast<uint64_t>((l * K + s)) * arrival_interval_ns;
                uint64_t addr = random_addresses ? rand_addr(rng) :
                    base_addr + (addr_stride == 0 ? s * reqs_per_stream * cacheline : s * addr_stride)
                    + l * cacheline;
                schedule.push_back({ts, s, l, addr});
            }
        }
    } else {
        // Chunked: all of stream 0, then all of stream 1 ...
        for (size_t s = 0; s < K; ++s) {
            for (size_t l = 0; l < reqs_per_stream; ++l) {
                uint64_t ts = (arrival_interval_ns == 0) ? 0 :
                    static_cast<uint64_t>(s * reqs_per_stream + l) * arrival_interval_ns;
                uint64_t addr = random_addresses ? rand_addr(rng) :
                    base_addr + s * reqs_per_stream * cacheline + l * cacheline;
                schedule.push_back({ts, s, l, addr});
            }
        }
    }

    // Feed into CXLMemExpander via insert()
    size_t inject_idx = 0;
    size_t prev_in_flight = 0;
    uint64_t current_time = 0;

    // We drive time forward by: inject all due requests at current_time,
    // then jump to next completion event.
    while (inject_idx < schedule.size() || true) {
        // Inject all requests whose arrival_ts <= current_time
        while (inject_idx < schedule.size() && schedule[inject_idx].ts <= current_time) {
            auto &r = schedule[inject_idx];
            int ret = ep->insert(r.ts, r.sid, r.addr, r.addr, 0);
            if (ret != 0) {
                accepted++;
            } else {
                rejected++;
            }
            size_t qs;
            {
                std::lock_guard<std::mutex> lk(ep->queue_mutex_);
                qs = ep->request_queue_.size() + ep->in_flight_requests_.size();
            }
            if (qs > peak_q) peak_q = qs;
            inject_idx++;
        }

        // Check for wave transitions
        {
            std::lock_guard<std::mutex> lk(ep->queue_mutex_);
            if (ep->in_flight_requests_.size() != prev_in_flight) {
                if (ep->in_flight_requests_.size() > prev_in_flight) waves++;
                prev_in_flight = ep->in_flight_requests_.size();
            }
        }

        // Find next event time: either next arrival or next completion
        uint64_t next_arrival = (inject_idx < schedule.size()) ? schedule[inject_idx].ts : UINT64_MAX;
        uint64_t next_complete = UINT64_MAX;
        bool queue_empty, inflight_empty;
        {
            std::lock_guard<std::mutex> lk(ep->queue_mutex_);
            queue_empty = ep->request_queue_.empty();
            inflight_empty = ep->in_flight_requests_.empty();
            for (const auto &[addr, req] : ep->in_flight_requests_) {
                if (req.complete_time < next_complete) {
                    next_complete = req.complete_time;
                }
            }
        }

        // Collect completions before retiring
        {
            std::lock_guard<std::mutex> lk(ep->queue_mutex_);
            for (const auto &[addr, req] : ep->in_flight_requests_) {
                if (req.complete_time <= current_time) {
                    completed_latencies.push_back(
                        static_cast<double>(req.complete_time - req.timestamp));
                }
            }
        }
        ep->process_queued_requests(current_time);

        // Determine if we are done
        bool all_injected = (inject_idx >= schedule.size());
        {
            std::lock_guard<std::mutex> lk(ep->queue_mutex_);
            queue_empty = ep->request_queue_.empty();
            inflight_empty = ep->in_flight_requests_.empty();
        }
        if (all_injected && queue_empty && inflight_empty) break;

        // Advance time
        uint64_t next_event = std::min(next_arrival, next_complete);
        if (next_event == UINT64_MAX) {
            current_time += 1;  // nudge
        } else {
            current_time = next_event;
        }
    }

    // Re-collect completions from any stragglers
    {
        std::lock_guard<std::mutex> lk(ep->queue_mutex_);
        for (const auto &[addr, req] : ep->in_flight_requests_) {
            completed_latencies.push_back(
                static_cast<double>(req.complete_time - req.timestamp));
            if (req.complete_time > current_time) current_time = req.complete_time;
        }
    }

    auto wall_end = std::chrono::high_resolution_clock::now();
    double cpu_ms = std::chrono::duration<double, std::milli>(wall_end - wall_start).count();

    // Compute statistics
    std::sort(completed_latencies.begin(), completed_latencies.end());
    size_t nC = completed_latencies.size();
    double avg = 0, p50 = 0, p95 = 0, p99 = 0;
    if (nC > 0) {
        avg = std::accumulate(completed_latencies.begin(), completed_latencies.end(), 0.0) / nC;
        p50 = completed_latencies[nC * 50 / 100];
        p95 = completed_latencies[std::min(nC - 1, nC * 95 / 100)];
        p99 = completed_latencies[std::min(nC - 1, nC * 99 / 100)];
    }

    // Ideal link transmission time: total_bytes / BW
    double total_bytes = static_cast<double>(N) * cacheline;
    double ideal_ns = total_bytes / bw_gbps;  // bw_gbps == GB/s == bytes/ns

    StreamResult r{};
    r.total_submitted = N;
    r.accepted = accepted;
    r.rejected = rejected;
    r.peak_queue_depth = peak_q;
    r.credit_waves = waves;
    r.makespan_ns = current_time;
    r.avg_lat_ns  = avg;
    r.p50_lat_ns  = p50;
    r.p95_lat_ns  = p95;
    r.p99_lat_ns  = p99;
    r.cpu_ms      = cpu_ms;
    r.ideal_ns    = ideal_ns;
    r.relative_error = ideal_ns > 0 ? (static_cast<double>(current_time) - ideal_ns) / ideal_ns : 0.0;
    r.occupation_size = ep->occupation.size();
    return r;
}

// ============================================================================
// PART 2: Stream Length Scaling
// ============================================================================
static void part2_stream_length() {
    section("PART 2 — STREAM LENGTH SCALING (single stream, all at t=0)");
    std::cout << std::fixed << std::setprecision(2);
    std::cout << "  "
              << std::setw(8)  << "N"
              << std::setw(10) << "Accept"
              << std::setw(10) << "Reject"
              << std::setw(10) << "PeakQ"
              << std::setw(10) << "Waves"
              << std::setw(14) << "Makespan(ns)"
              << std::setw(12) << "Ideal(ns)"
              << std::setw(12) << "RelErr(%)"
              << std::setw(12) << "AvgLat(ns)"
              << std::setw(12) << "P50(ns)"
              << std::setw(12) << "P95(ns)"
              << std::setw(12) << "P99(ns)"
              << std::setw(12) << "OccSz"
              << std::setw(10) << "CPU(ms)"
              << "\n";

    std::vector<size_t> sizes = {64, 128, 256, 512, 1024, 2048, 4096, 8192, 16384};
    for (size_t N : sizes) {
        auto r = run_stream(N, 0, 1, true, 0x100000, 0, false);
        std::cout << "  "
                  << std::setw(8)  << N
                  << std::setw(10) << r.accepted
                  << std::setw(10) << r.rejected
                  << std::setw(10) << r.peak_queue_depth
                  << std::setw(10) << r.credit_waves
                  << std::setw(14) << r.makespan_ns
                  << std::setw(12) << (uint64_t)r.ideal_ns
                  << std::setw(12) << r.relative_error * 100.0
                  << std::setw(12) << r.avg_lat_ns
                  << std::setw(12) << r.p50_lat_ns
                  << std::setw(12) << r.p95_lat_ns
                  << std::setw(12) << r.p99_lat_ns
                  << std::setw(12) << r.occupation_size
                  << std::setw(10) << r.cpu_ms
                  << "\n";
    }
}

// ============================================================================
// PART 3: Arrival-Spacing Sweep (1024 requests, single stream)
// ============================================================================
static void part3_arrival_spacing() {
    section("PART 3 — ARRIVAL-SPACING SWEEP (N=1024, K=1)");
    std::cout << "  Physical link spacing for 32 GB/s: 64 bytes / 32 GB/s = 2.0 ns\n\n";
    std::cout << "  "
              << std::setw(12) << "Interval(ns)"
              << std::setw(10) << "Accept"
              << std::setw(10) << "Waves"
              << std::setw(14) << "Makespan(ns)"
              << std::setw(12) << "Ideal(ns)"
              << std::setw(12) << "RelErr(%)"
              << std::setw(12) << "AvgLat(ns)"
              << std::setw(12) << "P95(ns)"
              << std::setw(10) << "CPU(ms)"
              << "\n";

    std::vector<uint64_t> intervals = {0, 1, 2, 4, 8, 16, 32, 64, 100, 500, 1000};
    for (uint64_t iv : intervals) {
        auto r = run_stream(1024, iv, 1, true, 0x200000, 0, false);
        std::cout << "  "
                  << std::setw(12) << iv
                  << std::setw(10) << r.accepted
                  << std::setw(10) << r.credit_waves
                  << std::setw(14) << r.makespan_ns
                  << std::setw(12) << (uint64_t)r.ideal_ns
                  << std::setw(12) << r.relative_error * 100.0
                  << std::setw(12) << r.avg_lat_ns
                  << std::setw(12) << r.p95_lat_ns
                  << std::setw(10) << r.cpu_ms
                  << "\n";
    }
}

// ============================================================================
// PART 4: Multi-Stream (K=1..32, total N=4096)
// ============================================================================
static void part4_multistream() {
    section("PART 4 — MULTI-STREAM EXPERIMENT (total N=4096, arrival interval=2ns)");

    auto print_header = [&]() {
        std::cout << "  "
                  << std::setw(6)  << "K"
                  << std::setw(10) << "Sched"
                  << std::setw(10) << "Accept"
                  << std::setw(10) << "Reject"
                  << std::setw(10) << "PeakQ"
                  << std::setw(14) << "Makespan(ns)"
                  << std::setw(12) << "Ideal(ns)"
                  << std::setw(12) << "RelErr(%)"
                  << std::setw(12) << "AvgLat(ns)"
                  << std::setw(10) << "CPU(ms)"
                  << "\n";
    };

    print_header();
    std::vector<size_t> Ks = {1, 2, 4, 8, 16, 32};
    for (size_t K : Ks) {
        // Round-robin
        {
            auto r = run_stream(4096, 2, K, true, 0x1000000, 0x1000000ULL, false);
            std::cout << "  "
                      << std::setw(6)  << K
                      << std::setw(10) << "RR"
                      << std::setw(10) << r.accepted
                      << std::setw(10) << r.rejected
                      << std::setw(10) << r.peak_queue_depth
                      << std::setw(14) << r.makespan_ns
                      << std::setw(12) << (uint64_t)r.ideal_ns
                      << std::setw(12) << r.relative_error * 100.0
                      << std::setw(12) << r.avg_lat_ns
                      << std::setw(10) << r.cpu_ms
                      << "\n";
        }
        // Chunked
        {
            auto r = run_stream(4096, 2, K, false, 0x1000000, 0x1000000ULL, false);
            std::cout << "  "
                      << std::setw(6)  << K
                      << std::setw(10) << "CHUNK"
                      << std::setw(10) << r.accepted
                      << std::setw(10) << r.rejected
                      << std::setw(10) << r.peak_queue_depth
                      << std::setw(14) << r.makespan_ns
                      << std::setw(12) << (uint64_t)r.ideal_ns
                      << std::setw(12) << r.relative_error * 100.0
                      << std::setw(12) << r.avg_lat_ns
                      << std::setw(10) << r.cpu_ms
                      << "\n";
        }
    }
}

// ============================================================================
// PART 5: Address Effect (N=4096, K=4, round-robin, interval=2ns)
// ============================================================================
static void part5_address_effect() {
    section("PART 5 — ADDRESS EFFECT (N=4096, K=4, RR, interval=2ns)");
    std::cout << "  "
              << std::setw(20) << "Address Mode"
              << std::setw(10) << "Accept"
              << std::setw(14) << "Makespan(ns)"
              << std::setw(12) << "AvgLat(ns)"
              << std::setw(12) << "OccSz"
              << std::setw(10) << "CPU(ms)"
              << "\n";

    // A: sequential dense addresses (streams packed)
    {
        auto r = run_stream(4096, 2, 4, true, 0x100000, 0, false);
        std::cout << "  " << std::setw(20) << "A: Dense Sequential"
                  << std::setw(10) << r.accepted
                  << std::setw(14) << r.makespan_ns
                  << std::setw(12) << r.avg_lat_ns
                  << std::setw(12) << r.occupation_size
                  << std::setw(10) << r.cpu_ms << "\n";
    }

    // B: formula-mapped: (layer * 128 + expert) * 256 MiB
    // For expert 0..3 at layer 0: base_addrs spaced 256 MiB apart
    {
        // We run 4 sub-streams each at their own starting address; use large stride
        uint64_t base = 0; // layer=0, expert=0 -> addr = 0
        uint64_t stride_256mib = 256ULL * 1024 * 1024; // 256 MiB
        auto r = run_stream(4096, 2, 4, true, base, stride_256mib, false);
        std::cout << "  " << std::setw(20) << "B: Formula(256MiB)"
                  << std::setw(10) << r.accepted
                  << std::setw(14) << r.makespan_ns
                  << std::setw(12) << r.avg_lat_ns
                  << std::setw(12) << r.occupation_size
                  << std::setw(10) << r.cpu_ms << "\n";
    }

    // C: random addresses
    {
        auto r = run_stream(4096, 2, 4, true, 0, 0, true);
        std::cout << "  " << std::setw(20) << "C: Randomized"
                  << std::setw(10) << r.accepted
                  << std::setw(14) << r.makespan_ns
                  << std::setw(12) << r.avg_lat_ns
                  << std::setw(12) << r.occupation_size
                  << std::setw(10) << r.cpu_ms << "\n";
    }
}

// ============================================================================
// PART 6: Occupation O(N^2) Investigation
// ============================================================================
static void part6_occupation() {
    section("PART 6 — OCCUPATION O(N^2) INVESTIGATION");

    std::cout << "  Testing how occupation.size() grows and the CPU cost of linear scan.\n\n";
    std::cout << "  " << std::setw(8)  << "N"
              << std::setw(14) << "OccAfter"
              << std::setw(14) << "CPU(ms)"
              << std::setw(16) << "CPU/N (us/req)"
              << "\n";

    // For sequential NEW addresses (never repeated), occupation grows = N
    // For REPEATED same address, occupation stays small (erase+emplace)
    std::vector<size_t> ns = {64, 256, 512, 1024, 2048, 4096, 8192};
    for (size_t N : ns) {
        auto r = run_stream(N, 0, 1, true, 0x500000, 0, false);
        double us_per = (r.cpu_ms * 1000.0) / N;
        std::cout << "  " << std::setw(8)  << N
                  << std::setw(14) << r.occupation_size
                  << std::setw(14) << r.cpu_ms
                  << std::setw(16) << us_per
                  << "\n";
    }

    // Now test: what if we use a fresh expander every 64 requests?
    // (simulating periodic re-instantiation)
    subsection("PART 6b — Periodic expander reset (fresh instance every 64 reqs)");
    std::cout << "  Strategy: for large N, split into chunks of 64 with a fresh CXLMemExpander\n";
    std::cout << "  per chunk, threading time forward manually.\n\n";
    std::cout << "  " << std::setw(8)  << "N"
              << std::setw(14) << "Makespan(ns)"
              << std::setw(14) << "CPU(ms)"
              << "\n";

    for (size_t N : ns) {
        const size_t CHUNK = 64;
        auto wall_start = std::chrono::high_resolution_clock::now();

        uint64_t global_time = 0;
        size_t accepted_total = 0;
        uint64_t chunk_addr = 0x600000;

        for (size_t offset = 0; offset < N; offset += CHUNK) {
            size_t chunk_n = std::min(CHUNK, N - offset);
            auto ep = make_ep();
            for (size_t i = 0; i < chunk_n; i++) {
                ep->insert(global_time, 0, chunk_addr + (offset + i) * 64, chunk_addr + (offset + i) * 64, 0);
            }
            // Drain
            while (true) {
                uint64_t next_c = UINT64_MAX;
                bool qi, fi;
                {
                    std::lock_guard<std::mutex> lk(ep->queue_mutex_);
                    qi = ep->request_queue_.empty();
                    fi = ep->in_flight_requests_.empty();
                    for (auto &[a, r] : ep->in_flight_requests_) {
                        if (r.complete_time < next_c) next_c = r.complete_time;
                    }
                }
                if (qi && fi) break;
                global_time = (next_c == UINT64_MAX) ? global_time + 1 : next_c;
                ep->process_queued_requests(global_time);
            }
        }
        auto wall_end = std::chrono::high_resolution_clock::now();
        double cpu_ms = std::chrono::duration<double, std::milli>(wall_end - wall_start).count();
        std::cout << "  " << std::setw(8) << N
                  << std::setw(14) << global_time
                  << std::setw(14) << cpu_ms
                  << "\n";
    }
}

// ============================================================================
// PART 7: Block-Size Scaling (bytes -> requests -> run)
// ============================================================================
static void part7_block_scaling() {
    section("PART 7 — BLOCK-SIZE SCALING (real insert/process queue path)");
    std::cout << "  BW=32 GB/s, lat=300ns, single stream, arrival_interval=2ns (physical link rate)\n\n";

    // block sizes in KiB -> convert to requests
    // 1 KiB = 1024 bytes; 1 cacheline = 64 bytes -> 1024/64 = 16 requests per KiB
    struct BlockTest { const char *label; size_t bytes; };
    std::vector<BlockTest> tests = {
        {"64 KiB",  64ULL  * 1024},
        {"256 KiB", 256ULL * 1024},
        {"1 MiB",   1ULL   * 1024 * 1024},
        {"4 MiB",   4ULL   * 1024 * 1024},
        {"16 MiB",  16ULL  * 1024 * 1024},
    };

    std::cout << "  " << std::setw(10) << "Block"
              << std::setw(10) << "N"
              << std::setw(10) << "Accept"
              << std::setw(10) << "Reject"
              << std::setw(14) << "Makespan(ns)"
              << std::setw(14) << "Ideal(ns)"
              << std::setw(12) << "RelErr(%)"
              << std::setw(12) << "AvgLat(ns)"
              << std::setw(12) << "P95(ns)"
              << std::setw(10) << "CPU(ms)"
              << "\n";

    for (auto &bt : tests) {
        size_t N = bt.bytes / 64;
        // Arrival interval = 2ns (physical link rate = 32 GB/s -> 64 bytes / 32 = 2 ns)
        auto r = run_stream(N, 2, 1, true, 0x700000, 0, false);
        std::cout << "  " << std::setw(10) << bt.label
                  << std::setw(10) << N
                  << std::setw(10) << r.accepted
                  << std::setw(10) << r.rejected
                  << std::setw(14) << r.makespan_ns
                  << std::setw(14) << (uint64_t)r.ideal_ns
                  << std::setw(12) << r.relative_error * 100.0
                  << std::setw(12) << r.avg_lat_ns
                  << std::setw(12) << r.p95_lat_ns
                  << std::setw(10) << r.cpu_ms
                  << "\n";
    }

    // Also run at interval=0 to show saturation at full burst
    subsection("PART 7b — Same block sizes at arrival_interval=0 (all-at-once burst)");
    std::cout << "  " << std::setw(10) << "Block"
              << std::setw(10) << "N"
              << std::setw(10) << "Accept"
              << std::setw(10) << "Reject"
              << std::setw(14) << "Makespan(ns)"
              << std::setw(14) << "Ideal(ns)"
              << std::setw(12) << "RelErr(%)"
              << std::setw(10) << "CPU(ms)"
              << "\n";
    for (auto &bt : tests) {
        size_t N = bt.bytes / 64;
        auto r = run_stream(N, 0, 1, true, 0x800000, 0, false);
        std::cout << "  " << std::setw(10) << bt.label
                  << std::setw(10) << N
                  << std::setw(10) << r.accepted
                  << std::setw(10) << r.rejected
                  << std::setw(14) << r.makespan_ns
                  << std::setw(14) << (uint64_t)r.ideal_ns
                  << std::setw(12) << r.relative_error * 100.0
                  << std::setw(10) << r.cpu_ms
                  << "\n";
    }
}

// ============================================================================
// PART 8: Convergence Analysis — Train on 64-4096, Validate on 8192-16384
// ============================================================================
static void part8_convergence() {
    section("PART 8 — CONVERGENCE ANALYSIS (steady-state stall factor)");
    std::cout << "  Running single-stream at physical arrival rate (2ns interval)\n";
    std::cout << "  Extracting per-wave overhead: Stall_Factor = Makespan / Ideal\n\n";

    std::cout << "  " << std::setw(8) << "N"
              << std::setw(10) << "Waves"
              << std::setw(14) << "Makespan(ns)"
              << std::setw(14) << "Ideal(ns)"
              << std::setw(14) << "StallFactor"
              << std::setw(12) << "RelErr(%)"
              << "\n";

    std::vector<size_t> sizes = {64, 128, 256, 512, 1024, 2048, 4096, 8192, 16384};
    for (size_t N : sizes) {
        auto r = run_stream(N, 2, 1, true, 0x900000, 0, false);
        double stall = (r.ideal_ns > 0 && r.makespan_ns > 0)
            ? static_cast<double>(r.makespan_ns) / r.ideal_ns : 0.0;
        std::cout << "  " << std::setw(8) << N
                  << std::setw(10) << r.credit_waves
                  << std::setw(14) << r.makespan_ns
                  << std::setw(14) << (uint64_t)r.ideal_ns
                  << std::setw(14) << stall
                  << std::setw(12) << r.relative_error * 100.0
                  << "\n";
    }
}

// ============================================================================
// MAIN
// ============================================================================
int main() {
    section("EXP-05B: CXLMemSim STREAM SCALING BENCHMARK");
    std::cout << "  Config: BW=32 GB/s, read_lat=300ns, write_lat=300ns\n";
    std::cout << "  MAX_QUEUE_SIZE=" << MAX_QUEUE_SIZE << ", INITIAL_CREDITS=" << INITIAL_CREDITS << "\n";
    std::cout << "  Pipeline latency = frontend(10) + forward(15) + read(300) + response(20) + protocol(6.5) = 351.5ns\n";

    part2_stream_length();
    part3_arrival_spacing();
    part4_multistream();
    part5_address_effect();
    part6_occupation();
    part7_block_scaling();
    part8_convergence();

    section("BENCHMARK COMPLETE — Share output to generate EXP05B_CXLMEMSIM_STREAM_SCALING.md");
    return 0;
}
