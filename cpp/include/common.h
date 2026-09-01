#pragma once
// VOIDFORGE common types — shared across all hot cores.
// Contract: JSON-serializable results, no exceptions to Python,
// timing in microseconds, bitmaps are plain uint8_t[65536].
#include <cstdint>
#include <string>
#include <vector>
#include <array>
#include <chrono>
#include <stdexcept>

namespace vf {

// Microsecond clock — steady, monotonic
inline uint64_t now_us() {
    using namespace std::chrono;
    return duration_cast<microseconds>(
        steady_clock::now().time_since_epoch()).count();
}

// Safe error container — every public function returns this on failure
struct ErrorInfo {
    std::string error;
    std::string error_type;
    bool has_error = false;
};

// Coverage bitmap — fixed 64KB (same as AFL++)
constexpr size_t BITMAP_SIZE = 65536;
using Bitmap = std::array<uint8_t, BITMAP_SIZE>;

// Zero a bitmap
inline void bitmap_clear(Bitmap& bm) { bm.fill(0); }

// Count non-zero entries (coverage)
inline size_t bitmap_count(const Bitmap& bm) {
    size_t n = 0;
    for (auto b : bm) if (b) ++n;
    return n;
}

// Crash record
struct CrashRecord {
    std::string hash;           // SHA256(top 3 frames)
    uint64_t fault_addr;
    std::string fault_type;     // "SEGV", "SIGABRT", "HEAP_OVERFLOW", etc.
    std::vector<uint64_t> stack_frames;
    int exploitability;         // 0-6 (6 = RIP control, 0 = benign)
    std::string input_path;
    uint64_t timestamp_us;
};

// Exploitability ranking constants
enum Exploitability : int {
    EXP_RIP_CONTROL       = 6,  // instruction pointer controlled
    EXP_WRITE_WHAT_WHERE  = 5,  // arbitrary write primitive
    EXP_CONTROLLED_DEREF  = 4,  // controlled pointer dereference
    EXP_HEAP_CORRUPTION   = 3,  // heap metadata corruption
    EXP_STACK_OVERFLOW    = 2,  // stack buffer overflow
    EXP_DATA_ONLY         = 1,  // data-only corruption
    EXP_DOS               = 0,  // denial of service / benign crash
};

} // namespace vf
