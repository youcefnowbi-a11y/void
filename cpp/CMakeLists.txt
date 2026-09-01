cmake_minimum_required(VERSION 3.20)
project(voidforge_native LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

# --- Python + pybind11 (required) ---
find_package(Python3 REQUIRED COMPONENTS Interpreter Development.Module)
find_package(pybind11 CONFIG REQUIRED)

# --- OpenSSL — optional; gates VF_HAVE_OPENSSL (TLS + SHA256).
# Without it: triage uses the built-in SHA256, TLS paths degrade. ---
find_package(OpenSSL QUIET)
if(OpenSSL_FOUND)
    set(VF_HAVE_OPENSSL ON)
    message(STATUS "VOIDFORGE: OpenSSL found — TLS + h2race ENABLED (si nghttp2)")
else()
    set(VF_HAVE_OPENSSL OFF)
    message(STATUS "VOIDFORGE: OpenSSL NOT found — SHA256 fallback + pas de TLS")
endif()

# --- Unicorn — optional; gates VF_HAVE_UNICORN (emu real engine) ---
find_library(UNICORN_LIB NAMES unicorn QUIET)
find_path(UNICORN_INCLUDE unicorn/unicorn.h QUIET)
if(UNICORN_LIB AND UNICORN_INCLUDE)
    set(VF_HAVE_UNICORN ON)
    message(STATUS "VOIDFORGE: Unicorn found — emu engine ENABLED")
else()
    set(VF_HAVE_UNICORN OFF)
    message(STATUS "VOIDFORGE: Unicorn NOT found — emu degrades to error stubs")
endif()

# --- nghttp2 — optional; gates VF_HAVE_H2 (h2_race real engine).
# h2 race needs TLS too — gate requires nghttp2 AND OpenSSL. ---
find_library(NGHTTP2_LIB NAMES nghttp2 QUIET)
find_path(NGHTTP2_INCLUDE nghttp2/nghttp2.h QUIET)
set(VF_HAVE_H2 OFF)
if(NGHTTP2_LIB AND NGHTTP2_INCLUDE AND VF_HAVE_OPENSSL)
    set(VF_HAVE_H2 ON)
    message(STATUS "VOIDFORGE: nghttp2 + OpenSSL found — h2_race ENABLED")
else()
    message(STATUS "VOIDFORGE: h2_race OFF (nghttp2=${NGHTTP2_LIB} openssl=${VF_HAVE_OPENSSL})")
endif()

# --- Common include ---
include_directories(${CMAKE_SOURCE_DIR})
include_directories(${CMAKE_SOURCE_DIR}/include)

set(VF_NATIVE_SOURCES
    bindings/pybind_module.cpp
    fuzz_core/emu_core.cpp
    fuzz_core/triage.cpp
    net_core/net_pacer.cpp
    net_core/h2_race.cpp
    heap_core/groom.cpp
)

# === PYBIND11 MODULE: voidforge_native ===
pybind11_add_module(voidforge_native ${VF_NATIVE_SOURCES})

if(VF_HAVE_UNICORN)
    target_compile_definitions(voidforge_native PRIVATE VF_HAVE_UNICORN)
    target_include_directories(voidforge_native PRIVATE ${UNICORN_INCLUDE})
    target_link_libraries(voidforge_native PRIVATE ${UNICORN_LIB})
endif()
if(VF_HAVE_H2)
    target_compile_definitions(voidforge_native PRIVATE VF_HAVE_H2)
    target_include_directories(voidforge_native PRIVATE ${NGHTTP2_INCLUDE})
    target_link_libraries(voidforge_native PRIVATE ${NGHTTP2_LIB})
endif()
if(VF_HAVE_OPENSSL)
    target_compile_definitions(voidforge_native PRIVATE VF_HAVE_OPENSSL)
    target_link_libraries(voidforge_native PRIVATE OpenSSL::SSL OpenSSL::Crypto)
endif()

# === AFL++ CUSTOM MUTATOR (shared library, Linux/WSL only) ===
if(UNIX)
    add_library(vf_mutator SHARED fuzz_core/mutator.cpp)
    target_compile_definitions(vf_mutator PRIVATE AFL_CUSTOM_MUTATOR)
    set_target_properties(vf_mutator PROPERTIES
        OUTPUT_NAME "vf_mutator"
        PREFIX ""  # no "lib" prefix — AFL++ expects the plain name
    )
endif()

# === libFuzzer driver (requires Clang + sanitizer; Linux) ===
if(CMAKE_CXX_COMPILER_ID MATCHES "Clang" AND UNIX)
    add_library(vf_fuzz_driver STATIC fuzz_core/libfuzzer_drv.cpp)
    target_compile_options(vf_fuzz_driver PRIVATE -fsanitize=fuzzer-no-link)
endif()

# === Tests (optional, GTest) ===
option(BUILD_TESTS "Build C++ unit tests" OFF)
if(BUILD_TESTS)
    enable_testing()
    find_package(GTest REQUIRED)
    add_subdirectory(tests)
endif()

# === Install the pybind module next to the Python tools (VOIDFORGE root) ===
install(TARGETS voidforge_native
    RUNTIME DESTINATION ${CMAKE_SOURCE_DIR}/..   # Windows .pyd
    LIBRARY DESTINATION ${CMAKE_SOURCE_DIR}/..   # Linux .so
)
