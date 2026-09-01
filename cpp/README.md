# VOIDFORGE C++ Hot Cores — `voidforge_native`

Pybind11 module exposing the high-performance cores to the Python brain.
**Status: built with ALL gates ON (Unicorn + OpenSSL + nghttp2) — acceptance
`lab/cpp_acceptance.py`: 15 PASS · 0 FAIL · 1 N/A (h2 live endpoint), exit 0.**
Measured: 4421 exec/s emu batch · net_pacer jitter 0.001ms · dedup triage OK.

| Submodule | Core | Purpose |
|---|---|---|
| `emu` | Unicorn engine | block-coverage emulation, batch = 1 FFI crossing, GIL free |
| `triage` | OpenSSL SHA256 | crash dedup (stack hash) + 0-6 exploitability ranking |
| `net` | Winsock2/POSIX | µs-precision stateful protocol replay (`net_pacer`) |
| `h2race` | OpenSSL + nghttp2 | HTTP/2 single-packet race (Kettle technique) |
| `heap` | CRT/glibc oracle | heap grooming: reuse-rate measurement, spray/punch/check |
| `libfuzz` | Linux/Clang only | programmatic libFuzzer campaign runner |
| (AFL++) | `vf_mutator.so` | custom mutator: RedQueen + splice + grammar + arithmetic |

## Build (Windows, MSVC BuildTools 2022)

```powershell
# deps (one-time) — perl est REQUIS par openssl (portable Strawberry Perl OK)
C:\vcpkg\vcpkg install unicorn openssl nghttp2 --triplet x64-windows
pip install pybind11 cmake

# configure + build — TOUJOURS via cpp\msvc_env.bat : vcvars64 seul laisse le
# SDK (INCLUDE/LIB) et rc.exe hors PATH → compiler detection "broken".
cd cpp
call msvc_env.bat
cmake -B build -G Ninja `
  -DCMAKE_TOOLCHAIN_FILE=C:/vcpkg/scripts/buildsystems/vcpkg.cmake `
  -DVCPKG_TARGET_TRIPLET=x64-windows `
  -Dpybind11_DIR=$(python -c "import pybind11; print(pybind11.get_cmake_dir())")
cmake --build build
# → build\voidforge_native.cp314-win_amd64.pyd — copy to VOIDFORGE root
#   AVEC les DLLs vcpkg (unicorn, nghttp2, libcrypto-3, libssl-3) :
copy build\voidforge_native.cp314-win_amd64.pyd ..
copy C:\vcpkg\installed\x64-windows\bin\*.dll ..
```

## Build (WSL/Linux — mutator + libFuzzer driver)

```bash
cd /mnt/c/Users/youcef\ cheriet/D/VOIDFORGE/cpp
cmake -B build-wsl -DCMAKE_CXX_COMPILER=clang++
cmake --build build-wsl
# → build-wsl/vf_mutator.so  (AFL_CUSTOM_MUTATOR_LIBRARY=./vf_mutator.so)
```

## Verify

```python
import voidforge_native as vn
print(dir(vn.emu), dir(vn.triage), dir(vn.net), dir(vn.h2race), dir(vn.heap))
```

## Feature gates (compile-time)

| Gate | Deps | Missing → |
|---|---|---|
| `VF_HAVE_UNICORN` | unicorn | `emu` functions return `NATIVE_UNAVAILABLE` results |
| `VF_HAVE_H2` | nghttp2 + OpenSSL | `h2race.execute` returns structured error |
| OpenSSL | always required | triage SHA256 + TLS + h2 |
| `vf_mutator.so` | Linux only | not built on Windows |
| `libfuzz` submodule | Linux + Clang | not exposed on Windows |

## Semantic notes (honest deviations from plan §5.5)

- **Emu timeout** : `uc_emu_start(timeout)` interne coûte ~15ms/run sous
  Windows (66 exec/s). Remplacé par un **watchdog persistant par engine**
  (condvar + `uc_emu_stop` cross-thread documenté) → 4421 exec/s, sémantique
  identique (`result.timeout=true` si deadline atteinte).
- **Self-modification** : le code n'est réécrit que si le guest a écrit dans
  sa page (hook `UC_HOOK_MEM_WRITE` sur `[code_base, code_end)`) — un
  `uc_mem_write` par run invaliderait le TB cache QEMU à chaque fois.
- **Stop address** : capé à `entry + code_len` — le padding de page n'est
  jamais exécuté même si `exit_addr` dépasse la fin du code (plan: 0x40000B
  sur un sled de 10 nops → 10 insns exécutés, pas 11).
- `replay_batch` opens a **fresh connection per mutation** — independent
  state per trial is the safer semantic for stateful fuzzing. The
  one-connection prefix amortization from the plan is deferred.
- `heap` oracle measures the **process CRT/glibc allocator** (truthful
  label in results) — NT-heap LFH rend le reuse-rate LIFO improbable sous
  Windows (mesuré 1-43% selon l'état du bucket) ; le seuil >0.9 du plan
  vaut pour ptmalloc/tcache.
- **nghttp2 ≥1.63 (vcpkg)** : `NGHTTP2_NO_SSIZE_T` requis sous MSVC + les
  variantes `nghttp2_hd_deflate_hd2` / `hd_inflate_hd3` (les legacy
  `ssize_t` sont POSIX-only).
- Instruction counting uses a per-insn code hook (exact counts for
  acceptance test #1). For raw throughput runs, batch perf target is
  validated on short inputs.

## Contracts (non-negotiable, enforced)

1. Every function returns JSON-serializable data (`py::dict`/primitives/stl).
2. No C++ exception escapes into Python — structured `error` fields.
3. Coverage bitmaps are `py::bytes` (64KB, AFL++ layout).
4. All timings are microseconds (`uint64_t`).
5. Paths are UTF-8 `std::string`.
