// VOIDFORGE triage — crash dedup + exploitability heuristics.
// Parses ASan / libFuzzer crash text, hashes top frames (SHA256 via OpenSSL),
// ranks 0-6 per plan §5.4 heuristics. Deduplicates by stack hash.
#include "triage.h"

#ifdef VF_HAVE_OPENSSL
#include <openssl/sha.h>
#endif
#include <filesystem>
#include <fstream>
#include <sstream>
#include <algorithm>
#include <unordered_map>
#include <cctype>
#include <cstring>
#include <regex>

namespace vf::triage {

namespace fs = std::filesystem;

namespace {

// ---- SHA256: OpenSSL when present, self-contained otherwise ----
#ifdef VF_HAVE_OPENSSL
std::string sha256_hex(const std::string& data) {
    unsigned char md[SHA256_DIGEST_LENGTH];
    SHA256(reinterpret_cast<const unsigned char*>(data.data()), data.size(), md);
    static const char* hexd = "0123456789abcdef";
    std::string out;
    out.reserve(SHA256_DIGEST_LENGTH * 2);
    for (int i = 0; i < SHA256_DIGEST_LENGTH; ++i) {
        out.push_back(hexd[md[i] >> 4]);
        out.push_back(hexd[md[i] & 0xF]);
    }
    return out;
}
#else
// Compact FIPS 180-4 SHA256 (no external deps) — single-shot, known-answer tested
std::string sha256_hex(const std::string& data) {
    static const uint32_t K[64] = {
        0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,
        0x923f82a4,0xab1c5ed5,0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,
        0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,0xe49b69c1,0xefbe4786,
        0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,
        0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,
        0x06ca6351,0x14292967,0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,
        0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,0xa2bfe8a1,0xa81a664b,
        0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
        0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,
        0x5b9cca4f,0x682e6ff3,0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,
        0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2};
    static const uint32_t H0[8] = {0x6a09e667,0xbb67ae85,0x3c6ef372,0xa54ff53a,
                                   0x510e527f,0x9b05688c,0x1f83d9ab,0x5be0cd19};

    std::vector<uint8_t> msg(data.begin(), data.end());
    uint64_t bitlen = (uint64_t)data.size() * 8;
    msg.push_back(0x80);
    while (msg.size() % 64 != 56) msg.push_back(0);
    for (int i = 7; i >= 0; --i)
        msg.push_back((uint8_t)(bitlen >> (8 * i)));

    uint32_t h[8];
    std::memcpy(h, H0, sizeof(h));
    auto rotr = [](uint32_t x, int n) { return (x >> n) | (x << (32 - n)); };

    for (size_t off = 0; off < msg.size(); off += 64) {
        uint32_t w[64];
        for (int i = 0; i < 16; ++i)
            w[i] = ((uint32_t)msg[off + i*4] << 24) | ((uint32_t)msg[off + i*4+1] << 16) |
                   ((uint32_t)msg[off + i*4+2] << 8) | (uint32_t)msg[off + i*4+3];
        for (int i = 16; i < 64; ++i) {
            uint32_t s0 = rotr(w[i-15],7) ^ rotr(w[i-15],18) ^ (w[i-15] >> 3);
            uint32_t s1 = rotr(w[i-2],17) ^ rotr(w[i-2],19) ^ (w[i-2] >> 10);
            w[i] = w[i-16] + s0 + w[i-7] + s1;
        }
        uint32_t a=h[0],b=h[1],c=h[2],d=h[3],e=h[4],f=h[5],g=h[6],hh=h[7];
        for (int i = 0; i < 64; ++i) {
            uint32_t S1 = rotr(e,6) ^ rotr(e,11) ^ rotr(e,25);
            uint32_t ch = (e & f) ^ (~e & g);
            uint32_t t1 = hh + S1 + ch + K[i] + w[i];
            uint32_t S0 = rotr(a,2) ^ rotr(a,13) ^ rotr(a,22);
            uint32_t maj = (a & b) ^ (a & c) ^ (b & c);
            uint32_t t2 = S0 + maj;
            hh=g; g=f; f=e; e=d+t1; d=c; c=b; b=a; a=t1+t2;
        }
        h[0]+=a; h[1]+=b; h[2]+=c; h[3]+=d; h[4]+=e; h[5]+=f; h[6]+=g; h[7]+=hh;
    }

    static const char* hd = "0123456789abcdef";
    std::string out;
    out.reserve(64);
    for (int i = 0; i < 8; ++i)
        for (int b = 7; b >= 0; --b)
            out.push_back(hd[(h[i] >> (4 * b)) & 0xF]);
    return out;
}
#endif

std::string lower(std::string s) {
    std::transform(s.begin(), s.end(), s.begin(),
                   [](unsigned char c) { return (char)std::tolower(c); });
    return s;
}

struct ParsedCrash {
    std::string fault_type = "UNKNOWN";
    uint64_t fault_addr = 0;
    std::vector<std::string> frames;
    std::string op;             // "READ"/"WRITE" if found (ASan op line)
};

ParsedCrash parse_crash_text(const std::string& text) {
    ParsedCrash p;
    std::string low = lower(text);

    // ---- fault type ----
    if (low.find("heap-buffer-overflow") != std::string::npos)      p.fault_type = "HEAP_BUFFER_OVERFLOW";
    else if (low.find("use-after-free") != std::string::npos)       p.fault_type = "USE_AFTER_FREE";
    else if (low.find("double-free") != std::string::npos)          p.fault_type = "DOUBLE_FREE";
    else if (low.find("stack-overflow") != std::string::npos)       p.fault_type = "STACK_OVERFLOW";
    else if (low.find("heap-use-after-free") != std::string::npos)  p.fault_type = "USE_AFTER_FREE";
    else if (low.find("global-buffer-overflow") != std::string::npos) p.fault_type = "GLOBAL_OVERFLOW";
    else if (low.find("sigabrt") != std::string::npos ||
             low.find("assert") != std::string::npos)               p.fault_type = "SIGABRT";
    else if (low.find("segv") != std::string::npos ||
             low.find("deadly signal") != std::string::npos)        p.fault_type = "SEGV";

    // ---- ASan operation (READ/WRITE) + fault addr + stack frames ----
    std::regex op_re(R"((READ|WRITE) of size (\d+))");
    std::smatch m;
    if (std::regex_search(text, m, op_re)) p.op = m[1];

    std::regex addr_re(R"(0x([0-9a-fA-F]{4,16}))");
    if (std::regex_search(text, m, addr_re)) {
        try { p.fault_addr = std::stoull(m[1].str(), nullptr, 16); } catch (...) {}
    }

    std::regex frame_re(R"(#(\d+)\s+0x[0-9a-fA-F]+\s+in\s+([A-Za-z_][\w:.<>~ ]*))");
    std::istringstream iss(text);
    std::string line;
    while (std::getline(iss, line)) {
        std::smatch fm;
        if (std::regex_search(line, fm, frame_re))
            p.frames.push_back(fm[2].str());
    }
    return p;
}

// Detect attacker-controlled fault addresses: repeated-byte patterns
// (0x41414141, 0x6161616161616161, 0xdeadbeef-ish constants)
bool addr_looks_controlled(uint64_t a) {
    if (a == 0) return false;
    uint8_t b[8];
    std::memcpy(b, &a, 8);
    bool all_same = true;
    for (int i = 1; i < 8; ++i) if (b[i] != b[0]) { all_same = false; break; }
    if (all_same) return true;
    // classic magic values
    uint32_t lo = (uint32_t)(a & 0xFFFFFFFF);
    if (lo == 0x41414141 || lo == 0x42424242 || lo == 0x43434343 ||
        lo == 0xdeadbeef || lo == 0xdeadfa11 || lo == 0xcafebabe) return true;
    return false;
}

int rank_exploitability(const ParsedCrash& p) {
    if (addr_looks_controlled(p.fault_addr) && p.fault_type == "SEGV")
        return EXP_RIP_CONTROL;                                  // 6
    if (p.op == "WRITE" && p.fault_type == "SEGV")
        return EXP_WRITE_WHAT_WHERE;                             // 5
    if (p.op == "READ" && p.fault_type == "SEGV")
        return EXP_CONTROLLED_DEREF;                             // 4
    if (p.fault_type == "HEAP_BUFFER_OVERFLOW" ||
        p.fault_type == "USE_AFTER_FREE" ||
        p.fault_type == "DOUBLE_FREE" ||
        p.fault_type == "GLOBAL_OVERFLOW")
        return EXP_HEAP_CORRUPTION;                              // 3
    if (p.fault_type == "STACK_OVERFLOW")
        return EXP_STACK_OVERFLOW;                               // 2
    if (p.fault_type == "SEGV")
        return EXP_DATA_ONLY;                                    // 1
    return EXP_DOS;                                              // 0 (SIGABRT/assert/unknown)
}

} // anonymous namespace

std::vector<TriagedCrash> triage_crashes(const TriageConfig& config) {
    std::vector<TriagedCrash> out;
    std::unordered_map<std::string, size_t> index_by_hash;

    try {
        if (!fs::exists(config.crash_dir) || !fs::is_directory(config.crash_dir))
            return out;

        for (const auto& entry : fs::directory_iterator(config.crash_dir)) {
            if (!entry.is_regular_file()) continue;
            std::ifstream f(entry.path(), std::ios::binary);
            if (!f) continue;
            std::ostringstream ss;
            ss << f.rdbuf();
            std::string text = ss.str().substr(0, 1 << 16);  // 64KB parse cap

            ParsedCrash p = parse_crash_text(text);

            TriagedCrash tc;
            tc.fault_type = p.fault_type;
            tc.fault_addr = p.fault_addr;
            tc.exploitability = rank_exploitability(p);

            size_t n = std::min((size_t)std::max(1, config.top_frames), p.frames.size());
            std::string key_material;
            for (size_t i = 0; i < n; ++i) key_material += p.frames[i] + "|";
            tc.stack_frames = std::vector<std::string>(
                p.frames.begin(), p.frames.begin() + n);
            if (key_material.empty())
                key_material = text.substr(0, 4096);   // content-hash fallback → dedup still works
            tc.hash = sha256_hex(key_material);

            auto it = index_by_hash.find(tc.hash);
            if (it != index_by_hash.end()) {
                out[it->second].duplicate_count++;
            } else {
                tc.duplicate_count = 1;
                tc.representative = entry.path().string();
                index_by_hash[tc.hash] = out.size();
                out.push_back(std::move(tc));
            }
        }
    } catch (...) {
        // swallow filesystem errors — return what we have (contract #2)
    }

    std::sort(out.begin(), out.end(),
              [](const TriagedCrash& a, const TriagedCrash& b) {
                  if (a.exploitability != b.exploitability)
                      return a.exploitability > b.exploitability;
                  return a.hash < b.hash;
              });
    return out;
}

} // namespace vf::triage
