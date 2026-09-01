// VOIDFORGE emu_core — Unicorn emulation engine implementation.
// All hooks are static C functions — zero Python callback overhead.
// Without VF_HAVE_UNICORN, functions degrade to structured errors
// (contract #2: nothing throws into Python).
#include "emu_core.h"

#include <unordered_map>
#include <memory>
#include <mutex>
#include <thread>
#include <atomic>
#include <cstring>

#ifdef VF_HAVE_UNICORN
#include <unicorn/unicorn.h>
#endif

namespace vf::emu {

namespace {

// ---- per-run context handed to static hooks (stable addresses) ----
// fault_kind pointe sur EngineState::fault_kind (char[32]) — l'EngineState
// vit dans un shared_ptr, l'adresse est stable tant que l'engine existe.
struct RunCtx {
    Bitmap*   cov;
    uint64_t* insns;
    uint64_t* fault_addr;
    char*     fault_kind;     // "READ"/"WRITE"/"FETCH"/"ACCESS"
    bool*     faulted;
    bool*     code_dirty;     // guest self-modification flag
    uint64_t  code_base;
    uint64_t  code_end;
};

#ifdef VF_HAVE_UNICORN

void hook_code(uc_engine* uc, uint64_t addr, uint32_t size, void* user_data) {
    (void)uc; (void)addr; (void)size;
    ++(*static_cast<RunCtx*>(user_data)->insns);
}

void hook_block(uc_engine* uc, uint64_t addr, uint32_t size, void* user_data) {
    (void)uc; (void)size;
    RunCtx* ctx = static_cast<RunCtx*>(user_data);
    (*ctx->cov)[addr % BITMAP_SIZE] = 1;
}

bool hook_mem_invalid(uc_engine* uc, uc_mem_type type, uint64_t addr,
                      int size, int64_t value, void* user_data) {
    (void)uc; (void)size; (void)value;
    RunCtx* ctx = static_cast<RunCtx*>(user_data);
    if (!*ctx->faulted) {
        *ctx->faulted = true;
        *ctx->fault_addr = addr;
        switch (type) {
            case UC_MEM_READ_UNMAPPED:   std::strncpy(ctx->fault_kind, "READ", 31);  break;
            case UC_MEM_WRITE_UNMAPPED:  std::strncpy(ctx->fault_kind, "WRITE", 31); break;
            case UC_MEM_FETCH_UNMAPPED:  std::strncpy(ctx->fault_kind, "FETCH", 31); break;
            default:                     std::strncpy(ctx->fault_kind, "ACCESS", 31); break;
        }
        ctx->fault_kind[31] = '\0';
    }
    return false;  // stop emulation — uc_emu_start returns UC_ERR_*_UNMAPPED
}

// self-modification detector: tout write guest dans la page code → dirty.
// (uc_mem_write hôte ne passe PAS par ce hook — il ne flushe que lui-même.)
bool hook_mem_code_write(uc_engine* uc, uc_mem_type type, uint64_t addr,
                         int size, int64_t value, void* user_data) {
    (void)uc; (void)type; (void)size; (void)value;
    RunCtx* ctx = static_cast<RunCtx*>(user_data);
    if (addr >= ctx->code_base && addr < ctx->code_end)
        *ctx->code_dirty = true;
    return true;   // let the write proceed
}

std::string map_uc_err(uc_err err) {
    switch (err) {
        case UC_ERR_READ_UNMAPPED:  return "UNMAPPED_READ";
        case UC_ERR_WRITE_UNMAPPED: return "UNMAPPED_WRITE";
        case UC_ERR_FETCH_UNMAPPED: return "UNMAPPED_FETCH";
        case UC_ERR_INSN_INVALID:   return "INVALID_INSN";
        case UC_ERR_EXCEPTION:      return "CPU_EXCEPTION";
        // unicorn2 a retiré UC_ERR_TIMEOUT — l'expiration de uc_emu_start
        // retourne UC_ERR_OK; le champ timeout d'EmuResult reste exact.
        default:                    return "EMU_ERROR";
    }
}

#endif // VF_HAVE_UNICORN

// ---- engine state + registry ----
struct EngineState {
#ifdef VF_HAVE_UNICORN
    uc_engine* uc = nullptr;
    uc_hook h_code = 0, h_block = 0, h_mem = 0;
#endif
    EmuConfig cfg{};
    std::vector<uint8_t> code;
    Bitmap cov{};
    uint64_t insns = 0;
    uint64_t fault_addr = 0;
    bool faulted = false;
    char fault_kind[32] = {0};
    std::unique_ptr<RunCtx> ctx;    // stable addresses for hooks
    std::mutex run_mu;              // serialize runs on this engine
    bool valid = false;
    uint64_t stop_addr = 0;         // capped emu stop (entry + code len)
    uc_hook h_code_write = 0;       // self-modification watch hook
    bool code_dirty = true;         // guest self-modification → re-write next run

    // ---- watchdog persistant (un thread par engine, réarmé par run) ----
    std::thread wd_thread;
    std::mutex wd_mu;
    std::condition_variable wd_cv;
    bool wd_armed = false;          // un run est en cours
    bool wd_shutdown = false;
    bool wd_fired = false;          // deadline expirée pendant ce run
    std::chrono::steady_clock::time_point wd_deadline;
};

std::mutex g_registry_mu;
std::unordered_map<int, std::shared_ptr<EngineState>> g_engines;
int g_next_id = 1;

inline uint64_t round_page(uint64_t n) {
    uint64_t r = (n + 0xFFF) & ~0xFFFull;
    return r < 0x1000 ? 0x1000 : r;
}

} // anonymous namespace

int engine_create(const EmuConfig& config, const std::string& code_bytes) {
#ifdef VF_HAVE_UNICORN
    std::lock_guard<std::mutex> lk(g_registry_mu);
    int id = g_next_id++;
    auto st = std::make_shared<EngineState>();
    st->cfg = config;
    st->code.assign(code_bytes.begin(), code_bytes.end());

    uc_err err = uc_open((uc_arch)config.arch, (uc_mode)config.mode, &st->uc);
    if (err != UC_ERR_OK) return -1;

    uint64_t stack_sz = round_page(config.stack_size);
    uint64_t code_sz  = round_page((uint64_t)st->code.size());
    if (uc_mem_map(st->uc, config.stack_base, (size_t)stack_sz, UC_PROT_ALL) != UC_ERR_OK ||
        uc_mem_map(st->uc, config.code_base, (size_t)code_sz, UC_PROT_ALL) != UC_ERR_OK) {
        uc_close(st->uc);
        return -1;
    }

    // hooks bound to stable EngineState storage — survives map rehash (shared_ptr)
    // stop_addr capé à entry+code_len : le padding de page n'est jamais du
    // code cible (le plan peut donner exit_addr = fin+1 → capé proprement)
    const uint64_t code_end = st->cfg.entry + (uint64_t)st->code.size();
    const uint64_t stop_addr =
        (st->cfg.exit_addr == 0 || st->cfg.exit_addr > code_end) ? code_end
                                                                 : st->cfg.exit_addr;
    st->stop_addr = stop_addr;
    st->ctx = std::make_unique<RunCtx>(RunCtx{
        &st->cov, &st->insns, &st->fault_addr, st->fault_kind, &st->faulted,
        &st->code_dirty, st->cfg.code_base, code_end });
    uc_hook_add(st->uc, &st->h_code, UC_HOOK_CODE, (void*)hook_code, st->ctx.get(), 1, 0);
    uc_hook_add(st->uc, &st->h_block, UC_HOOK_BLOCK, (void*)hook_block, st->ctx.get(), 1, 0);
    uc_hook_add(st->uc, &st->h_mem,
                (uc_hook_type)UC_HOOK_MEM_INVALID, (void*)hook_mem_invalid,
                st->ctx.get(), 1, 0);
    uc_hook_add(st->uc, &st->h_code_write,
                (uc_hook_type)UC_HOOK_MEM_WRITE, (void*)hook_mem_code_write,
                st->ctx.get(), st->cfg.code_base, code_end);

    // watchdog persistant — un seul thread pour TOUS les runs de cet engine
    if (st->cfg.timeout_us > 0) {
        st->wd_thread = std::thread([st]() {
            std::unique_lock<std::mutex> lk(st->wd_mu);
            for (;;) {
                st->wd_cv.wait(lk, [&] {
                    return st->wd_shutdown || st->wd_armed;
                });
                if (st->wd_shutdown) return;
                // dorme jusqu'à la deadline OU la fin du run (réveil par cv)
                if (!st->wd_cv.wait_until(lk, st->wd_deadline,
                                          [&] { return st->wd_shutdown || !st->wd_armed; })) {
                    // deadline expirée, run toujours actif → stop sec
                    st->wd_fired = true;
                    uc_emu_stop(st->uc);
                }
                st->wd_armed = false;
            }
        });
    }

    st->valid = true;
    g_engines[id] = std::move(st);
    return id;
#else
    (void)config; (void)code_bytes;
    return -1;  // module built without Unicorn
#endif
}

EmuResult engine_run(int engine_id, const std::string& input, uint64_t input_addr) {
    EmuResult r{};
    r.fault_addr = 0;
    r.insns_executed = 0;
    r.elapsed_us = 0;
    r.timeout = false;
#ifndef VF_HAVE_UNICORN
    (void)engine_id; (void)input; (void)input_addr;
    r.fault_type = "NATIVE_UNAVAILABLE";
    return r;
#else
    uint64_t t0 = now_us();
    std::shared_ptr<EngineState> st;
    {
        std::lock_guard<std::mutex> lk(g_registry_mu);
        auto it = g_engines.find(engine_id);
        if (it == g_engines.end() || !it->second->valid) {
            r.fault_type = "BAD_ENGINE_ID";
            r.elapsed_us = now_us() - t0;
            return r;
        }
        st = it->second;   // keeps the engine alive even if destroyed concurrently
    }
    std::lock_guard<std::mutex> run_lk(st->run_mu);

    bitmap_clear(st->cov);
    st->insns = 0;
    st->fault_addr = 0;
    st->faulted = false;
    st->fault_kind[0] = '\0';

    // fresh input each run; le CODE n'est réécrit que s'il a été modifié par
    // le guest (hook mem_write sur la page code) — réécrire systématiquement
    // invaliderait le TB cache QEMU à chaque run (~15ms/run → 66 exec/s).
    // Déterminisme préservé: le code en mémoire = st->code tant que !dirty.
    if (st->code_dirty) {
        uc_mem_write(st->uc, st->cfg.code_base, st->code.data(), st->code.size());
        st->code_dirty = false;
    }
    if (!input.empty())
        uc_mem_write(st->uc, input_addr, input.data(), input.size());

    // reset stack pointers into a fresh zone; zero hot stack for determinism
    uint64_t rsp = st->cfg.stack_base + st->cfg.stack_size - 0x1000;
    if (st->cfg.mode == 8 /* UC_MODE_64 */) {
        uc_reg_write(st->uc, UC_X86_REG_RSP, &rsp);
        uc_reg_write(st->uc, UC_X86_REG_RBP, &rsp);
    } else {
        uint32_t esp = (uint32_t)rsp;
        uc_reg_write(st->uc, UC_X86_REG_ESP, &esp);
        uc_reg_write(st->uc, UC_X86_REG_EBP, &esp);
    }
    static uint8_t zero_stack[0x10000] = {0};
    uc_mem_write(st->uc, rsp - sizeof(zero_stack), zero_stack, sizeof(zero_stack));

    // Watchdog réarmé par run : uc_emu_start(timeout) coûte ~15ms/run sous
    // Windows (timer interne par appel). Le thread persistant de l'engine
    // attend la deadline OU la fin du run (cv) → coût par run ≈ quelques µs.
    bool was_timeout = false;
    if (st->wd_thread.joinable()) {
        {
            std::lock_guard<std::mutex> lk(st->wd_mu);
            st->wd_deadline = std::chrono::steady_clock::now() +
                              std::chrono::microseconds(st->cfg.timeout_us);
            st->wd_fired = false;
            st->wd_armed = true;
        }
        st->wd_cv.notify_all();
    }
    uc_err err = uc_emu_start(st->uc, st->cfg.entry, st->stop_addr,
                              0, st->cfg.max_insns);
    if (st->wd_thread.joinable()) {
        {
            std::lock_guard<std::mutex> lk(st->wd_mu);
            st->wd_armed = false;
            was_timeout = st->wd_fired;
            st->wd_fired = false;
        }
        st->wd_cv.notify_all();
    }

    r.coverage = st->cov;
    r.insns_executed = (uint32_t)st->insns;
    r.fault_addr = st->fault_addr;
    if (st->faulted) {
        r.fault_type = std::string("UNMAPPED_") + (st->fault_kind[0] ? st->fault_kind : "ACCESS");
    } else if (err == UC_ERR_OK) {
        r.fault_type = "";
    } else {
        r.fault_type = map_uc_err(err);
        r.timeout = was_timeout;   // watchdog maison (unicorn2 n'a plus d'errno timeout)
    }
    r.elapsed_us = now_us() - t0;
    return r;
#endif
}

void engine_destroy(int engine_id) {
#ifdef VF_HAVE_UNICORN
    std::shared_ptr<EngineState> st;
    {
        std::lock_guard<std::mutex> lk(g_registry_mu);
        auto it = g_engines.find(engine_id);
        if (it == g_engines.end()) return;
        st = it->second;
        g_engines.erase(it);      // drop from registry
    }
    std::lock_guard<std::mutex> run_lk(st->run_mu);  // wait for in-flight run
    st->valid = false;
    if (st->wd_thread.joinable()) {          // stop the watchdog thread FIRST
        {
            std::lock_guard<std::mutex> lk(st->wd_mu);
            st->wd_shutdown = true;
            st->wd_armed = false;
        }
        st->wd_cv.notify_all();
        st->wd_thread.join();
    }
    if (st->uc) { uc_close(st->uc); st->uc = nullptr; }
#else
    (void)engine_id;
#endif
}

std::vector<EmuResult> engine_batch(int engine_id,
                                     const std::vector<std::string>& inputs,
                                     uint64_t input_addr) {
    std::vector<EmuResult> out;
    out.reserve(inputs.size());
    for (const auto& in : inputs)
        out.push_back(engine_run(engine_id, in, input_addr));
    return out;
}

} // namespace vf::emu
