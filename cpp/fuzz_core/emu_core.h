#pragma once
// VOIDFORGE emu_core — Unicorn-based emulation engine with block coverage.
// HOT PATH: engine_batch() runs N inputs in a tight C++ loop, zero Python.
#include "common.h"
#include "coverage.h"

namespace vf::emu {

struct EmuConfig {
    int arch;               // UC_ARCH_X86(3), UC_ARCH_ARM(1), UC_ARCH_ARM64(2)
    int mode;               // UC_MODE_32(4), UC_MODE_64(8)
    uint64_t code_base;     // where to map the code
    uint64_t stack_base;    // stack mapping base
    uint32_t stack_size;    // stack size (default 2MB)
    uint64_t entry;         // execution start address
    uint64_t exit_addr;     // execution end address (or 0 for max_insns)
    uint32_t max_insns;     // instruction limit (default 100000)
    uint32_t timeout_us;    // timeout in microseconds (default 5s)
};

struct EmuResult {
    Bitmap coverage;        // block coverage bitmap
    uint64_t fault_addr;    // 0 if no fault
    std::string fault_type; // "" if no fault, else "SEGV"/"UNMAPPED_READ"/...
    uint32_t insns_executed;
    uint64_t elapsed_us;
    bool timeout;
};

// Initialize emulator (call once, reuse for many inputs)
// code_bytes = the raw binary code to emulate
// Returns an opaque handle (engine ID), or -1 on failure
int engine_create(const EmuConfig& config, const std::string& code_bytes);

// Run one input through the emulator
EmuResult engine_run(int engine_id, const std::string& input, uint64_t input_addr);

// Destroy engine and free resources
void engine_destroy(int engine_id);

// Batch run: N inputs, returns N results — THE HOT PATH
std::vector<EmuResult> engine_batch(int engine_id,
                                     const std::vector<std::string>& inputs,
                                     uint64_t input_addr);

} // namespace vf::emu
