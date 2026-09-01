#pragma once
// VOIDFORGE h2_race — HTTP/2 single-packet race (James Kettle technique).
// Packs N requests into one TLS flight so they land in the same kernel
// receive buffer — a ~50-500µs arrival window. Tests single-use guards.
#include "common.h"
#include <string>
#include <vector>
#include <utility>

namespace vf::h2race {

struct RaceRequest {
    std::string method;         // "GET", "POST"
    std::string path;           // "/token?code=..."
    std::vector<std::pair<std::string, std::string>> headers;
    std::string body;           // POST body (can be empty)
};

struct RaceResponse {
    uint32_t stream_id = 0;
    int status_code = 0;
    std::vector<std::pair<std::string, std::string>> headers;
    std::string body;
};

struct RaceConfig {
    std::string host;
    uint16_t port = 443;
    bool use_tls = true;        // almost always true for HTTP/2
    std::vector<RaceRequest> requests;  // N requests to send simultaneously
    uint32_t warmup_streams = 1;        // warm streams before the race batch
    uint32_t response_timeout_us = 5000000;
};

struct RaceResult {
    std::vector<RaceResponse> responses;
    uint64_t send_wall_us = 0;      // time to send all frames
    uint64_t recv_wall_us = 0;      // time to receive all responses
    int successful_2xx = 0;
    int distinct_bodies = 0;
    std::string interpretation;
};

// Execute a single-packet HTTP/2 race
RaceResult execute(const RaceConfig& config);

} // namespace vf::h2race
