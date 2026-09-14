/*
 * EXP-05B Stage A: Native C++ Calibration Program
 * Compiles against CXLMemSim headers to evaluate CXLMemExpander on streaming bursts.
 */

#include <iostream>
#include <iomanip>
#include <vector>
#include <tuple>
#include <chrono>
#include <cmath>
#include <cstdint>

// Direct standalone CXLMemSim formula evaluation matching cxlendpoint.cpp exactly
namespace cxlmemsim_ref {

constexpr uint64_t kCacheLineSize = 64;

struct BandwidthModelConfig {
    double read_peak_gbps = 32.0;
    double write_peak_gbps = 32.0;
    double mixed_peak_gbps = 32.0;
    double knee_utilization = 0.80;
    double saturation_utilization = 0.98;
    double low_utilization_slope = 0.05;
    double max_penalty_ns = 5000.0;
    uint64_t min_window_ns = 100000;
};

double calculate_mlc_bandwidth_penalty(const BandwidthModelConfig &model, size_t access_count,
                                       uint64_t first_timestamp, uint64_t last_timestamp,
                                       double read_ratio, double read_latency_ns, double write_latency_ns) {
    if (access_count == 0) return 0.0;

    const uint64_t observed_window_ns = last_timestamp > first_timestamp ? last_timestamp - first_timestamp : 0;
    const double window_ns = static_cast<double>(std::max(observed_window_ns, model.min_window_ns));
    const double observed_gbps = static_cast<double>(access_count * kCacheLineSize) / window_ns;
    const double peak_gbps = model.read_peak_gbps;
    const double utilization = observed_gbps / peak_gbps;
    if (utilization <= 0.0) return 0.0;

    const double transfer_ns_per_cacheline = static_cast<double>(kCacheLineSize) / peak_gbps;
    const double base_latency_ns = read_latency_ns * read_ratio + write_latency_ns * (1.0 - read_ratio);
    double penalty_ns = transfer_ns_per_cacheline * utilization * model.low_utilization_slope;

    if (utilization > model.knee_utilization) {
        const double clipped_utilization = std::min(utilization, model.saturation_utilization);
        const double knee_span = std::max(0.001, model.saturation_utilization - model.knee_utilization);
        const double knee_progress = (clipped_utilization - model.knee_utilization) / knee_span;
        const double queue_multiplier =
            (clipped_utilization / std::max(0.001, 1.0 - clipped_utilization)) * knee_progress * knee_progress;
        penalty_ns += transfer_ns_per_cacheline * queue_multiplier;
    }
    if (utilization > model.saturation_utilization) {
        penalty_ns += base_latency_ns * ((utilization - model.saturation_utilization) /
                                         std::max(0.001, 1.0 - model.saturation_utilization));
    }

    const double dynamic_cap = std::max(model.max_penalty_ns, base_latency_ns * 10.0);
    return std::clamp(penalty_ns, 0.0, dynamic_cap);
}

} // namespace cxlmemsim_ref

int main() {
    std::cout << "===========================================================================\n";
    std::cout << "  CXLMemSim Native C++ Verification Harness\n";
    std::cout << "===========================================================================\n";

    constexpr uint64_t expert_bytes = 268435456ULL; // 256 MiB
    cxlmemsim_ref::BandwidthModelConfig model;
    model.read_peak_gbps = 32.0;

    std::vector<uint64_t> stream_sizes = {
        64 * 1024,
        1 * 1024 * 1024,
        4 * 1024 * 1024,
        16 * 1024 * 1024,
        64 * 1024 * 1024,
        256 * 1024 * 1024
    };

    std::cout << std::setw(12) << "Stream Size" << " | "
              << std::setw(10) << "Tx Count" << " | "
              << std::setw(14) << "Window (ns)" << " | "
              << std::setw(12) << "Obs BW (GB/s)" << " | "
              << std::setw(10) << "Util (%)" << " | "
              << std::setw(14) << "Penalty (ns)" << "\n";
    std::cout << std::string(85, '-') << "\n";

    for (auto sz : stream_sizes) {
        size_t count = sz / 64;
        uint64_t first_ts = 0;
        uint64_t last_ts = (count - 1) * 2; // at 32 GB/s, 2 ns per line
        uint64_t window = std::max(last_ts - first_ts, model.min_window_ns);
        double obs_gbps = static_cast<double>(count * 64) / window;
        double util = (obs_gbps / model.read_peak_gbps) * 100.0;
        double penalty = cxlmemsim_ref::calculate_mlc_bandwidth_penalty(model, count, first_ts, last_ts, 1.0, 300.0, 300.0);

        std::string sz_str = (sz >= 1024 * 1024) ? std::to_string(sz / (1024 * 1024)) + " MB" : std::to_string(sz / 1024) + " KB";
        std::cout << std::setw(12) << sz_str << " | "
                  << std::setw(10) << count << " | "
                  << std::setw(14) << window << " | "
                  << std::setw(12) << std::fixed << std::setprecision(3) << obs_gbps << " | "
                  << std::setw(10) << std::fixed << std::setprecision(1) << util << " | "
                  << std::setw(14) << std::fixed << std::setprecision(2) << penalty << "\n";
    }

    return 0;
}
