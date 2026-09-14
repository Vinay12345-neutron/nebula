/*
 * EXP-05B Stage B: Microvalidation Harness for CXLMemSim
 * Investigates:
 * 1. Part 3: Concurrent arrivals at t=0 (4, 8, 32, 64 requests) through real queue path.
 * 2. Part 4: Sequential spaced arrivals (t=0, 1000, 2000, 3000 ns).
 * 3. Part 5: Same stream (tid=0) vs multi-stream (tid=0,1,2,3).
 * 4. Part 6: Access-vector API (calculate_bandwidth / calculate_latency) comparison.
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

// Stub implementation for CoherencyEngine::process_read referenced by RemoteCXLExpander in cxlendpoint.cpp.
// (CXLMemExpander does not use RemoteCXLExpander, but cxlendpoint.cpp contains both classes).
CoherencyResponse CoherencyEngine::process_read(const CoherencyRequest &) {
    return CoherencyResponse{0.0, MHSLDCacheState::SHARED, true, 0};
}

namespace {

void print_header(const std::string &title) {
    std::cout << "\n" << std::string(75, '=') << "\n";
    std::cout << "  " << title << "\n";
    std::cout << std::string(75, '=') << "\n";
}

BandwidthModelConfig get_test_bw_config(double bw_gbps = 32.0) {
    BandwidthModelConfig cfg;
    cfg.read_peak_gbps = bw_gbps;
    cfg.write_peak_gbps = bw_gbps;
    cfg.knee_utilization = 0.80;
    cfg.saturation_utilization = 0.98;
    cfg.low_utilization_slope = 0.05;
    cfg.max_penalty_ns = 5000.0;
    cfg.min_window_ns = 100000;
    cfg.calibrated_from_mlc = true;
    return cfg;
}

// Drain queue simulation driver: advances time step-by-step or jump-to-next-event
struct RequestEventLog {
    uint64_t tid;
    uint64_t addr;
    uint64_t submit_time;
    uint64_t issue_time;
    uint64_t complete_time;
    double latency_ns;
};

std::vector<RequestEventLog> drain_queue_event_driven(CXLMemExpander &ep, uint64_t start_time) {
    std::vector<RequestEventLog> completed_events;
    uint64_t current_time = start_time;

    // Process queued requests to initiate the first batch of in-flight requests
    ep.process_queued_requests(current_time);

    while (true) {
        // Find the earliest completion time among in-flight requests
        uint64_t next_complete_time = UINT64_MAX;
        {
            std::lock_guard<std::mutex> lock(ep.queue_mutex_);
            if (ep.request_queue_.empty() && ep.in_flight_requests_.empty()) {
                break; // All requests completely processed and retired
            }
            for (const auto &[addr, req] : ep.in_flight_requests_) {
                if (req.complete_time < next_complete_time) {
                    next_complete_time = req.complete_time;
                }
            }
        }

        if (next_complete_time == UINT64_MAX) {
            // No in-flight request, but request_queue_ has items waiting for credits
            current_time += 1;
        } else {
            current_time = next_complete_time;
        }

        // Before process_queued_requests erases them, log completing requests
        {
            std::lock_guard<std::mutex> lock(ep.queue_mutex_);
            for (const auto &[addr, req] : ep.in_flight_requests_) {
                if (req.complete_time <= current_time) {
                    completed_events.push_back({
                        req.tid,
                        req.address,
                        req.timestamp,
                        req.issue_time,
                        req.complete_time,
                        static_cast<double>(req.complete_time - req.timestamp)
                    });
                }
            }
        }

        // Advance CXLMemExpander queue pipeline
        ep.process_queued_requests(current_time);
    }

    return completed_events;
}

} // namespace

int main() {
    print_header("EXP-05B MICROVALIDATION: REAL QUEUE PATH VS. ANALYTICAL API");

    // -------------------------------------------------------------------------
    // TEST 1: Part 3 - Concurrent 4 Requests at t=0 (TIDs 0, 1, 2, 3)
    // -------------------------------------------------------------------------
    {
        print_header("TEST 1: Part 3 - 4 Concurrent Requests at t=0 ns (TIDs 0, 1, 2, 3)");
        CXLMemExpander ep(32, 32, 300, 300, 0, 64);
        ep.configure_bandwidth_model(get_test_bw_config(32.0));

        uint64_t addrs[4] = {0x1000, 0x2000, 0x3000, 0x4000};
        for (int i = 0; i < 4; i++) {
            int ret = ep.insert(0, i, addrs[i], addrs[i], 0);
            std::cout << "  * Submitted Req " << i << " (tid=" << i << ", addr=" << std::hex << addrs[i] << std::dec
                      << ") -> insert() return=" << ret << " | Queue Size=" << ep.request_queue_.size() << "\n";
        }

        auto logs = drain_queue_event_driven(ep, 0);

        std::cout << "\n  Execution Log (Real Queue Pipeline):\n";
        std::cout << "  " << std::setw(6) << "TID" << " | "
                  << std::setw(10) << "Address" << " | "
                  << std::setw(12) << "Submit (ns)" << " | "
                  << std::setw(12) << "Issue (ns)" << " | "
                  << std::setw(14) << "Complete (ns)" << " | "
                  << std::setw(14) << "Latency (ns)" << "\n";
        std::cout << "  " << std::string(75, '-') << "\n";
        uint64_t makespan_4 = 0;
        for (const auto &log : logs) {
            std::cout << "  " << std::setw(6) << log.tid << " | "
                      << std::setw(10) << std::hex << log.addr << std::dec << " | "
                      << std::setw(12) << log.submit_time << " | "
                      << std::setw(12) << log.issue_time << " | "
                      << std::setw(14) << log.complete_time << " | "
                      << std::setw(14) << std::fixed << std::setprecision(1) << log.latency_ns << "\n";
            if (log.complete_time > makespan_4) makespan_4 = log.complete_time;
        }
        std::cout << "  => Final Makespan for 4 concurrent requests: " << makespan_4 << " ns\n";
    }

    // -------------------------------------------------------------------------
    // TEST 2: Part 3 - 8, 32, 64 Requests at t=0
    // -------------------------------------------------------------------------
    int batch_counts[4] = {8, 32, 64, 65};
    for (int count : batch_counts) {
        print_header("TEST 2: Concurrent Batch Size N = " + std::to_string(count) + " at t=0 ns");
        CXLMemExpander ep(32, 32, 300, 300, 0, 64);
        ep.configure_bandwidth_model(get_test_bw_config(32.0));

        int accepted = 0;
        int rejected = 0;
        for (int i = 0; i < count; i++) {
            uint64_t addr = 0x10000 + i * 64;
            int ret = ep.insert(0, i, addr, addr, 0);
            if (ret != 0) accepted++;
            else rejected++;
        }
        std::cout << "  * Submitted " << count << " requests: Accepted=" << accepted
                  << ", Rejected (Queue Full)=" << rejected
                  << " | Peak Queue Depth=" << ep.request_queue_.size() << "\n";

        auto logs = drain_queue_event_driven(ep, 0);
        uint64_t makespan = 0;
        double sum_lat = 0;
        for (const auto &log : logs) {
            sum_lat += log.latency_ns;
            if (log.complete_time > makespan) makespan = log.complete_time;
        }
        double avg_lat = logs.empty() ? 0 : sum_lat / logs.size();
        std::cout << "  * Retired Requests: " << logs.size()
                  << " | Avg Latency: " << std::fixed << std::setprecision(2) << avg_lat << " ns"
                  << " | Final Makespan: " << makespan << " ns\n";
    }

    // -------------------------------------------------------------------------
    // TEST 3: Part 4 - Sequential Spaced Arrivals (t = 0, 1000, 2000, 3000 ns)
    // -------------------------------------------------------------------------
    {
        print_header("TEST 3: Part 4 - Sequential Control: 4 Spaced Requests (0, 1000, 2000, 3000 ns)");
        CXLMemExpander ep(32, 32, 300, 300, 0, 64);
        ep.configure_bandwidth_model(get_test_bw_config(32.0));

        uint64_t timestamps[4] = {0, 1000, 2000, 3000};
        uint64_t addrs[4] = {0x1000, 0x2000, 0x3000, 0x4000};
        std::vector<RequestEventLog> all_logs;

        for (int i = 0; i < 4; i++) {
            ep.insert(timestamps[i], i, addrs[i], addrs[i], 0);
        }
        auto logs = drain_queue_event_driven(ep, 0);

        std::cout << "  " << std::setw(6) << "TID" << " | "
                  << std::setw(10) << "Address" << " | "
                  << std::setw(12) << "Submit (ns)" << " | "
                  << std::setw(12) << "Issue (ns)" << " | "
                  << std::setw(14) << "Complete (ns)" << " | "
                  << std::setw(14) << "Latency (ns)" << "\n";
        std::cout << "  " << std::string(75, '-') << "\n";
        uint64_t makespan_spaced = 0;
        for (const auto &log : logs) {
            std::cout << "  " << std::setw(6) << log.tid << " | "
                      << std::setw(10) << std::hex << log.addr << std::dec << " | "
                      << std::setw(12) << log.submit_time << " | "
                      << std::setw(12) << log.issue_time << " | "
                      << std::setw(14) << log.complete_time << " | "
                      << std::setw(14) << std::fixed << std::setprecision(1) << log.latency_ns << "\n";
            if (log.complete_time > makespan_spaced) makespan_spaced = log.complete_time;
        }
        std::cout << "  => Final Makespan for spaced requests: " << makespan_spaced << " ns\n";
    }

    // -------------------------------------------------------------------------
    // TEST 4: Part 5 - Same Stream (tid=0) vs Multi-Stream (tids 0,1,2,3)
    // -------------------------------------------------------------------------
    {
        print_header("TEST 4: Part 5 - Same TID (tid=0) vs Multi-TID (0,1,2,3) at t=0");
        CXLMemExpander ep_same(32, 32, 300, 300, 0, 64);
        ep_same.configure_bandwidth_model(get_test_bw_config(32.0));
        for (int i = 0; i < 4; i++) {
            ep_same.insert(0, 0, 0x1000 + i * 64, 0x1000 + i * 64, 0);
        }
        auto logs_same = drain_queue_event_driven(ep_same, 0);

        CXLMemExpander ep_multi(32, 32, 300, 300, 0, 64);
        ep_multi.configure_bandwidth_model(get_test_bw_config(32.0));
        for (int i = 0; i < 4; i++) {
            ep_multi.insert(0, i, 0x1000 + i * 64, 0x1000 + i * 64, 0);
        }
        auto logs_multi = drain_queue_event_driven(ep_multi, 0);

        std::cout << "  * Same TID Makespan:  " << logs_same.back().complete_time << " ns | Avg Lat: "
                  << (logs_same[0].latency_ns + logs_same[1].latency_ns + logs_same[2].latency_ns + logs_same[3].latency_ns) / 4.0 << " ns\n";
        std::cout << "  * Multi-TID Makespan: " << logs_multi.back().complete_time << " ns | Avg Lat: "
                  << (logs_multi[0].latency_ns + logs_multi[1].latency_ns + logs_multi[2].latency_ns + logs_multi[3].latency_ns) / 4.0 << " ns\n";
        bool identical = (logs_same.back().complete_time == logs_multi.back().complete_time);
        std::cout << "  => Are Same-TID and Multi-TID queue timings identical? " << (identical ? "YES (Queue is agnostic to TID)" : "NO") << "\n";
    }

    // -------------------------------------------------------------------------
    // TEST 5: Part 6 - Access-Vector API Comparison
    // -------------------------------------------------------------------------
    {
        print_header("TEST 5: Part 6 - Access Vector API (calculate_bandwidth / calculate_latency)");
        CXLMemExpander ep(32, 32, 300, 300, 0, 64);
        ep.configure_bandwidth_model(get_test_bw_config(32.0));

        // Register addresses in occupation so is_address_local returns true
        for (int i = 0; i < 4; i++) {
            ep.occupation.push_back({0, 0x1000ULL + i * 64, 0});
        }
        ep.invalidate_cache();

        std::vector<std::tuple<uint64_t, uint64_t>> accesses_t0 = {
            {0, 0x1000}, {0, 0x1040}, {0, 0x1080}, {0, 0x10c0}
        };

        double bw_penalty_t0 = ep.calculate_bandwidth(accesses_t0);
        double avg_lat_t0 = ep.calculate_latency(accesses_t0, 110.0);

        std::cout << "  * 4 Accesses at t=0 ns:\n";
        std::cout << "    - calculate_bandwidth() penalty: " << bw_penalty_t0 << " ns\n";
        std::cout << "    - calculate_latency() average:   " << avg_lat_t0 << " ns\n";

        std::vector<std::tuple<uint64_t, uint64_t>> accesses_spaced = {
            {0, 0x1000}, {1000, 0x1040}, {2000, 0x1080}, {3000, 0x10c0}
        };

        double bw_penalty_spaced = ep.calculate_bandwidth(accesses_spaced);
        double avg_lat_spaced = ep.calculate_latency(accesses_spaced, 110.0);

        std::cout << "  * 4 Accesses Spaced (0, 1000, 2000, 3000 ns):\n";
        std::cout << "    - calculate_bandwidth() penalty: " << bw_penalty_spaced << " ns\n";
        std::cout << "    - calculate_latency() average:   " << avg_lat_spaced << " ns\n";
    }

    print_header("MICROVALIDATION COMPLETE");
    return 0;
}
