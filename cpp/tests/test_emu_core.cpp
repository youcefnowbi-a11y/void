// Placeholder test translation units — the authoritative acceptance
// suite lives in lab/cpp_acceptance.py (tests 1-12 of the plan).
// Real GTest bodies land in Phase 12; kept compilable so BUILD_TESTS=ON
// does not break the build.
#include <gtest/gtest.h>

TEST(VoidforgePlaceholder, Suite) {
    SUCCEED() << "acceptance enforced by lab/cpp_acceptance.py";
}
