// VOIDFORGE h2_race — HTTP/2 single-packet race implementation.
//
// Wire plan (per plan §5.6):
//   1. TCP → TLS (ALPN "h2") → connection preface + SETTINGS
//   2. server SETTINGS → SETTINGS ACK
//   3. optional warmup stream(s) — fire and forget, frames ignored later
//   4. ALL race HEADERS(+DATA) frames built into ONE contiguous buffer,
//      stream IDs 3,5,7... odd — HPACK via one connection-level deflater
//      (server decodes them in wire order with a single decoder state)
//   5. ONE send / SSL_write call — single flight, minimal segments
//   6. read responses, match by stream id, count 2xx, dedupe bodies
//
// Built only when VF_HAVE_H2 is defined (OpenSSL + nghttp2 found);
// otherwise execute() returns a structured error (contract #2).
#include "h2_race.h"

#include <set>
#include <map>
#include <cstring>
#include <algorithm>

#ifdef _WIN32
#  ifndef NOMINMAX
#    define NOMINMAX
#  endif
#  ifndef WIN32_LEAN_AND_MEAN
#    define WIN32_LEAN_AND_MEAN
#  endif
#  include <winsock2.h>
#  include <ws2tcpip.h>
#  pragma comment(lib, "ws2_32.lib")
using socket_t = SOCKET;
static const socket_t kInvalidSocket = INVALID_SOCKET;
#else
#  include <sys/socket.h>
#  include <sys/select.h>
#  include <netinet/in.h>
#  include <netinet/tcp.h>
#  include <arpa/inet.h>
#  include <netdb.h>
#  include <unistd.h>
#  include <fcntl.h>
using socket_t = int;
static const socket_t kInvalidSocket = -1;
#endif

#ifdef VF_HAVE_H2
#  include <openssl/ssl.h>
#  include <openssl/err.h>
   // vcpkg nghttp2 ≥1.63: les typedefs ssize_t callback sont POSIX-only.
   // On les désactive — on n'utilise que nghttp2_hd_* (HPACK), aucun callback.
#  define NGHTTP2_NO_SSIZE_T 1
#  include <nghttp2/nghttp2.h>
#endif

namespace vf::h2race {

namespace {

struct WsaGuard2 {
    bool ok = true;
#ifdef _WIN32
    WsaGuard2() { WSADATA d; ok = (WSAStartup(MAKEWORD(2, 2), &d) == 0); }
    ~WsaGuard2() { if (ok) WSACleanup(); }
#endif
};
WsaGuard2& wsa2() { static WsaGuard2 g; return g; }

socket_t tcp_connect(const std::string& host, uint16_t port, std::string& err) {
    if (!wsa2().ok) { err = "WSAStartup failed"; return kInvalidSocket; }
    struct addrinfo hints {};
    hints.ai_family = AF_UNSPEC;
    hints.ai_socktype = SOCK_STREAM;
    struct addrinfo* res = nullptr;
    if (getaddrinfo(host.c_str(), std::to_string(port).c_str(), &hints, &res) != 0 || !res) {
        err = "DNS failed: " + host;
        return kInvalidSocket;
    }
    socket_t s = socket(res->ai_family, res->ai_socktype, res->ai_protocol);
    if (s == kInvalidSocket) { freeaddrinfo(res); err = "socket() failed"; return s; }
    if (::connect(s, res->ai_addr, (int)res->ai_addrlen) != 0) {
        closesocket(s); freeaddrinfo(res);
        err = "connect failed";
        return kInvalidSocket;
    }
    freeaddrinfo(res);
    int one = 1;
    setsockopt(s, IPPROTO_TCP, TCP_NODELAY, (const char*)&one, sizeof(one));
    return s;
}

void put_u24(uint8_t* p, uint32_t v) {
    p[0] = (uint8_t)(v >> 16); p[1] = (uint8_t)(v >> 8); p[2] = (uint8_t)v;
}
void put_u32(uint8_t* p, uint32_t v) {
    p[0] = (uint8_t)(v >> 24); p[1] = (uint8_t)(v >> 16);
    p[2] = (uint8_t)(v >> 8);  p[3] = (uint8_t)v;
}

void append_frame(std::vector<uint8_t>& out, uint8_t type, uint8_t flags,
                  uint32_t stream_id, const uint8_t* payload, size_t len) {
    uint8_t hdr[9];
    put_u24(hdr, (uint32_t)len);
    hdr[3] = type;
    hdr[4] = flags;
    put_u32(hdr + 5, stream_id & 0x7FFFFFFFu);
    out.insert(out.end(), hdr, hdr + 9);
    if (len) out.insert(out.end(), payload, payload + len);
}

#ifdef VF_HAVE_H2

// HPACK-encode one request's headers with a connection-level deflater
std::vector<uint8_t> hpack_encode(nghttp2_hd_deflater* def,
                                  const RaceRequest& req,
                                  const std::string& scheme,
                                  const std::string& authority) {
    std::vector<nghttp2_nv> nvs;
    auto add = [&](const std::string& n, const std::string& v) {
        nghttp2_nv nv;
        nv.name = (uint8_t*)n.data();  nv.namelen = n.size();
        nv.value = (uint8_t*)v.data(); nv.valuelen = v.size();
        nv.flags = NGHTTP2_NV_FLAG_NONE;
        nvs.push_back(nv);
    };
    add(":method", req.method.empty() ? "GET" : req.method);
    add(":scheme", scheme);
    add(":authority", authority);
    add(":path", req.path);
    for (const auto& h : req.headers) add(h.first, h.second);

    size_t bound = nghttp2_hd_deflate_bound(def, nvs.data(), nvs.size());
    std::vector<uint8_t> block(bound);
    // vcpkg nghttp2 ≥1.63 : la variante legacy deflate_hd est derrière
    // NGHTTP2_NO_SSIZE_T — on utilise la variante nghttp2_ssize (hd2)
    ptrdiff_t n = nghttp2_hd_deflate_hd2(def, block.data(), bound, nvs.data(), nvs.size());
    if (n < 0) block.clear();
    else block.resize((size_t)n);
    return block;
}

bool ssl_send_all(SSL* ssl, const uint8_t* p, size_t n) {
    while (n > 0) {
        int w = SSL_write(ssl, p, (int)std::min<size_t>(n, 16384));
        if (w <= 0) return false;
        p += w; n -= (size_t)w;
    }
    return true;
}

bool plain_send_all(socket_t s, const uint8_t* p, size_t n) {
    while (n > 0) {
#ifdef _WIN32
        int w = ::send(s, (const char*)p, (int)std::min<size_t>(n, 16384), 0);
#else
        ptrdiff_t w = ::send(s, p, std::min<size_t>(n, 16384), 0);
#endif
        if (w <= 0) return false;
        p += w; n -= (size_t)w;
    }
    return true;
}

struct Session {
    SSL* ssl = nullptr;
    socket_t sock = kInvalidSocket;
    std::vector<uint8_t> rbuf;

    bool send_all(const uint8_t* p, size_t n) {
        if (ssl) return ssl_send_all(ssl, p, n);
        return plain_send_all(sock, p, n);
    }
    // blocking read of exactly n bytes (headers) — false on EOF/timeout
    bool read_exact(uint8_t* dst, size_t n) {
        size_t got = 0;
        while (got < n) {
            size_t avail = rbuf.size();
            if (avail > 0) {
                size_t take = std::min(avail, n - got);
                std::memcpy(dst + got, rbuf.data(), take);
                rbuf.erase(rbuf.begin(), rbuf.begin() + (long)take);
                got += take;
                continue;
            }
#ifdef _WIN32
            int r = ssl ? SSL_read(ssl, (char*)dst + got, (int)(n - got))
                        : ::recv(sock, (char*)dst + got, (int)(n - got), 0);
#else
            ptrdiff_t r = ssl ? SSL_read(ssl, (char*)dst + got, (int)(n - got))
                            : ::recv(sock, (char*)dst + got, n - got, 0);
#endif
            if (r <= 0) return false;
            got += (size_t)r;
        }
        return true;
    }
    // read whatever is available now into rbuf (at least 1 byte)
    bool pump() {
        uint8_t tmp[16384];
#ifdef _WIN32
        int r = ssl ? SSL_read(ssl, (char*)tmp, sizeof(tmp))
                    : ::recv(sock, (char*)tmp, sizeof(tmp), 0);
#else
        ptrdiff_t r = ssl ? SSL_read(ssl, (char*)tmp, sizeof(tmp))
                        : ::recv(sock, (char*)tmp, sizeof(tmp), 0);
#endif
        if (r <= 0) return false;
        rbuf.insert(rbuf.end(), tmp, tmp + r);
        return true;
    }
};

#endif // VF_HAVE_H2

} // anonymous namespace

RaceResult execute(const RaceConfig& config) {
    RaceResult r;
#ifndef VF_HAVE_H2
    (void)config;
    r.interpretation = "nghttp2/OpenSSL unavailable in this build (VF_HAVE_H2 undefined)";
    return r;
#else
    uint64_t t0 = now_us();

    // ---- connect + TLS with ALPN h2 ----
    std::string err;
    Session sess;
    sess.sock = tcp_connect(config.host, config.port, err);
    if (sess.sock == kInvalidSocket) {
        r.interpretation = "connect failed: " + err;
        return r;
    }

    SSL_CTX* ctx = nullptr;
    if (config.use_tls) {
        ctx = SSL_CTX_new(TLS_client_method());
        SSL_CTX_set_min_proto_version(ctx, TLS1_2_VERSION);
        SSL_CTX_set_alpn_protos(ctx, (const unsigned char*)"\x02h2", 3);
        sess.ssl = SSL_new(ctx);
        SSL_set_tlsext_host_name(sess.ssl, config.host.c_str());
        SSL_set_fd(sess.ssl, (int)sess.sock);
        if (SSL_connect(sess.ssl) != 1) {
            r.interpretation = "TLS handshake failed";
            SSL_free(sess.ssl); SSL_CTX_free(ctx);
            closesocket(sess.sock);
            return r;
        }
        // confirm ALPN negotiated h2
        const unsigned char* alpn = nullptr; unsigned int alpn_len = 0;
        SSL_get0_alpn_selected(sess.ssl, &alpn, &alpn_len);
        if (alpn_len != 2 || std::memcmp(alpn, "h2", 2) != 0) {
            r.interpretation = "server did not negotiate HTTP/2 (ALPN)";
            SSL_free(sess.ssl); SSL_CTX_free(ctx);
            closesocket(sess.sock);
            return r;
        }
    } else if (config.port != 80 && config.port != 8080) {
        r.interpretation = "cleartext h2 needs port 80/8080-style endpoint";
    }

    std::string authority = config.host;
    if (config.port != 443 && config.port != 80)
        authority += ":" + std::to_string(config.port);
    std::string scheme = config.use_tls ? "https" : "http";

    // recv timeout on the socket (coarse safety net)
#ifdef _WIN32
    DWORD rcv_ms = config.response_timeout_us / 1000 + 1000;
    setsockopt(sess.sock, SOL_SOCKET, SO_RCVTIMEO, (const char*)&rcv_ms, sizeof(rcv_ms));
#else
    struct timeval tv { config.response_timeout_us / 1000000 + 1,
                        (suseconds_t)((config.response_timeout_us % 1000000)) };
    setsockopt(sess.sock, SOL_SOCKET, SO_RCVTIMEO, (const char*)&tv, sizeof(tv));
#endif

    // ---- preface + our SETTINGS + SETTINGS ACK ----
    static const char kPreface[] = "PRI * HTTP/2.0\r\n\r\nSM\r\n\r\n";
    std::vector<uint8_t> hello;
    hello.insert(hello.end(), kPreface, kPreface + 24);
    append_frame(hello, 0x4, 0x0, 0, nullptr, 0);              // SETTINGS
    uint8_t ack[9]; put_u24(ack, 0); ack[3] = 0x4; ack[4] = 0x1; put_u32(ack + 5, 0);
    hello.insert(hello.end(), ack, ack + 9);                    // SETTINGS ACK
    if (!sess.send_all(hello.data(), hello.size())) {
        r.interpretation = "preface send failed";
        if (sess.ssl) { SSL_free(sess.ssl); SSL_CTX_free(ctx); }
        closesocket(sess.sock);
        return r;
    }

    // HPACK sessions (connection-level, order-preserving)
    nghttp2_hd_deflater* def = nullptr;
    nghttp2_hd_inflater* inf = nullptr;
    nghttp2_hd_deflate_new(&def, 4096);
    nghttp2_hd_inflate_new(&inf);

    // ---- warmup streams (fire & forget, ids 1,2? — keep odd: 1) ----
    uint32_t next_sid = 1;
    std::set<uint32_t> warm_ids;
    for (uint32_t i = 0; i < config.warmup_streams; ++i) {
        RaceRequest warm;
        warm.method = "GET";
        warm.path = "/";
        auto block = hpack_encode(def, warm, scheme, authority);
        if (!block.empty()) {
            std::vector<uint8_t> f;
            append_frame(f, 0x1, 0x5 /*END_STREAM|END_HEADERS*/, next_sid,
                         block.data(), block.size());
            sess.send_all(f.data(), f.size());
            warm_ids.insert(next_sid);
        }
        next_sid += 2;
    }

    // ---- THE RACE: build every frame into one buffer ----
    std::vector<uint8_t> flight;
    std::vector<uint32_t> race_ids;
    for (const auto& req : config.requests) {
        uint32_t sid = next_sid;
        next_sid += 2;
        race_ids.push_back(sid);
        auto block = hpack_encode(def, req, scheme, authority);
        if (block.empty()) continue;
        uint8_t hflags = 0x4;                          // END_HEADERS
        if (req.body.empty()) hflags |= 0x1;           // END_STREAM
        append_frame(flight, 0x1, hflags, sid, block.data(), block.size());
        if (!req.body.empty())
            append_frame(flight, 0x0, 0x1 /*END_STREAM*/, sid,
                         (const uint8_t*)req.body.data(), req.body.size());
    }

    r.send_wall_us = now_us() - t0;
    uint64_t send_t0 = now_us();
    bool sent = sess.send_all(flight.data(), flight.size());
    r.send_wall_us = now_us() - send_t0;
    if (!sent) {
        r.interpretation = "race send failed";
        nghttp2_hd_deflate_del(def); nghttp2_hd_inflate_del(inf);
        if (sess.ssl) { SSL_free(sess.ssl); SSL_CTX_free(ctx); }
        closesocket(sess.sock);
        return r;
    }

    // ---- read responses until all race streams close or timeout ----
    std::map<uint32_t, RaceResponse*> by_sid;   // views into r.responses
    std::map<uint32_t, std::string> pending_headers_raw; // not needed — inflate inline
    std::set<uint32_t> closed;
    r.recv_wall_us = 0;
    uint64_t recv_t0 = now_us();
    bool goaway = false;

    std::vector<RaceResponse> store(config.requests.size());
    for (size_t i = 0; i < race_ids.size(); ++i) {
        store[i].stream_id = race_ids[i];
        by_sid[race_ids[i]] = &store[i];
    }

    while (closed.size() < race_ids.size() && !goaway) {
        if (now_us() - recv_t0 > config.response_timeout_us) break;
        uint8_t fh[9];
        if (!sess.read_exact(fh, 9)) break;
        uint32_t flen = ((uint32_t)fh[0] << 16) | ((uint32_t)fh[1] << 8) | fh[2];
        uint8_t ftype = fh[3];
        uint8_t fflags = fh[4];
        uint32_t fsid = 0;
        {
            uint8_t sidb[4];
            if (!sess.read_exact(sidb, 4)) break;
            fsid = ((uint32_t)sidb[0] << 24 | (uint32_t)sidb[1] << 16 |
                    (uint32_t)sidb[2] << 8 | sidb[3]) & 0x7FFFFFFFu;
        }
        std::vector<uint8_t> payload(flen);
        if (flen > 0 && !sess.read_exact(payload.data(), flen)) break;

        if (warm_ids.count(fsid)) {
            if ((ftype == 0x1 && (fflags & 0x1)) || ftype == 0x3)
                warm_ids.erase(fsid);
            continue;
        }
        if (!by_sid.count(fsid) && ftype != 0x7) continue;  // stray frame

        switch (ftype) {
            case 0x1: {  // HEADERS
                RaceResponse* resp = by_sid[fsid];
                // inflate HPACK block (connection-level inflater, wire order)
                ptrdiff_t rc = 0;
                const uint8_t* in = payload.data();
                size_t inlen = payload.size();
                while (rc >= 0) {
                    nghttp2_nv nv;
                    int inflate_flags = 0;
                    size_t proclen = inlen;
                    // hd3 : (inflater, nv_out, flags, const in, inlen, in_final)
                    // bloc de headers complet en un morceau → in_final=1
                    rc = nghttp2_hd_inflate_hd3(inf, &nv, &inflate_flags, in, proclen, 1);
                    if (rc < 0) break;
                    in += rc; inlen -= (size_t)rc;
                    if (inflate_flags & NGHTTP2_HD_INFLATE_EMIT) {
                        std::string name((const char*)nv.name, nv.namelen);
                        std::string value((const char*)nv.value, nv.valuelen);
                        if (name == ":status") {
                            try { resp->status_code = std::stoi(value); } catch (...) {}
                        } else {
                            resp->headers.emplace_back(name, value);
                        }
                    }
                    if (inflate_flags & NGHTTP2_HD_INFLATE_FINAL) {
                        nghttp2_hd_inflate_end_headers(inf);
                        break;
                    }
                    if (inlen == 0 && !(inflate_flags & NGHTTP2_HD_INFLATE_EMIT)) break;
                }
                if (fflags & 0x1) closed.insert(fsid);   // END_STREAM on trailers/headers
                break;
            }
            case 0x0: {  // DATA
                RaceResponse* resp = by_sid[fsid];
                resp->body.append((const char*)payload.data(), payload.size());
                if (fflags & 0x1) closed.insert(fsid);
                break;
            }
            case 0x3:  // RST_STREAM
                closed.insert(fsid);
                break;
            case 0x7:  // GOAWAY
                goaway = true;
                break;
            default:   // SETTINGS(4)/PING(6)/WINDOW_UPDATE(8)/PRIORITY(2) — ignore
                break;
        }
    }
    r.recv_wall_us = now_us() - recv_t0;

    // ---- results ----
    std::set<std::string> bodies;
    for (auto& resp : store) {
        r.responses.push_back(std::move(resp));
        if (resp.status_code >= 200 && resp.status_code < 300) r.successful_2xx++;
        if (!resp.body.empty()) bodies.insert(resp.body);
    }
    r.distinct_bodies = (int)bodies.size();
    r.interpretation =
        r.successful_2xx > 1 ? "single-use guard ABSENT — race WIN" :
        r.successful_2xx == 1 ? "guard held — atomic" :
        "no 2xx observed — verify request validity";

    nghttp2_hd_deflate_del(def);
    nghttp2_hd_inflate_del(inf);
    if (sess.ssl) { SSL_shutdown(sess.ssl); SSL_free(sess.ssl); }
    if (ctx) SSL_CTX_free(ctx);
    closesocket(sess.sock);
    return r;
#endif
}

} // namespace vf::h2race
