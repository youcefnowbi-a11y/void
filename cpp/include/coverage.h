#pragma once
// VOIDFORGE coverage bitmap operations — edge-hit merging.
#include "common.h"
#include <algorithm>

namespace vf {

// Edge-hit coverage: merge source bitmap into destination (OR)
inline void bitmap_merge(Bitmap& dst, const Bitmap& src) {
    for (size_t i = 0; i < BITMAP_SIZE; ++i)
        dst[i] |= src[i];
}

// Check if source has NEW coverage not in cumulative
inline bool has_new_coverage(const Bitmap& cumulative, const Bitmap& current) {
    for (size_t i = 0; i < BITMAP_SIZE; ++i)
        if (current[i] && !cumulative[i]) return true;
    return false;
}

// Coverage percentage
inline double coverage_pct(const Bitmap& bm) {
    return 100.0 * bitmap_count(bm) / BITMAP_SIZE;
}

} // namespace vf
