#pragma once
// VOIDFORGE net_pacer — microsecond-precision stateful protocol replay.
// Cross-platform: Winsock2 (_WIN32) / POSIX sockets (__linux__).
#include "common.h"
#include <string>
#include <vector>

namespace vf::net {

struct Message {
    std::string data;                 // raw bytes to send
    uint64_t delay_us = 0;            // delay BEFORE sending this message
    bool expect_response = true;      // wait for response?
    uint32_t response_timeout_us = 3000000; // recv deadline (default 3s)
};

struct Response {
    std::string data;                 // raw bytes received
    uint64_t send_time_us = 0;
    uint64_t recv_time_us = 0;
    int status = 0;                   // 0 ok, -1 timeout, -2 connection error
};

struct ReplayConfig {
    std::string host;
    uint16_t port = 80;
    bool use_tls = false;
    std::vector<Message> sequence;
    int mutate_index = -1;            // which message to mutate (-1 = none)
    std::string mutation;             // replacement bytes for mutated message
};

struct ReplayResult {
    std::vector<Response> responses;
    uint64_t total_elapsed_us = 0;
    bool connection_ok = false;
    std::string error;
};

// Replay a message sequence with µs timing
ReplayResult replay(const ReplayConfig& config);

// Batch replay: run N mutations of the same sequence.
// Each trial opens a fresh connection — independent state per mutation
// (the safer semantic for stateful protocol fuzzing; the one-connection
// prefix-amortization optimization from the plan is deferred).
std::vector<ReplayResult> replay_batch(
    const ReplayConfig& base_config,
    const std::vector<std::string>& mutations);

} // namespace vf::net
