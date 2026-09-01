#pragma once
// VOIDFORGE triage — crash deduplication + exploitability ranking.
#include "common.h"
#include <string>
#include <vector>

namespace vf::triage {

struct TriageConfig {
    std::string crash_dir;      // directory containing crash files
    std::string binary_path;    // target binary (for symbolization)
    int top_frames = 3;         // frames to hash
    bool symbolize = false;     // attempt symbolization from crash text
};

struct TriagedCrash {
    std::string hash;           // SHA256(frame0||frame1||frame2)
    int exploitability;         // 0-6 scale (EXP_RIP_CONTROL = 6)
    std::string fault_type;     // SEGV, SIGABRT, HEAP_BUFFER_OVERFLOW, ...
    uint64_t fault_addr;
    std::vector<std::string> stack_frames;
    int duplicate_count;        // how many crashes share this hash
    std::string representative; // path to one crash file with this hash
};

// Triage all crashes in directory — sorted by exploitability (highest first)
std::vector<TriagedCrash> triage_crashes(const TriageConfig& config);

} // namespace vf::triage
