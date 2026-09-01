// VOIDFORGE net_pacer — µs-precision replay implementation.
// Windows: Winsock2 + QueryPerformanceCounter + hybrid spin-wait.
// Linux:   POSIX sockets + clock_nanosleep.
// TLS:     OpenSSL (VF_HAVE_OPENSSL).
#include "net_pacer.h"

#include <cstring>
#include <thread>

#ifdef _WIN32
#  ifndef WIN32_LEAN_AND_MEAN
#    define WIN32_LEAN_AND_MEAN
#  endif
#  include <winsock2.h>
#  include <ws2tcpip.h>
#  include <timeapi.h>
#  pragma comment(lib, "ws2_32.lib")
#  pragma comment(lib, "winmm.lib")
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
#  include <time.h>
#  include <sched.h>
#  include <cerrno>
using socket_t = int;
static const socket_t kInvalidSocket = -1;
#endif

#ifdef VF_HAVE_OPENSSL
#  include <openssl/ssl.h>
#  include <openssl/err.h>
#endif

namespace vf::net {

namespace {

// ---- one-time WSA startup on Windows ----
struct WsaGuard {
    bool ok = true;
#ifdef _WIN32
    WsaGuard() {
        WSADATA d; ok = (WSAStartup(MAKEWORD(2, 2), &d) == 0);
        // timer resolution 1ms — sans ça Sleep(1) peut dormir 15.6ms
        timeBeginPeriod(1);
    }
    ~WsaGuard() { if (ok) { timeEndPeriod(1); WSACleanup(); } }
#endif
};
WsaGuard& wsa() { static WsaGuard g; return g; }

// ---- precise hybrid wait: Sleep for the bulk, pure spin for the tail ----
// Windows sans timeBeginPeriod: Sleep(1) ≈ 1-2ms (une fois la résolution
// montée). On ne dort que si le reste > 5ms → jamais d'overshoot; la queue
// est un spin pur → précision sub-µs. (Contrat perf: jitter ≤ 500µs.)
void precise_wait_until(uint64_t target_us) {
#ifdef _WIN32
    static LARGE_INTEGER freq = [] { LARGE_INTEGER f; QueryPerformanceFrequency(&f); return f; }();
    LARGE_INTEGER now;
    for (;;) {
        QueryPerformanceCounter(&now);
        uint64_t nowu = (uint64_t)(now.QuadPart * 1000000LL / freq.QuadPart);
        if (nowu >= target_us) return;
        uint64_t remain = target_us - nowu;
        if (remain > 5000) Sleep(1);          // ≤5ms d'erreur pire-case
        else if (remain > 100) YieldProcessor(); // yield-spin
        else { /* full spin final */ }
    }
#else
    uint64_t nowu;
    struct timespec ts;
    for (;;) {
        clock_gettime(CLOCK_MONOTONIC, &ts);
        nowu = (uint64_t)ts.tv_sec * 1000000ull + ts.tv_nsec / 1000ull;
        if (nowu >= target_us) return;
        uint64_t remain = target_us - nowu;
        if (remain > 5000) { ts.tv_nsec = 100000; nanosleep(&ts, nullptr); }
        else if (remain > 100) sched_yield();
    }
#endif
}

// ---- connect with timeout (non-blocking connect + select) ----
socket_t connect_host(const std::string& host, uint16_t port, uint32_t timeout_us,
                      std::string& err) {
    if (!wsa().ok) { err = "WSAStartup failed"; return kInvalidSocket; }

    struct addrinfo hints {};
    hints.ai_family = AF_UNSPEC;
    hints.ai_socktype = SOCK_STREAM;
    hints.ai_protocol = IPPROTO_TCP;
    struct addrinfo* res = nullptr;
    if (getaddrinfo(host.c_str(), std::to_string(port).c_str(), &hints, &res) != 0 || !res) {
        err = "DNS resolution failed: " + host;
        return kInvalidSocket;
    }

    socket_t s = socket(res->ai_family, res->ai_socktype, res->ai_protocol);
    if (s == kInvalidSocket) {
        freeaddrinfo(res);
        err = "socket() failed";
        return s;
    }

#ifdef _WIN32
    u_long nb = 1; ioctlsocket(s, FIONBIO, &nb);
#else
    int flags = fcntl(s, F_GETFL, 0);
    fcntl(s, F_SETFL, flags | O_NONBLOCK);
#endif

    int rc = ::connect(s, res->ai_addr, (int)res->ai_addrlen);
    bool connected = (rc == 0);
    if (!connected) {
        fd_set wset, eset;
        FD_ZERO(&wset); FD_SET(s, &wset);
        FD_ZERO(&eset); FD_SET(s, &eset);
        struct timeval tv { (long)(timeout_us / 1000000), (long)((timeout_us % 1000000)) };
#ifdef _WIN32
        int sel = select(0, nullptr, &wset, &eset, &tv);
#else
        int sel = select((int)s + 1, nullptr, &wset, &eset, &tv);
#endif
        if (sel > 0 && FD_ISSET(s, &wset)) connected = true;
    }
    freeaddrinfo(res);

    if (!connected) {
        closesocket(s);
        err = "connect timeout/failed";
        return kInvalidSocket;
    }

#ifdef _WIN32
    u_long nb0 = 0; ioctlsocket(s, FIONBIO, &nb0);   // back to blocking
#else
    fcntl(s, F_SETFL, flags);                        // back to blocking
#endif
    int one = 1;
    setsockopt(s, IPPROTO_TCP, TCP_NODELAY, (const char*)&one, sizeof(one));
    return s;
}

void close_socket(socket_t s) {
    if (s != kInvalidSocket) closesocket(s);
}

// ---- wait for socket readability within deadline ----
bool wait_readable(socket_t s, uint64_t deadline_us) {
    uint64_t now = now_us();
    if (now >= deadline_us) return false;
    uint64_t remain = deadline_us - now;
    fd_set rset;
    FD_ZERO(&rset); FD_SET(s, &rset);
    struct timeval tv { (long)(remain / 1000000), (long)(remain % 1000000) };
#ifdef _WIN32
    return select(0, &rset, nullptr, nullptr, &tv) > 0;
#else
    return select((int)s + 1, &rset, nullptr, nullptr, &tv) > 0;
#endif
}

// ---- recv until quiescence or deadline (read loop, keeps extras) ----
// quiescence 8ms: assez pour attraper les fragments TCP d'une réponse,
// assez court pour ne pas dévorer les delay_us des messages suivants.
std::string recv_response(socket_t s, uint32_t timeout_us, bool& timed_out) {
    timed_out = false;
    std::string out;
    uint64_t deadline = now_us() + timeout_us;
    char buf[16384];
    // first byte must arrive within the full timeout; then 8ms quiescence
    if (!wait_readable(s, deadline)) { timed_out = true; return out; }
    for (;;) {
#ifdef _WIN32
        int n = ::recv(s, buf, sizeof(buf), 0);
#else
        ssize_t n = ::recv(s, buf, sizeof(buf), 0);
#endif
        if (n <= 0) break;
        out.append(buf, buf + n);
        uint64_t now = now_us();
        if (now + 8000 >= deadline) break;          // no time for another window
        if (!wait_readable(s, now + 8000)) break;   // 8ms quiescence
    }
    return out;
}

#ifdef VF_HAVE_OPENSSL
// TLS read with deadline via non-blocking SSL + select on underlying fd
std::string recv_response_tls(SSL* ssl, socket_t s, uint32_t timeout_us, bool& timed_out) {
    timed_out = false;
    std::string out;
    uint64_t deadline = now_us() + timeout_us;
    char buf[16384];
    for (;;) {
        int n = SSL_read(ssl, buf, (int)sizeof(buf));
        if (n > 0) {
            out.append(buf, buf + n);
            uint64_t now2 = now_us();
            if (now2 + 50000 >= deadline) break;
            if (!wait_readable(s, now2 + 50000)) break;
            continue;
        }
        int err = SSL_get_error(ssl, n);
        if (err == SSL_ERROR_WANT_READ) {
            if (!wait_readable(s, deadline)) { timed_out = true; break; }
            continue;
        }
        break;  // ZERO_RETURN (clean close) or hard error → done
    }
    return out;
}
#endif

} // anonymous namespace

ReplayResult replay(const ReplayConfig& config) {
    ReplayResult r;
    uint64_t t0 = now_us();

    socket_t s = connect_host(config.host, config.port, 5000000, r.error);
    if (s == kInvalidSocket) {
        r.total_elapsed_us = now_us() - t0;
        return r;
    }
    r.connection_ok = true;

#ifdef VF_HAVE_OPENSSL
    SSL_CTX* ctx = nullptr;
    SSL* ssl = nullptr;
    if (config.use_tls) {
        ctx = SSL_CTX_new(TLS_client_method());
        SSL_CTX_set_min_proto_version(ctx, TLS1_2_VERSION);
        ssl = SSL_new(ctx);
        SSL_set_tlsext_host_name(ssl, config.host.c_str());
        SSL_set_fd(ssl, (int)s);
        if (SSL_connect(ssl) != 1) {
            r.error = "TLS handshake failed";
            SSL_free(ssl); SSL_CTX_free(ctx); close_socket(s);
            r.total_elapsed_us = now_us() - t0;
            return r;
        }
    }
#endif

    for (size_t i = 0; i < config.sequence.size(); ++i) {
        Message msg = config.sequence[i];
        if ((int)i == config.mutate_index) msg.data = config.mutation;

        if (msg.delay_us > 0)
            precise_wait_until(t0 + msg.delay_us);

        Response resp;
        resp.send_time_us = now_us();

        // full send loop
        const char* p = msg.data.data();
        size_t left = msg.data.size();
        bool send_ok = true;
#ifdef VF_HAVE_OPENSSL
        if (ssl) {
            while (left > 0) {
                int n = SSL_write(ssl, p, (int)left);
                if (n <= 0) { send_ok = false; break; }
                p += n; left -= (size_t)n;
            }
        } else
#endif
        {
#ifdef _WIN32
            while (left > 0) {
                int n = ::send(s, p, (int)left, 0);
                if (n <= 0) { send_ok = false; break; }
                p += n; left -= (size_t)n;
            }
#else
            while (left > 0) {
                ssize_t n = ::send(s, p, left, 0);
                if (n <= 0) { send_ok = false; break; }
                p += n; left -= (size_t)n;
            }
#endif
        }
        if (!send_ok) {
            resp.status = -2;
            r.responses.push_back(resp);
            r.error = "send failed mid-sequence";
            break;
        }

        if (msg.expect_response) {
            bool timed_out = false;
#ifdef VF_HAVE_OPENSSL
            if (ssl) resp.data = recv_response_tls(ssl, s, msg.response_timeout_us, timed_out);
            else
#endif
            resp.data = recv_response(s, msg.response_timeout_us, timed_out);
            resp.recv_time_us = now_us();
            resp.status = timed_out ? -1 : 0;
        }
        r.responses.push_back(resp);
    }

#ifdef VF_HAVE_OPENSSL
    if (ssl) { SSL_shutdown(ssl); SSL_free(ssl); }
    if (ctx) SSL_CTX_free(ctx);
#endif
    close_socket(s);
    r.total_elapsed_us = now_us() - t0;
    return r;
}

std::vector<ReplayResult> replay_batch(
    const ReplayConfig& base_config,
    const std::vector<std::string>& mutations) {
    std::vector<ReplayResult> out;
    out.reserve(mutations.size());
    for (const auto& m : mutations) {
        ReplayConfig c = base_config;
        c.mutation = m;
        out.push_back(replay(c));
    }
    return out;
}

} // namespace vf::net
