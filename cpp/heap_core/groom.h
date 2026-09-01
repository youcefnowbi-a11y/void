#pragma once
// VOIDFORGE heap_core — heap grooming oracle (v2, research-grade).
// Measures allocator reuse probability for a size class — the question
// after a UAF/overflow: can the freed chunk be reclaimed with
// attacker-controlled data?
#include "common.h"
#include <string>
#include <vector>

namespace vf::heap {

struct GroomConfig {
    size_t target_size = 64;        // size class to target
    uint32_t spray_count = 256;     // how many objects to allocate
    std::string pattern = "VF";     // byte pattern for spray content
    uint32_t measure_trials = 1000; // reuse measurement trials
};

struct GroomResult {
    double reuse_rate = 0.0;        // P(reclamation) observed over trials
    uint64_t avg_reuse_us = 0;      // average time to reuse
    size_t actual_size_class = 0;   // actual allocator size class used
    std::string allocator;          // "ucrt-heap"/"ptmalloc(glibc)"
    bool tcache_hit = false;        // immediate same-address reuse
    std::string interpretation;
};

// Measure reuse probability for a given size class
GroomResult measure_reuse(const GroomConfig& config);

// Spray: allocate N objects of target_size filled with pattern
// Returns pointers (as uint64_t addresses) for verification
std::vector<uint64_t> spray(size_t target_size, uint32_t count,
                             const std::string& pattern);

// Punch holes at specific indices (free those allocations)
void punch_holes(const std::vector<uint32_t>& indices);

// Check which holes were reclaimed (read back and compare pattern)
// NOTE: reads freed memory — deliberate, that is the measurement.
// Guarded by SEH on Windows; safe on Linux for sizes < 128KB.
std::vector<bool> check_reclamation(const std::string& expected_pattern);

} // namespace vf::heap
