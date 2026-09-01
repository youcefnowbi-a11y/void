// VOIDFORGE heap_core — grooming oracle implementation.
// Measures the CRT/glibc allocator's own reuse behavior at a size class:
//   alloc A → free A → alloc B(same size) → B == A ?
// LIFO fastbins/tcache make immediate same-address reuse near-certain
// for small sizes — that is the grooming signal we quantify.
#include "groom.h"

#include <mutex>
#include <cstring>
#include <cstdlib>
#include <numeric>
#include <algorithm>

#ifdef _WIN32
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#endif

namespace vf::heap {

namespace {

struct AllocBook {
    std::vector<void*> ptrs;
    std::vector<size_t> sizes;
    std::vector<bool> freed;
    std::vector<std::string> content;   // last written pattern per slot
    std::mutex mu;
};
AllocBook& book() { static AllocBook b; return b; }

// free→realloc latency probe (single trial)
inline bool reuse_trial(size_t sz, uint64_t& dt_us) {
    void* a = std::malloc(sz);
    if (!a) return false;
    volatile uint8_t touch = *(volatile uint8_t*)a; (void)touch;
    std::free(a);
    uint64_t t0 = now_us();
    void* b = std::malloc(sz);
    dt_us = now_us() - t0;
    bool same = (b == a);
    std::free(b);
    return same;
}

#ifdef _WIN32
// SEH-guarded read of freed memory (UB by design — it IS the measurement)
bool safe_read(const void* p, size_t n, uint8_t* out) {
    __try {
        memcpy(out, p, n);
        return true;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return false;
    }
}
#else
bool safe_read(const void* p, size_t n, uint8_t* out) {
    // glibc never munmaps chunks < 128KB → read is safe in practice
    memcpy(out, p, n);
    return true;
}
#endif

} // anonymous namespace

std::vector<uint64_t> spray(size_t target_size, uint32_t count,
                             const std::string& pattern) {
    std::vector<uint64_t> out;
    std::lock_guard<std::mutex> lk(book().mu);
    out.reserve(count);
    for (uint32_t i = 0; i < count; ++i) {
        void* p = std::malloc(target_size);
        if (!p) break;
        // fill with the pattern, repeated to the allocation end
        size_t off = 0;
        const char* pd = pattern.empty() ? "V" : pattern.c_str();
        size_t pl = pattern.empty() ? 1 : pattern.size();
        while (off < target_size) {
            size_t chunk = std::min(pl, target_size - off);
            std::memcpy((uint8_t*)p + off, pd, chunk);
            off += chunk;
        }
        book().ptrs.push_back(p);
        book().sizes.push_back(target_size);
        book().freed.push_back(false);
        book().content.push_back(pattern.empty() ? std::string("V") : pattern);
        out.push_back((uint64_t)(uintptr_t)p);
    }
    return out;
}

void punch_holes(const std::vector<uint32_t>& indices) {
    std::lock_guard<std::mutex> lk(book().mu);
    for (uint32_t i : indices) {
        if (i < book().ptrs.size() && !book().freed[i]) {
            std::free(book().ptrs[i]);
            book().freed[i] = true;
        }
    }
}

std::vector<bool> check_reclamation(const std::string& expected_pattern) {
    std::vector<bool> out;
    std::lock_guard<std::mutex> lk(book().mu);
    out.reserve(book().ptrs.size());
    std::vector<uint8_t> probe(expected_pattern.size() ? expected_pattern.size() : 1);
    for (size_t i = 0; i < book().ptrs.size(); ++i) {
        if (!book().freed[i]) { out.push_back(false); continue; }
        size_t n = std::min(probe.size(), book().sizes[i]);
        // did the freed chunk keep our pattern (NOT reclaimed/overwritten),
        // or did someone else write there? "reclaimed by attacker" here is
        // approximated by: pattern destroyed → something reused the slot.
        if (safe_read(book().ptrs[i], n, probe.data())) {
            out.push_back(std::memcmp(probe.data(),
                                      book().content[i].data(), n) != 0);
        } else {
            out.push_back(false);   // unreadable (page dropped) — count as no
        }
    }
    return out;
}

GroomResult measure_reuse(const GroomConfig& config) {
    GroomResult r;
    size_t sz = std::max<size_t>(config.target_size, 1);

#ifdef _WIN32
    r.allocator = "ucrt-heap";
    r.actual_size_class = (sz + 15) & ~(size_t)15;   // 16-byte granularity
#else
    r.allocator = "ptmalloc(glibc)";
    // tcache bins are 16-byte spaced chunk sizes (request + 8 header → 16-align)
    r.actual_size_class = ((sz + 8 + 15) & ~(size_t)15) - 8;
#endif

    uint32_t trials = std::max(config.measure_trials, 1u);
    uint64_t hits = 0;
    uint64_t total_dt = 0;
    bool first_immediate = false;
    for (uint32_t t = 0; t < trials; ++t) {
        uint64_t dt = 0;
        if (reuse_trial(sz, dt)) {
            hits++;
            if (t == 0) first_immediate = true;
        }
        total_dt += dt;
    }
    r.reuse_rate = 100.0 * (double)hits / (double)trials;
    r.avg_reuse_us = total_dt / trials;
    r.tcache_hit = first_immediate;

    if (r.reuse_rate > 90.0)
        r.interpretation = "near-certain reclaim — UAF highly exploitable at this size class";
    else if (r.reuse_rate > 50.0)
        r.interpretation = "likely reclaim — groom with same-size spray";
    else
        r.interpretation = "unstable reclaim — widen spray or change size class";
    return r;
}

} // namespace vf::heap
