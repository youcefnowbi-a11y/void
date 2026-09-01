// VOIDFORGE vf_mutator — AFL++ custom mutator (Linux/WSL only).
// Loaded via AFL_CUSTOM_MUTATOR_LIBRARY=./vf_mutator.so
// Strategies: RedQueen value replacement, chunk splice, grammar tokens,
// arithmetic mutation with interesting values. Builds with the AFL++
// custom-mutator C API (function names are mandatory).
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <vector>
#include <string>
#include <algorithm>

extern "C" {

// ---- xorshift64* RNG (self-contained, no rand()) ----
struct Rng {
    uint64_t s;
    explicit Rng(uint64_t seed) : s(seed ? seed : 0x9E3779B97F4A7C15ull) {}
    uint64_t next() {
        s ^= s >> 12; s ^= s << 25; s ^= s >> 27;
        return s * 0x2545F4914F6CDD1Dull;
    }
    uint32_t below(uint32_t n) { return n ? (uint32_t)(next() % n) : 0; }
};

struct VfMutator {
    Rng rng;
    // dictionary of tokens observed from inputs (grown on the fly)
    std::vector<std::string> tokens;

    explicit VfMutator(uint64_t seed) : rng(seed) {}

    static const uint32_t* interesting32(size_t* n) {
        static const uint32_t v[] = {
            0u, 1u, 0x7Fu, 0x80u, 0xFFu, 0x100u, 0x3FFu, 0x400u, 0x7FFu,
            0x800u, 0xFFFFu, 0x10000u, 0xFFFFFFF0u, 0x7FFFFFFFu, 0x80000000u,
            0xFFFFFFFFu
        };
        *n = sizeof(v) / sizeof(v[0]);
        return v;
    }
    static const uint64_t* interesting64(size_t* n) {
        static const uint64_t v[] = {
            0ull, 1ull, 0x7Full, 0x800ull, 0xFFFFull, 0x10000000ull,
            0x7FFFFFFFull, 0x8000000000000000ull, 0xFFFFFFFFFFFFFFFFull
        };
        *n = sizeof(v) / sizeof(v[0]);
        return v;
    }

    // ---- strategy 1: RedQueen-style value replacement ----
    // find integer-looking runs and replace with boundary neighbours
    size_t redqueen(uint8_t* out, size_t cap, const uint8_t* buf, size_t n) {
        size_t len = std::min(n, cap);
        std::memcpy(out, buf, len);
        if (len < 2) return len;
        size_t attempts = 4;
        for (size_t a = 0; a < attempts; ++a) {
            uint32_t width = (rng.next() % 3) ? 4 : 2;      // 4 or 2 bytes
            if (len < width + 1) return len;
            size_t pos = rng.below((uint32_t)(len - width));
            size_t in = rng.below(2);
            uint64_t cur = 0;
            if (in) {  // big-endian read
                for (uint32_t i = 0; i < width; ++i)
                    cur = (cur << 8) | out[pos + i];
            } else {   // little-endian read
                std::memcpy(&cur, out + pos, width);
            }
            uint64_t repl = cur;
            switch (rng.below(6)) {
                case 0: repl = 0; break;
                case 1: repl = (uint64_t)(width == 4 ? 0xFFFFFFFFll : -1ll); break;
                case 2: repl = cur + 1; break;
                case 3: repl = cur - 1; break;
                case 4: {
                    if (width == 4) { size_t k; const uint32_t* iv = interesting32(&k);
                        repl = iv[rng.below((uint32_t)k)]; }
                    else { size_t k; const uint64_t* iv = interesting64(&k);
                        repl = iv[rng.below((uint32_t)k)]; }
                    break;
                }
                default: repl = rng.next(); break;
            }
            if (in) { for (uint32_t i = 0; i < width; ++i) out[pos + i] = (uint8_t)(repl >> (8 * (width - 1 - i))); }
            else std::memcpy(out + pos, &repl, width);
        }
        return len;
    }

    // ---- strategy 2: chunk splice from add_buf ----
    size_t splice(uint8_t* out, size_t cap, const uint8_t* buf, size_t n,
                  const uint8_t* add, size_t add_len) {
        if (!add || add_len == 0 || n == 0) {
            size_t len = std::min(n, cap);
            std::memcpy(out, buf, len);
            return len;
        }
        size_t cut = rng.below((uint32_t)n);
        size_t take = rng.below((uint32_t)add_len);
        size_t len = std::min(cap, cut + take);
        std::memcpy(out, buf, std::min(cut, cap));
        std::memcpy(out + cut, add, std::min(take, len - std::min(cut, cap)));
        return len;
    }

    // ---- strategy 3: grammar token replacement ----
    size_t grammar(uint8_t* out, size_t cap, const uint8_t* buf, size_t n) {
        size_t len = std::min(n, cap);
        std::memcpy(out, buf, len);
        if (tokens.size() < 2 || len == 0) return len;
        const std::string& tok = tokens[rng.below((uint32_t)tokens.size())];
        // find a token-sized window and overwrite with a dictionary token
        if (tok.size() > len) return len;
        size_t pos = rng.below((uint32_t)(len - tok.size() + 1));
        std::memcpy(out + pos, tok.data(), tok.size());
        return len;
    }

    // learn tokens: split input on separator-ish bytes, keep 3-16 char chunks
    void learn(const uint8_t* buf, size_t n) {
        if (tokens.size() > 256) return;
        size_t i = 0;
        while (i < n) {
            while (i < n && (buf[i] < 0x20 || buf[i] > 0x7E)) ++i;
            size_t j = i;
            while (j < n && buf[j] >= 0x20 && buf[j] <= 0x7E) ++j;
            if (j - i >= 3 && j - i <= 16 && tokens.size() <= 256)
                tokens.emplace_back((const char*)buf + i, j - i);
            i = j + 1;
        }
    }
};

// ---- AFL++ mandatory API ----

void* afl_custom_init(void* afl, unsigned int seed) {
    (void)afl;
    return new VfMutator(seed);
}

size_t afl_custom_fuzz(void* data, uint8_t* buf, size_t buf_size,
                       uint8_t** out_buf, uint8_t* add_buf,
                       size_t add_buf_size, size_t max_size) {
    VfMutator* m = static_cast<VfMutator*>(data);
    static thread_local std::vector<uint8_t> out;
    out.resize(max_size ? max_size : buf_size + 64);
    size_t cap = out.size();

    m->learn(buf, buf_size);

    switch (m->rng.below(4)) {
        case 0:  out.resize(m->redqueen(out.data(), cap, buf, buf_size)); break;
        case 1:  out.resize(m->splice(out.data(), cap, buf, buf_size, add_buf, add_buf_size)); break;
        case 2:  out.resize(m->grammar(out.data(), cap, buf, buf_size)); break;
        default: out.resize(m->redqueen(out.data(), cap, buf, buf_size)); break;
    }
    *out_buf = out.data();
    return out.size();
}

size_t afl_custom_havoc_mutation(void* data, uint8_t* buf, size_t buf_size,
                                  uint8_t** out_buf, size_t max_size) {
    VfMutator* m = static_cast<VfMutator*>(data);
    static thread_local std::vector<uint8_t> out;
    out.resize(max_size ? max_size : buf_size + 64);
    size_t len = m->redqueen(out.data(), out.size(), buf, buf_size);
    out.resize(len);
    *out_buf = out.data();
    return len;
}

uint8_t afl_custom_havoc_mutation_probability(void* data) {
    (void)data;
    return 8;  // 8% havoc share — RedQueen carries the load
}

void afl_custom_deinit(void* data) {
    delete static_cast<VfMutator*>(data);
}

} // extern "C"
