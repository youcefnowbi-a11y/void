#pragma once
// VOIDFORGE libfuzzer_drv — programmatic libFuzzer campaign runner.
// Clang + -fsanitize=fuzzer ONLY (WSL/Linux). Never builds under MSVC.
#include "common.h"
#include <string>
#include <vector>

namespace vf::libfuzz {

struct FuzzConfig {
    std::string target_path;    // path to instrumented binary
    std::string corpus_dir;     // initial corpus directory
    std::string artifact_dir;   // where to write crashes
    uint32_t max_seconds = 60;
    uint32_t max_len = 4096;
    int jobs = 1;
    std::vector<std::string> extra_flags;
};

struct FuzzResult {
    uint64_t total_execs = 0;
    uint32_t execs_per_sec = 0;
    uint32_t corpus_size = 0;
    double coverage_pct = 0.0;
    std::vector<std::string> crash_paths;
    uint64_t elapsed_us = 0;
    std::string error;
};

FuzzResult run_campaign(const FuzzConfig& config);

} // namespace vf::libfuzz
