# VOIDFORGE C++ unit tests (optional — needs GTest)
# These mirror lab/cpp_acceptance.py checks at the C++ level.
add_executable(vf_tests
    test_emu_core.cpp
    test_net_pacer.cpp
    test_triage.cpp
    test_h2_race.cpp
)
target_include_directories(vf_tests PRIVATE ${CMAKE_SOURCE_DIR}/include)
target_link_libraries(vf_tests PRIVATE GTest::gtest_main)
include(GoogleTest)
gtest_discover_tests(vf_tests)
