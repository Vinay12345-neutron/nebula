/*
 * EXP-05B Batch Activation Validation Microbenchmark
 *
 * Question: For K expert transfers in one TierMoE batch step, does the CXLMemSim
 * queue exhibit:
 *   (A) T = K*N*Δt + T0       (one startup regardless of K)
 *   (B) T = K*N*Δt + K*T0     (startup per expert)
 *
 * Tests four scheduling modes for K = 1, 2, 4, 8, 16, 32:
 *   CONCAT:     All K*N requests on one shared CXLMemExpander, one continuous stream
 *   RR:         K*N requests interleaved round-robin on one expander
 *   CHUNKED:    N requests per expert submitted in chunks on one expander
 *   SEQUENTIAL: Fresh CXLMemExpander per expert (K independent activations)
 *
 * Compile:
 *   g++ -std=c++20 -O3 -Wno-subobject-linkage \
 *       -I calibration/stub_includes \
 *       -I /home/k8s-admin/Vinay/CXLMemSim/include \
 *       calibration/batch_activation_validation.cpp \
 *       /home/k8s-admin/Vinay/CXLMemSim/src/cxlendpoint.cpp \
 *       -o calibration/batch_activation && ./calibration/batch_activation
 *
 * N per expert: 4096 cache lines (256 KiB representative block)
 * Justification: from stream-scaling study, N=4096 at 2ns interval gives
 *   T_overhead = 19639 - 8192 = 11447 ns ≈ T0 = 11438 ns (calibrated).
 *   Convergence law error at N=4096: 139.7% of ideal — large but constant T0 is extractable.
 *
 * IMPORTANT: upstream CXLMemSim is NOT modified.
 */

#define SPDLOG_ACTIVE_LEVEL SPDLOG_LEVEL_OFF
#include <algorithm>
#include "cxlendpoint.h"
#include "coherency_engine.h"
#include <iostream>
#include <iomanip>
#include <vector>
#include <cstdint>
#include <chrono>
#include <numeric>
#include <memory>
#include <string>

// Stub for RemoteCXLExpander linker dependency (same as in all previous calibration binaries)
CoherencyResponse CoherencyEngine::process_read(const CoherencyRequest &) {
    return CoherencyResponse{0.0, MHSLDCacheState::SHARED, true, 0};
}

// ============================================================================
// CONSTANTS
// ============================================================================

static constexpr size_t   N_LINES_PER_EXPERT = 4096;   // cache lines per expert representative block
static constexpr uint64_t DELTA_T_NS         = 2;      // arrival interval = 64 / 32 GB/s = 2 ns
static constexpr double   BW_GBPS            = 32.0;
static constexpr double   LAT_NS             = 300.0;
static constexpr double   T0_CALIBRATED_NS   = 11438.0; // from stream-scaling study (N=64..4096, C=5719)

// ============================================================================
// FACTORY
// ============================================================================

static std::unique_ptr<CXLMemExpander> make_ep() {
    auto ep = std::make_unique<CXLMemExpander>(
        static_cast<int>(BW_GBPS), static_cast<int>(BW_GBPS),
        static_cast<int>(LAT_NS),  static_cast<int>(LAT_NS),
        0, 1 << 20);  // id=0, capacity=1 MiB
    BandwidthModelConfig cfg;
    cfg.read_peak_gbps       = BW_GBPS;
    cfg.write_peak_gbps      = BW_GBPS;
    cfg.knee_utilization     = 0.80;
    cfg.saturation_utilization = 0.98;
    cfg.low_utilization_slope  = 0.05;
    cfg.max_penalty_ns         = 5000.0;
    cfg.min_window_ns          = 100000;
    cfg.calibrated_from_mlc    = true;
    ep->configure_bandwidth_model(cfg);
    return ep;
}

// ============================================================================
// RESULT STRUCT
// ============================================================================

struct RunResult {
    size_t   K;
    size_t   N_per_expert;
    size_t   total_submitted;
    size_t   accepted;
    size_t   rejected;
    size_t   peak_queue;
    uint64_t makespan_ns;
    double   ideal_ns;     // K * N * 2 ns
    double   overhead_ns;  // makespan - ideal
    double   rel_overhead; // overhead / ideal
    double   cpu_ms;
    // Predictions
    double   model_A_ns;   // ideal only
    double   model_B_ns;   // ideal + T0
    double   model_C_ns;   // ideal + K*T0
    double   err_A_ns;
    double   err_B_ns;
    double   err_C_ns;
    std::string mode;
    size_t   n_expander_instances; // how many CXLMemExpander objects used
};

// ============================================================================
// SHARED-EXPANDER RUNNER (CONCAT, RR, CHUNKED all use this)
// ============================================================================

static RunResult run_shared(
    size_t K, const std::string &mode, bool round_robin,
    uint64_t base_addr = 0x100000ULL)
{
    auto ep = make_ep();

    const size_t total_N = K * N_LINES_PER_EXPERT;
    const uint64_t cacheline = 64;

    // Build schedule
    struct Req { uint64_t ts; uint64_t addr; };
    std::vector<Req> schedule;
    schedule.reserve(total_N);

    if (mode == "CONCAT") {
        // All K*N requests as one contiguous stream
        for (size_t i = 0; i < total_N; ++i) {
            schedule.push_back({i * DELTA_T_NS,
                                base_addr + i * cacheline});
        }
    } else if (mode == "RR") {
        // Round-robin: request 0 of expert 0, request 0 of expert 1, ...
        for (size_t l = 0; l < N_LINES_PER_EXPERT; ++l) {
            for (size_t k = 0; k < K; ++k) {
                size_t idx = l * K + k;
                schedule.push_back({idx * DELTA_T_NS,
                                    base_addr + (k * N_LINES_PER_EXPERT + l) * cacheline});
            }
        }
    } else { // CHUNKED
        // All N lines of expert 0, then all N lines of expert 1, ...
        for (size_t k = 0; k < K; ++k) {
            for (size_t l = 0; l < N_LINES_PER_EXPERT; ++l) {
                size_t idx = k * N_LINES_PER_EXPERT + l;
                schedule.push_back({idx * DELTA_T_NS,
                                    base_addr + idx * cacheline});
            }
        }
        // Same as CONCAT with same addresses — address doesn't matter (confirmed)
        // We use the same timestamps so this is identical to CONCAT.
        // To make CHUNKED truly distinguishable, we note: since addresses are unique
        // and CXLMemSim ignores TID/address for timing, CHUNKED == CONCAT.
        // We keep it as a separate measurement to verify this empirically.
    }

    auto wall_start = std::chrono::high_resolution_clock::now();

    size_t inject_idx = 0, accepted = 0, rejected = 0, peak_q = 0;
    uint64_t current_time = 0;

    while (true) {
        // Inject all due
        while (inject_idx < schedule.size() && schedule[inject_idx].ts <= current_time) {
            auto &r = schedule[inject_idx];
            int ret = ep->insert(r.ts, 0, r.addr, r.addr, 0);
            if (ret != 0) accepted++;
            else          rejected++;
            size_t qs;
            { std::lock_guard<std::mutex> lk(ep->queue_mutex_);
              qs = ep->request_queue_.size() + ep->in_flight_requests_.size(); }
            if (qs > peak_q) peak_q = qs;
            inject_idx++;
        }

        ep->process_queued_requests(current_time);

        bool all_in = (inject_idx >= schedule.size());
        bool q_empty, if_empty;
        uint64_t next_complete = UINT64_MAX;
        { std::lock_guard<std::mutex> lk(ep->queue_mutex_);
          q_empty  = ep->request_queue_.empty();
          if_empty = ep->in_flight_requests_.empty();
          for (auto &[a, req] : ep->in_flight_requests_)
              if (req.complete_time < next_complete) next_complete = req.complete_time; }

        if (all_in && q_empty && if_empty) break;

        uint64_t next_arrival = (inject_idx < schedule.size()) ? schedule[inject_idx].ts : UINT64_MAX;
        uint64_t next_event = std::min(next_arrival, next_complete);
        current_time = (next_event == UINT64_MAX) ? current_time + 1 : next_event;
    }

    // Collect straggling in-flight
    { std::lock_guard<std::mutex> lk(ep->queue_mutex_);
      for (auto &[a, req] : ep->in_flight_requests_)
          if (req.complete_time > current_time) current_time = req.complete_time; }

    auto wall_end = std::chrono::high_resolution_clock::now();
    double cpu_ms = std::chrono::duration<double, std::milli>(wall_end - wall_start).count();

    double ideal_ns    = static_cast<double>(total_N) * DELTA_T_NS;
    double overhead_ns = static_cast<double>(current_time) - ideal_ns;

    RunResult r{};
    r.K                  = K;
    r.N_per_expert       = N_LINES_PER_EXPERT;
    r.total_submitted    = total_N;
    r.accepted           = accepted;
    r.rejected           = rejected;
    r.peak_queue         = peak_q;
    r.makespan_ns        = current_time;
    r.ideal_ns           = ideal_ns;
    r.overhead_ns        = overhead_ns;
    r.rel_overhead       = ideal_ns > 0 ? overhead_ns / ideal_ns : 0;
    r.cpu_ms             = cpu_ms;
    r.mode               = mode;
    r.n_expander_instances = 1;
    r.model_A_ns         = ideal_ns;
    r.model_B_ns         = ideal_ns + T0_CALIBRATED_NS;
    r.model_C_ns         = ideal_ns + K * T0_CALIBRATED_NS;
    r.err_A_ns           = static_cast<double>(current_time) - r.model_A_ns;
    r.err_B_ns           = static_cast<double>(current_time) - r.model_B_ns;
    r.err_C_ns           = static_cast<double>(current_time) - r.model_C_ns;
    return r;
}

// ============================================================================
// SEQUENTIAL ACTIVATION RUNNER (fresh CXLMemExpander per expert)
// ============================================================================

static RunResult run_sequential(size_t K, uint64_t base_addr = 0x900000ULL) {
    auto wall_start = std::chrono::high_resolution_clock::now();

    size_t accepted = 0, rejected = 0, peak_q = 0;
    uint64_t global_time = 0;

    for (size_t k = 0; k < K; ++k) {
        auto ep = make_ep();
        // Submit N lines at 2ns intervals, global timestamps monotonically increasing
        for (size_t l = 0; l < N_LINES_PER_EXPERT; ++l) {
            uint64_t ts = global_time + l * DELTA_T_NS;
            uint64_t addr = base_addr + (k * N_LINES_PER_EXPERT + l) * 64;
            int ret = ep->insert(ts, 0, addr, addr, 0);
            if (ret != 0) accepted++;
            else          rejected++;
            size_t qs;
            { std::lock_guard<std::mutex> lk(ep->queue_mutex_);
              qs = ep->request_queue_.size() + ep->in_flight_requests_.size(); }
            if (qs > peak_q) peak_q = qs;
        }

        // Drain this expert's expander
        uint64_t local_time = global_time;
        while (true) {
            ep->process_queued_requests(local_time);
            bool q_empty, if_empty;
            uint64_t next_complete = UINT64_MAX;
            { std::lock_guard<std::mutex> lk(ep->queue_mutex_);
              q_empty  = ep->request_queue_.empty();
              if_empty = ep->in_flight_requests_.empty();
              for (auto &[a, req] : ep->in_flight_requests_)
                  if (req.complete_time < next_complete) next_complete = req.complete_time; }
            if (q_empty && if_empty) break;
            local_time = (next_complete == UINT64_MAX) ? local_time + 1 : next_complete;
        }
        global_time = local_time; // time continues forward for the next expert
    }

    auto wall_end = std::chrono::high_resolution_clock::now();
    double cpu_ms = std::chrono::duration<double, std::milli>(wall_end - wall_start).count();

    size_t total_N     = K * N_LINES_PER_EXPERT;
    double ideal_ns    = static_cast<double>(total_N) * DELTA_T_NS;
    double overhead_ns = static_cast<double>(global_time) - ideal_ns;

    RunResult r{};
    r.K                  = K;
    r.N_per_expert       = N_LINES_PER_EXPERT;
    r.total_submitted    = total_N;
    r.accepted           = accepted;
    r.rejected           = rejected;
    r.peak_queue         = peak_q;
    r.makespan_ns        = global_time;
    r.ideal_ns           = ideal_ns;
    r.overhead_ns        = overhead_ns;
    r.rel_overhead       = ideal_ns > 0 ? overhead_ns / ideal_ns : 0;
    r.cpu_ms             = cpu_ms;
    r.mode               = "SEQUENTIAL";
    r.n_expander_instances = K;
    r.model_A_ns         = ideal_ns;
    r.model_B_ns         = ideal_ns + T0_CALIBRATED_NS;
    r.model_C_ns         = ideal_ns + K * T0_CALIBRATED_NS;
    r.err_A_ns           = static_cast<double>(global_time) - r.model_A_ns;
    r.err_B_ns           = static_cast<double>(global_time) - r.model_B_ns;
    r.err_C_ns           = static_cast<double>(global_time) - r.model_C_ns;
    return r;
}

// ============================================================================
// PRINT HELPERS
// ============================================================================

static void section(const std::string &s) {
    std::cout << "\n" << std::string(88, '=') << "\n  " << s << "\n" << std::string(88, '=') << "\n";
}

static void print_header() {
    std::cout << std::fixed << std::setprecision(1);
    std::cout
        << std::setw(10) << "Mode"
        << std::setw(4)  << "K"
        << std::setw(9)  << "Total_N"
        << std::setw(8)  << "Accept"
        << std::setw(8)  << "Reject"
        << std::setw(7)  << "PeakQ"
        << std::setw(13) << "Makespan(ns)"
        << std::setw(12) << "Ideal(ns)"
        << std::setw(12) << "Ovhd(ns)"
        << std::setw(10) << "Ovhd/T0"
        << std::setw(11) << "ErrA(ns)"
        << std::setw(11) << "ErrB(ns)"
        << std::setw(11) << "ErrC(ns)"
        << std::setw(8)  << "CPU(ms)"
        << "\n";
}

static void print_row(const RunResult &r) {
    double ovhd_in_T0 = r.overhead_ns / T0_CALIBRATED_NS;
    std::cout
        << std::setw(10) << r.mode
        << std::setw(4)  << r.K
        << std::setw(9)  << r.total_submitted
        << std::setw(8)  << r.accepted
        << std::setw(8)  << r.rejected
        << std::setw(7)  << r.peak_queue
        << std::setw(13) << r.makespan_ns
        << std::setw(12) << (uint64_t)r.ideal_ns
        << std::setw(12) << (int64_t)r.overhead_ns
        << std::setw(10) << ovhd_in_T0
        << std::setw(11) << (int64_t)r.err_A_ns
        << std::setw(11) << (int64_t)r.err_B_ns
        << std::setw(11) << (int64_t)r.err_C_ns
        << std::setw(8)  << r.cpu_ms
        << "\n";
}

// ============================================================================
// MAIN
// ============================================================================

int main() {
    section("EXP-05B BATCH ACTIVATION VALIDATION");
    std::cout << "  BW=" << BW_GBPS << " GB/s, lat=" << LAT_NS
              << " ns, N_per_expert=" << N_LINES_PER_EXPERT
              << " cachelines (" << (N_LINES_PER_EXPERT * 64 / 1024) << " KiB)\n";
    std::cout << "  Arrival interval Δt=" << DELTA_T_NS << " ns (physical link rate)\n";
    std::cout << "  T0_calibrated=" << T0_CALIBRATED_NS << " ns\n";
    std::cout << "  INITIAL_CREDITS=" << INITIAL_CREDITS << ", MAX_QUEUE_SIZE=" << MAX_QUEUE_SIZE << "\n";
    std::cout << "  Columns: ErrA = makespan - Model_A(V/BW), ErrB = makespan - Model_B(V/BW+T0), ErrC = makespan - Model_C(V/BW+K*T0)\n";
    std::cout << "  Ovhd/T0 = (makespan - ideal) / T0_calibrated (should be ~1 for Model B, ~K for Model C)\n\n";

    std::vector<size_t> Ks = {1, 2, 4, 8, 16, 32};

    // ---- CONCAT ----
    section("PART 3A — CONCAT: K*N requests as one contiguous stream on ONE expander");
    std::cout << "  One CXLMemExpander, sequential timestamps, unique addresses per cacheline.\n";
    std::cout << "  All experts concatenated as a single uninterrupted byte stream.\n\n";
    print_header();
    std::vector<RunResult> concat_results;
    for (size_t K : Ks) {
        auto r = run_shared(K, "CONCAT", false, 0x100000ULL);
        print_row(r);
        concat_results.push_back(r);
    }

    // ---- RR ----
    section("PART 3B — RR: K*N requests interleaved round-robin on ONE expander");
    std::cout << "  One CXLMemExpander; expert 0 line 0, expert 1 line 0, ..., expert 0 line 1, ...\n\n";
    print_header();
    std::vector<RunResult> rr_results;
    for (size_t K : Ks) {
        auto r = run_shared(K, "RR", true, 0x200000ULL);
        print_row(r);
        rr_results.push_back(r);
    }

    // ---- CHUNKED ----
    section("PART 3C — CHUNKED: N-line chunks per expert on ONE expander");
    std::cout << "  One CXLMemExpander; all N lines of expert 0 then all N lines of expert 1, etc.\n";
    std::cout << "  Sequential addresses; same timestamp sequence as CONCAT (should be identical).\n\n";
    print_header();
    std::vector<RunResult> chunk_results;
    for (size_t K : Ks) {
        auto r = run_shared(K, "CHUNKED", false, 0x400000ULL);
        print_row(r);
        chunk_results.push_back(r);
    }

    // ---- SEQUENTIAL ----
    section("PART 3D — SEQUENTIAL: Fresh CXLMemExpander per expert (K independent activations)");
    std::cout << "  K separate CXLMemExpander instances, each drained before starting the next.\n";
    std::cout << "  Global time is threaded forward monotonically across activations.\n\n";
    print_header();
    std::vector<RunResult> seq_results;
    for (size_t K : Ks) {
        auto r = run_sequential(K, 0x700000ULL);
        print_row(r);
        seq_results.push_back(r);
    }

    // ---- OVERHEAD COMPARISON TABLE ----
    section("PART 7 — KEY MATHEMATICAL TEST: Overhead vs K");
    std::cout << "  T0_calibrated = " << T0_CALIBRATED_NS << " ns\n";
    std::cout << "  If Ovhd ≈ T0 (constant): Model B (T=V/BW+T0) is supported\n";
    std::cout << "  If Ovhd ≈ K*T0: Model C (T=V/BW+K*T0) is supported\n\n";

    std::cout << std::setw(12) << "K"
              << std::setw(14) << "CONCAT_Ovhd"
              << std::setw(14) << "CONCAT/T0"
              << std::setw(14) << "RR_Ovhd"
              << std::setw(14) << "RR/T0"
              << std::setw(14) << "CHUNKED_Ovhd"
              << std::setw(14) << "CHUNKED/T0"
              << std::setw(14) << "SEQ_Ovhd"
              << std::setw(14) << "SEQ/T0"
              << std::setw(14) << "SEQ/CONCAT"
              << "\n";

    for (size_t i = 0; i < Ks.size(); ++i) {
        size_t K = Ks[i];
        double co = concat_results[i].overhead_ns;
        double ro = rr_results[i].overhead_ns;
        double ho = chunk_results[i].overhead_ns;
        double so = seq_results[i].overhead_ns;
        std::cout << std::setw(12) << K
                  << std::setw(14) << (int64_t)co
                  << std::setw(14) << co / T0_CALIBRATED_NS
                  << std::setw(14) << (int64_t)ro
                  << std::setw(14) << ro / T0_CALIBRATED_NS
                  << std::setw(14) << (int64_t)ho
                  << std::setw(14) << ho / T0_CALIBRATED_NS
                  << std::setw(14) << (int64_t)so
                  << std::setw(14) << so / T0_CALIBRATED_NS
                  << std::setw(14) << (co > 0 ? so / co : 0)
                  << "\n";
    }

    section("PART 8 — MODEL PREDICTION ERRORS");
    std::cout << "  Positive error = makespan > model prediction (model underestimates)\n";
    std::cout << "  Negative error = makespan < model prediction (model overestimates)\n\n";
    for (auto &mode_results : {
            std::make_pair(std::string("CONCAT"),   &concat_results),
            std::make_pair(std::string("RR"),        &rr_results),
            std::make_pair(std::string("CHUNKED"),   &chunk_results),
            std::make_pair(std::string("SEQUENTIAL"),&seq_results)}) {
        std::cout << "  Mode: " << mode_results.first << "\n";
        std::cout << std::setw(6) << "K"
                  << std::setw(16) << "Makespan(ns)"
                  << std::setw(16) << "ErrA(ns)"
                  << std::setw(12) << "ErrA(%)"
                  << std::setw(16) << "ErrB(ns)"
                  << std::setw(12) << "ErrB(%)"
                  << std::setw(16) << "ErrC(ns)"
                  << std::setw(12) << "ErrC(%)"
                  << "\n";
        for (auto &r : *mode_results.second) {
            double ms = static_cast<double>(r.makespan_ns);
            std::cout << std::setw(6) << r.K
                      << std::setw(16) << r.makespan_ns
                      << std::setw(16) << (int64_t)r.err_A_ns
                      << std::setw(12) << (ms > 0 ? r.err_A_ns/ms*100 : 0)
                      << std::setw(16) << (int64_t)r.err_B_ns
                      << std::setw(12) << (ms > 0 ? r.err_B_ns/ms*100 : 0)
                      << std::setw(16) << (int64_t)r.err_C_ns
                      << std::setw(12) << (ms > 0 ? r.err_C_ns/ms*100 : 0)
                      << "\n";
        }
        std::cout << "\n";
    }

    section("BENCHMARK COMPLETE — Share output to write EXP05B_CXLMEMSIM_BATCH_ACTIVATION_VALIDATION.md");
    return 0;
}
