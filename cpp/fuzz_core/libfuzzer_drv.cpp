// VOIDFORGE libfuzzer_drv — subprocess wrapper around an instrumented
// libFuzzer target. The speed lives in the instrumented binary; this driver
// structures the campaign, parses final stats and harvests artifacts.
// Linux/Clang only (#ifdef __linux__ + fork/exec).
#include "libfuzzer_drv.h"

#include <cstdio>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <sstream>
#include <algorithm>

#ifdef __linux__
#include <unistd.h>
#include <sys/wait.h>
#include <sys/resource.h>
#endif

namespace vf::libfuzz {

namespace fs = std::filesystem;

FuzzResult run_campaign(const FuzzConfig& config) {
    FuzzResult r;
    uint64_t t0 = now_us();
#ifndef __linux__
    (void)config;
    r.error = "libfuzzer_drv requires Linux/WSL with Clang (-fsanitize=fuzzer)";
    r.elapsed_us = now_us() - t0;
    return r;
#else
    if (!fs::exists(config.target_path)) {
        r.error = "target not found: " + config.target_path;
        r.elapsed_us = now_us() - t0;
        return r;
    }
    fs::create_directories(config.artifact_dir);
    std::string stats_path = config.artifact_dir + "/fuzzer_stats_final.txt";

    // ---- fork/exec: target -runs=N -max_len= -artifact_prefix= -print_final_stats=1 ----
    pid_t pid = fork();
    if (pid == 0) {
        // child: redirect stdout+stderr to stats file
        FILE* f = freopen(stats_path.c_str(), "w", stdout);
        if (!f) _exit(127);
        dup2(fileno(stdout), fileno(stderr));

        std::vector<std::string> args;
        args.push_back(config.target_path);
        args.push_back("-max_total_time=" + std::to_string(config.max_seconds));
        args.push_back("-max_len=" + std::to_string(config.max_len));
        args.push_back("-artifact_prefix=" + config.artifact_dir + "/");
        args.push_back("-print_final_stats=1");
        args.push_back("-rss_limit_mb=4096");
        for (const auto& fl : config.extra_flags) args.push_back(fl);
        args.push_back(config.corpus_dir);

        std::vector<char*> argv;
        for (auto& a : args) argv.push_back(a.data());
        argv.push_back(nullptr);

        // cap the child so a runaway fuzzer cannot eat the box
        struct rlimit rl;
        rl.rlim_cur = (rlim_t)4 << 30;   // 4GB address space (64-bit math!)
        rl.rlim_max = (rlim_t)4 << 30;
        setrlimit(RLIMIT_AS, &rl);

        execv(config.target_path.c_str(), argv.data());
        _exit(127);   // exec failed
    } else if (pid < 0) {
        r.error = "fork failed";
        r.elapsed_us = now_us() - t0;
        return r;
    }

    int status = 0;
    waitpid(pid, &status, 0);
    r.elapsed_us = now_us() - t0;

    // ---- parse final stats ----
    std::ifstream sf(stats_path);
    if (sf) {
        std::string line;
        while (std::getline(sf, line)) {
            auto num_after = [&](const std::string& key) -> double {
                if (line.rfind(key, 0) == 0) {
                    try { return std::stod(line.substr(key.size())); } catch (...) {}
                }
                return -1.0;
            };
            double v;
            if ((v = num_after("stat::number_of_executed_units: ")) >= 0)
                r.total_execs = (uint64_t)v;
            else if ((v = num_after("stat::edge_coverage: ")) >= 0)
                r.coverage_pct = v;
            else if ((v = num_after("stat::corpus_size: ")) >= 0)
                r.corpus_size = (uint32_t)v;
        }
    }
    if (r.total_execs > 0 && r.elapsed_us > 0)
        r.execs_per_sec = (uint32_t)(r.total_execs * 1000000ull / r.elapsed_us);

    // ---- harvest artifacts ----
    try {
        for (const auto& e : fs::directory_iterator(config.artifact_dir))
            if (e.is_regular_file() &&
                e.path().filename().string().rfind("crash-", 0) == 0)
                r.crash_paths.push_back(e.path().string());
    } catch (...) {}
    std::sort(r.crash_paths.begin(), r.crash_paths.end());
#endif
    return r;
}

} // namespace vf::libfuzz
