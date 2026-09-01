// VOIDFORGE voidforge_native — the single pybind11 module.
// Submodules: emu / triage / net / h2race / heap (+ libfuzz on Linux).
// Contracts: JSON-serializable results, no exceptions to Python,
// py::bytes coverage bitmaps, GIL released on all hot paths.
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
namespace py = pybind11;

#include "fuzz_core/emu_core.h"
#include "fuzz_core/triage.h"
#include "net_core/net_pacer.h"
#include "net_core/h2_race.h"
#include "heap_core/groom.h"
#ifdef __linux__
#include "fuzz_core/libfuzzer_drv.h"
#endif

#ifdef VF_HAVE_UNICORN
#include <unicorn/unicorn.h>
#endif

namespace {

// Unicorn constants for the Python side (real values when available)
inline int uc_arch_x86() {
#ifdef VF_HAVE_UNICORN
    return UC_ARCH_X86;
#else
    return 3;
#endif
}
inline int uc_arch_arm() {
#ifdef VF_HAVE_UNICORN
    return UC_ARCH_ARM;
#else
    return 1;
#endif
}
inline int uc_arch_arm64() {
#ifdef VF_HAVE_UNICORN
    return UC_ARCH_ARM64;
#else
    return 2;
#endif
}
inline int uc_mode_32() {
#ifdef VF_HAVE_UNICORN
    return UC_MODE_32;
#else
    return 4;
#endif
}
inline int uc_mode_64() {
#ifdef VF_HAVE_UNICORN
    return UC_MODE_64;
#else
    return 8;
#endif
}

} // anonymous namespace

PYBIND11_MODULE(voidforge_native, m) {
    m.doc() = "VOIDFORGE C++ hot cores — high-performance fuzzing, "
              "network pacing, and heap grooming";

    // --- emu_core ---
    auto emu = m.def_submodule("emu", "Unicorn emulation engine");

    emu.attr("ARCH_X86") = uc_arch_x86();
    emu.attr("ARCH_ARM") = uc_arch_arm();
    emu.attr("ARCH_ARM64") = uc_arch_arm64();
    emu.attr("MODE_32") = uc_mode_32();
    emu.attr("MODE_64") = uc_mode_64();

    py::class_<vf::emu::EmuConfig>(emu, "EmuConfig")
        .def(py::init<>())
        .def_readwrite("arch", &vf::emu::EmuConfig::arch)
        .def_readwrite("mode", &vf::emu::EmuConfig::mode)
        .def_readwrite("code_base", &vf::emu::EmuConfig::code_base)
        .def_readwrite("stack_base", &vf::emu::EmuConfig::stack_base)
        .def_readwrite("stack_size", &vf::emu::EmuConfig::stack_size)
        .def_readwrite("entry", &vf::emu::EmuConfig::entry)
        .def_readwrite("exit_addr", &vf::emu::EmuConfig::exit_addr)
        .def_readwrite("max_insns", &vf::emu::EmuConfig::max_insns)
        .def_readwrite("timeout_us", &vf::emu::EmuConfig::timeout_us);

    py::class_<vf::emu::EmuResult>(emu, "EmuResult")
        .def_readonly("fault_addr", &vf::emu::EmuResult::fault_addr)
        .def_readonly("fault_type", &vf::emu::EmuResult::fault_type)
        .def_readonly("insns_executed", &vf::emu::EmuResult::insns_executed)
        .def_readonly("elapsed_us", &vf::emu::EmuResult::elapsed_us)
        .def_readonly("timeout", &vf::emu::EmuResult::timeout)
        .def("coverage_bytes", [](const vf::emu::EmuResult& r) {
            return py::bytes(reinterpret_cast<const char*>(r.coverage.data()),
                             vf::BITMAP_SIZE);
        });

    emu.def("engine_create", &vf::emu::engine_create,
            py::arg("config"), py::arg("code_bytes"));
    emu.def("engine_run", &vf::emu::engine_run,
            py::arg("engine_id"), py::arg("input"), py::arg("input_addr"));
    emu.def("engine_destroy", &vf::emu::engine_destroy, py::arg("engine_id"));
    emu.def("engine_batch", &vf::emu::engine_batch,
            py::arg("engine_id"), py::arg("inputs"), py::arg("input_addr"),
            py::call_guard<py::gil_scoped_release>());  // RELEASE GIL — hot path

    // --- triage ---
    auto tri = m.def_submodule("triage", "Crash dedup and exploitability ranking");

    py::class_<vf::triage::TriagedCrash>(tri, "TriagedCrash")
        .def_readonly("hash", &vf::triage::TriagedCrash::hash)
        .def_readonly("exploitability", &vf::triage::TriagedCrash::exploitability)
        .def_readonly("fault_type", &vf::triage::TriagedCrash::fault_type)
        .def_readonly("fault_addr", &vf::triage::TriagedCrash::fault_addr)
        .def_readonly("stack_frames", &vf::triage::TriagedCrash::stack_frames)
        .def_readonly("duplicate_count", &vf::triage::TriagedCrash::duplicate_count)
        .def_readonly("representative", &vf::triage::TriagedCrash::representative);

    py::class_<vf::triage::TriageConfig>(tri, "TriageConfig")
        .def(py::init<>())
        .def_readwrite("crash_dir", &vf::triage::TriageConfig::crash_dir)
        .def_readwrite("binary_path", &vf::triage::TriageConfig::binary_path)
        .def_readwrite("top_frames", &vf::triage::TriageConfig::top_frames)
        .def_readwrite("symbolize", &vf::triage::TriageConfig::symbolize);

    tri.def("triage_crashes", &vf::triage::triage_crashes, py::arg("config"));
            // NOTE: pas de gil_scoped_release ici — le cast du résultat
            // (vector<TriagedCrash> → liste) doit voir le GIL. Le scan
            // filesystem/regex reste rapide; le GIL n'est un vrai gain
            // que sur emu.engine_batch/net.replay_batch.

    // --- net_pacer ---
    auto net = m.def_submodule("net", "Microsecond network replay");

    py::class_<vf::net::Message>(net, "Message")
        .def(py::init<>())
        .def_readwrite("data", &vf::net::Message::data)
        .def_readwrite("delay_us", &vf::net::Message::delay_us)
        .def_readwrite("expect_response", &vf::net::Message::expect_response)
        .def_readwrite("response_timeout_us", &vf::net::Message::response_timeout_us);

    py::class_<vf::net::Response>(net, "Response")
        .def_readonly("data", &vf::net::Response::data)
        .def_readonly("send_time_us", &vf::net::Response::send_time_us)
        .def_readonly("recv_time_us", &vf::net::Response::recv_time_us)
        .def_readonly("status", &vf::net::Response::status);

    py::class_<vf::net::ReplayConfig>(net, "ReplayConfig")
        .def(py::init<>())
        .def_readwrite("host", &vf::net::ReplayConfig::host)
        .def_readwrite("port", &vf::net::ReplayConfig::port)
        .def_readwrite("use_tls", &vf::net::ReplayConfig::use_tls)
        .def_readwrite("sequence", &vf::net::ReplayConfig::sequence)
        .def_readwrite("mutate_index", &vf::net::ReplayConfig::mutate_index)
        .def_readwrite("mutation", &vf::net::ReplayConfig::mutation);

    // ReplayResult — OUBLIÉ dans le plan §6 (bug du plan) : sans ce binding,
    // le cast du retour de replay/replay_batch échoue.
    py::class_<vf::net::ReplayResult>(net, "ReplayResult")
        .def_readonly("responses", &vf::net::ReplayResult::responses)
        .def_readonly("total_elapsed_us", &vf::net::ReplayResult::total_elapsed_us)
        .def_readonly("connection_ok", &vf::net::ReplayResult::connection_ok)
        .def_readonly("error", &vf::net::ReplayResult::error);

    net.def("replay", &vf::net::replay, py::arg("config"),
            py::call_guard<py::gil_scoped_release>());
    net.def("replay_batch", &vf::net::replay_batch,
            py::arg("base_config"), py::arg("mutations"),
            py::call_guard<py::gil_scoped_release>());

    // --- h2_race ---
    auto h2 = m.def_submodule("h2race", "HTTP/2 single-packet race");

    py::class_<vf::h2race::RaceRequest>(h2, "RaceRequest")
        .def(py::init<>())
        .def_readwrite("method", &vf::h2race::RaceRequest::method)
        .def_readwrite("path", &vf::h2race::RaceRequest::path)
        .def_readwrite("headers", &vf::h2race::RaceRequest::headers)
        .def_readwrite("body", &vf::h2race::RaceRequest::body);

    py::class_<vf::h2race::RaceResponse>(h2, "RaceResponse")
        .def_readonly("stream_id", &vf::h2race::RaceResponse::stream_id)
        .def_readonly("status_code", &vf::h2race::RaceResponse::status_code)
        .def_readonly("headers", &vf::h2race::RaceResponse::headers)
        .def_readonly("body", &vf::h2race::RaceResponse::body);

    py::class_<vf::h2race::RaceConfig>(h2, "RaceConfig")
        .def(py::init<>())
        .def_readwrite("host", &vf::h2race::RaceConfig::host)
        .def_readwrite("port", &vf::h2race::RaceConfig::port)
        .def_readwrite("use_tls", &vf::h2race::RaceConfig::use_tls)
        .def_readwrite("requests", &vf::h2race::RaceConfig::requests)
        .def_readwrite("warmup_streams", &vf::h2race::RaceConfig::warmup_streams)
        .def_readwrite("response_timeout_us", &vf::h2race::RaceConfig::response_timeout_us);

    py::class_<vf::h2race::RaceResult>(h2, "RaceResult")
        .def_readonly("responses", &vf::h2race::RaceResult::responses)
        .def_readonly("send_wall_us", &vf::h2race::RaceResult::send_wall_us)
        .def_readonly("recv_wall_us", &vf::h2race::RaceResult::recv_wall_us)
        .def_readonly("successful_2xx", &vf::h2race::RaceResult::successful_2xx)
        .def_readonly("distinct_bodies", &vf::h2race::RaceResult::distinct_bodies)
        .def_readonly("interpretation", &vf::h2race::RaceResult::interpretation);

    h2.def("execute", &vf::h2race::execute, py::arg("config"),
           py::call_guard<py::gil_scoped_release>());

    // --- heap groom (v2) ---
    auto heap = m.def_submodule("heap", "Heap grooming oracle");

    py::class_<vf::heap::GroomConfig>(heap, "GroomConfig")
        .def(py::init<>())
        .def_readwrite("target_size", &vf::heap::GroomConfig::target_size)
        .def_readwrite("spray_count", &vf::heap::GroomConfig::spray_count)
        .def_readwrite("pattern", &vf::heap::GroomConfig::pattern)
        .def_readwrite("measure_trials", &vf::heap::GroomConfig::measure_trials);

    py::class_<vf::heap::GroomResult>(heap, "GroomResult")
        .def_readonly("reuse_rate", &vf::heap::GroomResult::reuse_rate)
        .def_readonly("avg_reuse_us", &vf::heap::GroomResult::avg_reuse_us)
        .def_readonly("actual_size_class", &vf::heap::GroomResult::actual_size_class)
        .def_readonly("allocator", &vf::heap::GroomResult::allocator)
        .def_readonly("tcache_hit", &vf::heap::GroomResult::tcache_hit)
        .def_readonly("interpretation", &vf::heap::GroomResult::interpretation);

    heap.def("measure_reuse", &vf::heap::measure_reuse, py::arg("config"));
    heap.def("spray", &vf::heap::spray, py::arg("target_size"),
             py::arg("count"), py::arg("pattern"));
    heap.def("punch_holes", &vf::heap::punch_holes, py::arg("indices"));
    heap.def("check_reclamation", &vf::heap::check_reclamation,
             py::arg("expected_pattern"));

#ifdef __linux__
    // --- libfuzzer driver (Linux/Clang only) ---
    auto lf = m.def_submodule("libfuzz", "libFuzzer programmatic campaign runner");

    py::class_<vf::libfuzz::FuzzConfig>(lf, "FuzzConfig")
        .def(py::init<>())
        .def_readwrite("target_path", &vf::libfuzz::FuzzConfig::target_path)
        .def_readwrite("corpus_dir", &vf::libfuzz::FuzzConfig::corpus_dir)
        .def_readwrite("artifact_dir", &vf::libfuzz::FuzzConfig::artifact_dir)
        .def_readwrite("max_seconds", &vf::libfuzz::FuzzConfig::max_seconds)
        .def_readwrite("max_len", &vf::libfuzz::FuzzConfig::max_len)
        .def_readwrite("jobs", &vf::libfuzz::FuzzConfig::jobs)
        .def_readwrite("extra_flags", &vf::libfuzz::FuzzConfig::extra_flags);

    py::class_<vf::libfuzz::FuzzResult>(lf, "FuzzResult")
        .def_readonly("total_execs", &vf::libfuzz::FuzzResult::total_execs)
        .def_readonly("execs_per_sec", &vf::libfuzz::FuzzResult::execs_per_sec)
        .def_readonly("corpus_size", &vf::libfuzz::FuzzResult::corpus_size)
        .def_readonly("coverage_pct", &vf::libfuzz::FuzzResult::coverage_pct)
        .def_readonly("crash_paths", &vf::libfuzz::FuzzResult::crash_paths)
        .def_readonly("elapsed_us", &vf::libfuzz::FuzzResult::elapsed_us)
        .def_readonly("error", &vf::libfuzz::FuzzResult::error);

    lf.def("run_campaign", &vf::libfuzz::run_campaign, py::arg("config"),
           py::call_guard<py::gil_scoped_release>());
#endif
}
