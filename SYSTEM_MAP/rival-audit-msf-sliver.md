# Rival Audit: Metasploit-Framework vs. Sliver — Architecture Deep-Dive

*Audited from source: `C:\Users\youcef cheriet\D\VOIDFORGE\_rivals\metasploit-framework` (Ruby) and `_rivals\sliver` (Go, BishopFox). All paths/symbols below were read directly from these checkouts.*

---

# PART I — METASPLOIT-FRAMEWORK

## 1. Module Architecture: `Msf::Exploit` and the Mixin Composition System

### 1.1 The loading contract

Every module file declares one class named `MetasploitModule`. The loader (`lib/msf/core/modules/loader/base.rb`, `module_eval_with_lexical_scope`, lines 47–50, 144) reads the file and `module_eval`s its content **inside a generated namespace module**, so the class binds lexically against the framework's constants — that's why a bare `class MetasploitModule < Msf::Exploit::Remote` resolves `Msf::Exploit::Remote`, `Rank`, and `ExcellentRanking` without any explicit qualification. This is the entire module-DSL trick: one constant, lexically scoped eval, and the file *is* the module.

### 1.2 Class hierarchy

`Msf::Exploit < Msf::Module` (`lib/msf/core/exploit.rb:13`). The base class carries:

- **Targets** — `Rex::Transformer.transform(info['Targets'], Array, [Target], 'Targets')` (`exploit.rb:282`); auto-target injection when no "Automatic" target exists (`has_auto_target?`, lines 315–321; `lib/msf/core/exploit/auto_target.rb` for fingerprint-driven selection).
- **Stances** — `Msf::Exploit::Stance::Aggressive/Passive` (`exploit.rb:183–197`); aggressive exploits get a `WfsDelay` advanced option automatically (`exploit.rb:298–303`).
- **CheckCode** — a `Struct.new(:code, :message, :reason, :details, :vuln)` with six factories (`exploit.rb:52–153`): `Unknown`, `Safe`, `Detected`, `Appears`, `Vulnerable`, `Unsupported`. Contract enforced repo-wide (see `AGENTS.md`): `check` returns only CheckCodes with a reason string; `CheckCode::Vulnerable` requires hard evidence (command output), `Appears` is version/banner inference.
- **Failure taxonomy** — `fail_with(Failure::Unreachable|NoAccess|UnexpectedReply|...)`, `Msf::Exploit::Failure::None` default (`exploit.rb:287`).
- **Lifecycle** — `setup` (starts payload handler, `exploit.rb:394`), `exploit` (empty stub, line 341, always overridden), `cleanup`, `session_created?` used by mixin loops to stop brute-forcing once a session lands.

### 1.3 The mixin composition system (the core mechanism)

Mixins are ordinary Ruby modules under `Msf::Exploit::*` composed with `include`/`prepend`. `Msf::Exploit.mixins` (`exploit.rb:212–242`) even does a BFS over the `Msf::Exploit` namespace to enumerate every loaded mixin for tooling. Four composition patterns:

**A. Protocol mixins — wrap I/O, register options, define connection state.**
- `Msf::Exploit::Remote::Tcp` (`lib/msf/core/exploit/remote/tcp.rb:47`): `connect(global, opts)` (line 91), `disconnect` (185), `connect_timeout` (249), plus `EvasiveTCP` (line 5) for IDS-evasive socket flags. The framework auto-prepends `host:port` to `print_*` output via `print_prefix` (documented in `AGENTS.md`), so modules never hand-format peers.
- `Msf::Exploit::Remote::HttpClient` (`lib/msf/core/exploit/remote/http_client.rb:14`): `connect` (150), `send_request_cgi` (462), `send_request_cgi!` (492 — fails the module on connection error), `connect_ws` (265), HTML/JSON response helpers (`res.get_html_document`, `res.get_json_document`).
- Sibling protocol mixins in `lib/msf/core/exploit/`: `smb/` (RubySMB), `sqli/` (full SQLi DSL), `ntlm.rb`, `powershell.rb`, `java.rb`, `oracle.rb`, `pgadmin.rb`, `view_state.rb`, `laravel_crypto_killer.rb` — each a self-contained protocol stack.

**B. Technique mixins — override the exploit loop itself and call back into the module.**
- `Msf::Exploit::Brute` (`lib/msf/core/exploit/brute.rb:12`): **replaces `exploit`** (line 38). Reads `target.bruteforce` start/stop/step addresses, computes per-key direction (lines 53–67), lets the datastore override addresses via `import_from_datastore` (`Start*`/`Stop*` prefixed keys, lines 178–184), auto-derives step from `payload.nop_sled_size` (92–102), then loops `brute_exploit(curr)` → `brute_wait` → increment, **breaking on `session_created?`** (line 108). The module author implements only `brute_exploit(addrs)` (152) and `single_exploit` (158). It registers `BruteWait`/`BruteStep` advanced options namespaced to `Msf::Exploit::Brute` (25–29).
- `Msf::Exploit::CmdStager` (`lib/msf/core/exploit/cmd_stager.rb` + `cmd_stager/` backends for Windows/Linux/Unix/VBS/PowerShell/Bourne), `Msf::Exploit::Egghunter`, `Msf::Exploit::Seh`, `Msf::Exploit::FileDropper` (registers files for cleanup; `needs_cleanup` propagates to `Msf::Post`, see `post.rb:18`), `Msf::Exploit::EXE` (payload→binary formats), `Msf::Exploit::Retry`.

**C. Cross-cutting wrappers via `prepend`.**
- `prepend Msf::Exploit::Remote::AutoCheck` must be the **last** line of the mixin block (`AGENTS.md` — include raises `NotImplementedError`). Prepending makes `AutoCheck#exploit` shadow the composed `exploit`: it runs `check`, aborts unless `CheckCode::Vulnerable/Appears` (override: `ForceExploit true`), then `super`s into the real chain. This is AOP-as-policy: the framework injects a *verify-before-fire* gate into every modern module without touching its body.

**D. Order is contract** (documented in `AGENTS.md`): protocol mixins → utility mixins → `Msf::Auxiliary::Report` → post mixins → `prepend AutoCheck`. Because later `include`s shadow earlier method definitions, ordering decides which `connect`/`exploit` wins; mixin authors call `super` inside `initialize`, `setup`, `cleanup` to preserve the chain.

### 1.4 A real module, dissected

`modules/exploits/linux/http/zimbra_xxe_rce.rb`:

```ruby
class MetasploitModule < Msf::Exploit::Remote   # line 6
  Rank = ExcellentRanking                       # line 7
  include Msf::Exploit::Remote::HttpClient      # line 9
  include Msf::Exploit::Remote::HttpServer      # line 10 (second-stage callback listener)
  include Msf::Exploit::FileDropper             # line 11
  def check ... end                             # line 187
  def exploit ... end                           # line 256
  fail_with(Failure::UnexpectedReply, ...)      # lines 216, 225, 233, 242
```

### 1.5 Datastore

- Base store: `lib/msf/core/data_store.rb` (keyed strings, user-defined vs. defaults, aliases).
- `Msf::ModuleDataStore < DataStore` (`lib/msf/core/module_data_store.rb:11`) implements **global→module inheritance** in `search_for` (lines 35–62), a deterministic cascade:
  1. module user-defined value,
  2. framework (global `setg`) value — but *only* if non-default (line 41),
  3. registered option **fallbacks** (e.g. `SMBUser` falls back to generic `Username`, lines 46–53),
  4. imported defaults,
  5. option default,
  6. framework datastore again as last resort.
- Options are typed (`OptString/OptInt/OptBool/OptPath`, `lib/msf/core/option_container.rb`), validated by `exploit.options.validate(exploit.datastore)` inside `Msf::ExploitDriver#validate` (`lib/msf/core/exploit_driver.rb:104–111`).
- Payloads share the exploit's datastore — `LHOST/LPORT` set once applies to both (exploit_driver comment, line 108).

## 2. Ranking & Reliability: `Msf::Rank` in Theory and Use

**Definition** — `lib/msf/core/constants.rb:36–52`: an integer ladder `ManualRanking=0, Low=100, Average=200, Normal=300, Good=400, Great=500, Excellent=600` plus the display map `RankingName`. Module-side accessor: `lib/msf/core/module/ranking.rb` (`Msf::Module::Ranking` ActiveSupport concern): `ClassMethods#rank` = `const_defined?('Rank') ? const_get('Rank') : Msf::NormalRanking` (lines 8–10), with `rank_to_s`/`rank_to_h` for display. Rank is **author-attested**, enforced by `tools/dev/msftidy.rb` + the `Notes` hash (`Stability`/`SideEffects`/`Reliability` enums, `constants.rb:57–111`: e.g. `REPEATABLE_SESSION`, `CRASH_SAFE`, `IOC_IN_LOGS`).

**Consumption points:**
1. **Console gating** — `lib/msf/ui/console/command_dispatcher/exploit.rb:104–112`: `minrank = RankingName.invert[framework.datastore['MinimumRank']] || 0`; attempts to run a lower-ranked exploit print an error unless you lower `setg MinimumRank` — a global quality floor for automation.
2. **Search/sort** — `lib/msf/ui/console/command_dispatcher/modules.rb`: `rank` search filter with numeric comparison operators (`'rank' => 'gte400'`, line 402), sort key (lines 416, 457, 559), table `RankFormatter`/`RankStyler` (lines 1831–1837).
3. **Automated selection** — `modules/auxiliary/server/browser_autopwn2.rb` + mixin `lib/msf/core/exploit/remote/browser_autopwn2.rb`: builds `bap_groups[ranking]` (line 211), sorts groups descending (`bap_groups.sort_by {|k,v| k}.reverse`, line 224), skips exploits not matching the current rank bucket (line 237) — i.e., **the framework itself picks highest-rank browser exploits to serve**, payload auto-selection per OS at line 128/411.
4. **Driver-level** — `Msf::ExploitDriver` (`lib/msf/core/exploit_driver.rb`) is the framework's programmatic run loop: `validate` (69–114) enforces target/payload compatibility + cleanup feasibility, then `run` (line 117+) generates payload, launches handler, executes. This + MinimumRank is exactly the seam automation (Nexpose integration historically, modern `msfrpcd`/`msf-json-rpc.ru` at repo root) uses.

## 3. The DB & Workspace Memory

**Architecture**: `Msf::DBManager` is composed from concern modules in `lib/msf/core/db_manager/` — `host.rb`, `service.rb`, `vuln.rb`, `cred.rb`, `loot.rb`, `session.rb`, `event.rb`, `exploit_attempt.rb`, `vuln_detail.rb`, `web.rb`, `wmap.rb`, `workspace.rb`, plus `import.rb`/`db_export.rb` (Nexpose/Nmap/PcapXML ingestion). The ORM models (`Mdm::*`, `Metasploit::Credential::*`) live in the external `metasploit_data_models` / `metasploit-credential` gems — this repo's `app/models/` contains only `application_record.rb` — backed by Postgres via `::ApplicationRecord.connection_pool.with_connection` (`db_manager/cred.rb:5`).

**Write path** — `lib/msf/core/auxiliary/report.rb` is the module-facing API: `report_host` (129), `report_service` (170), `report_note` (179), `report_vuln` (292), `report_exploit` (348), `report_loot` (357), `report_web_site/page/form/vuln` (366–393), `store_loot` (419), `store_local` (494), `store_cred` (549), and the credential trio `create_credential` (37), `create_credential_login` (47), `create_credential_and_login` (57) which map into `Metasploit::Credential::Core/Private/Public/Login` (JTR-format-tagged hashes). `db_manager/cred.rb#creds` (3–66) is the read side: an ActiveRecord query joining `Core → Private/Public/Realm` and `logins → service → host`, filterable by type, `jtr_format`, ports, services, user, pass, or free-text.

**How post-exploitation feeds the next module** — three concrete loops, all operator-initiated by design:

1. **`-R` pivot flags**: `lib/msf/ui/console/command_dispatcher/db.rb` — `hosts -R` / `services -R` / `creds -R` collect matching addrs and call `set_rhosts_from_addrs(rhosts.uniq)` (lines 414, 501–502, 643–667), writing `RHOSTS` straight into the datastore. The canonical "found 40 SSH hosts → run ssh_login against all" automation.
2. **Credential reuse**: scanner/session modules (`auxiliary/scanner/ssh/ssh_login`, `smb_login`, etc.) call `create_credential_and_login` on success — the cred lands in the workspace keyed to `Mdm::Service`. The operator then either reuses it via the `creds` table (`creds` prints `public:private@login`), or runs `exploit/windows/smb/psexec` with the harvested NTLM hash (hashdump post module → `Metasploit::Credential::Private` with `jtr_format=nt` → `SMBPass <hash>`). No silent autofill — but the full chain is machine-queryable, and resource scripts (`resource -s`) or the `db.rb` helpers automate the copy.
3. **Vuln/session bookkeeping**: sessions become `Mdm::Session` rows (`db_manager/session.rb`); `post` modules read/write via the same Report API; `vulns` + `exploit_attempt` tables let automation (and `check` runs through `AutoCheck`) correlate a discovered vuln to the exploit that proves it.

The workspace (`db_manager/workspace.rb`, `Mdm::Workspace` scoping in every query, e.g. `cred.rb:14`) partitions all of this per engagement — the DB *is* the framework's long-term memory, and `module_cache.rb` keeps the module index queryable too.

## 4. AUX vs EXPLOIT vs POST — Three Cognitive Roles

| | `Msf::Auxiliary` | `Msf::Exploit` | `Msf::Post` |
|---|---|---|---|
| Base | `lib/msf/core/auxiliary.rb:13` | `exploit.rb:13` | `post.rb:6` (+ `Msf::PostMixin`) |
| Entry | `run` (60) | `exploit` (341) | `run` (via PostMixin) |
| Payload/Targets | none | payload↔target compat matrix | none (operates inside a session) |
| Session req. | no | creates sessions | **required** — `OptInt.new('SESSION', [true, ...], -1)` (`post_mixin.rb:24`), session-type compatibility via `Msf::SessionCompatibility` (`post_mixin.rb:7`) |
| Autocreation | singleton (`self.create`, 55–58) | per-run instance | anonymous `self.create(session)` for IRB (42–55) |
| `autofilter` default | `false` (79–81) | `true` (353) | n/a |
| Rank | advisory | drives MinimumRank/autopwn | advisory |
| DB contract | **producer**: report_*/store_* | producer + session spawn | **consumer+producer**: harvest creds/loot/screenshots, write back |

**Cognitive reading**: auxiliary = *sensory organs* (scan, fingerprint, brute, fuzz, sniff → convert the world into DB facts); exploit = *action organs* (convert a DB fact — service, version, vuln — into code execution and a session, gated by check/rank); post = *digestion* (inside the session, extract hashes/creds/loot/route info and write it back, which re-arms the other two). The Postgres workspace is the blackboard that makes the three families a closed cognitive loop.

---

# PART II — SLIVER

## 5. Implant Architecture: Sessions, Tunnels, P2P, and Evasion

### 5.1 Two execution modes from one template

Entry: `implant/sliver/main.go:47` → `runner.Main()` (`implant/sliver/runner/runner.go:100`). The same source compiles to **beacon** or **session** mode purely by template conditionals (`{{if .Config.IsBeacon}}` / `{{else}}`, lines 125–131), plus service-shellcode/shared-lib variants (`{{if .Config.IsService}}` svc.Run, lines 67–98; `{{range .Config.Exports}}` exported entrypoints in `main.go:36–44`). Before anything, `limits.ExecLimits()` (runner.go:119, `implant/sliver/limits/`) performs environment checks (hostname/user/domain/UID deny-lists compiled per build) to refuse execution in the wrong sandbox/AV analysis host.

### 5.2 Session mode (interactive)

`sessionMainLoop` (runner.go:621–742): `connection.Start()` → `pivots.RestartAllListeners` (635) → `MsgRegister` with full host inventory (`registerSliver`, 760–817: hostname, host UUID `implant/sliver/hostuuid/`, user/uid/gid, OS/arch/pid, binary path, `ConfigID`, `PeerID`, `Capabilities`) → then a receive loop dispatching envelopes by type across **five handler tables**: `GetPivotHandlers`, `GetTunnelHandlers`, `GetSystemHandlers`, `GetKillHandlers`, `GetRportFwdHandlers` (649–653). Windows token impersonation forces a per-task `WrapperHandler` because `ImpersonateLoggedOnUser` is thread-affine (the comment at 685–689 says exactly that). `MsgCloseSession` → clean exit (726).

### 5.3 Beacon mode (async)

- `beaconStartup` (runner.go:135–175): `transports.StartBeaconLoop` yields a `Beacon` — a struct of six function pointers `Init/Start/Send/Recv/Close/Cleanup` (`implant/sliver/transports/beacon.go:78–96`), implemented per-transport (mtls/wg/http/dns) by switch on the C2 URI scheme (beacon.go:150–170). Failures count against `GetMaxConnectionErrors()` (compile-time `{{.Config.MaxConnectionErrors}}`, `transports/transports.go:216–222`) then the implant exits; otherwise sleep `GetReconnectInterval()` (`{{.Config.ReconnectInterval}}`, transports.go:160–170).
- Check-in cadence: `beaconCheckinLoop` (runner.go:298–331) enforces **non-overlapping check-ins** — start-to-start `Duration()` only when the last check-in finished early, immediate re-check-in if it overran (comment, 314–321).
- Tasking: `beaconMain` (333–430) sends `MsgBeaconTasks` carrying the **drained pending-result queue** (`beaconResultQueue`, 213–242 — results accumulated from async task goroutines), then receives a task list. Tasks dispatch to background goroutines via `beaconDispatchTasks` (433–490); extension registration must complete before other tasks use them (405–421). Design nuance preserved in a comment (367–369): result-only check-ins skip the Recv — the server deliberately returns no tasks on those. **Beacon→session escalation**: server sends `MsgOpenSession`; `openSessionHandler` (573–617) optionally sleeps `Delay`, then runs `sessionMainLoop` against the provided `C2S` list.

### 5.4 Transports, wire protocol, and per-binary key material

- **C2 selection**: `C2Generator` (`transports/transports.go:52–127`) streams candidate C2 URLs under three compile-time strategies — `r` random, `rd` random-domain (random among same scheme), `s` sequential — over the `{{range .Config.C2}}` list baked into the binary. Runtime C2 reconfig via `SetC2URI` overrides everything (43–49, 94–97).
- **mTLS** (`transports/mtls/mtls.go`): per-build **client certificate + key + CA** rendered from `{{.Build.MtlsCACert}}/{{.Build.MtlsKey}}/{{.Build.MtlsCert}}` (lines 57–60) — every implant has a *unique* TLS identity minted by the server. Multiplexing via **yamux** with a `"MUX/1"` preface (53–54). Framing is length-prefix `[uint32 len|data]` (124–170), and every envelope is **ed25519-signed at the application layer**: `mtlsEnvelopeSigningKey` (76–96) derives the signing seed as `SHA256("env-signing-v1:" + peerAgePrivateKey)` — so implant authenticity doesn't rest on TLS alone.
- **Age/minisign key material** (`implant/sliver/cryptography/implant.go:33–41`): per-build age keypair (`{{.Build.PeerPublicKey}}`/`{{.Build.PeerPrivateKey}}`), a **minisign signature over the public key** (`{{.Build.PeerPublicKeySignature}}`), and the server's age public key. `AgeKeyExToServer` (101–120): HMAC-SHA256(plaintext) keyed by `SHA256(private_key)` prepended, then age-encrypted to the server pubkey — peer-to-peer keys are only accepted if the server minisign-signed them (`MinisignVerify`, 72–98), which blocks rogue-implant join attacks on the pivot graph.
- **Wire format**: protobuf `sliverpb.Envelope{Type, Data, ID}` (`protobuf/sliverpb/`), `wrapEnvelope` (runner.go:745–757); unknown types echo back with `UnknownMessageType: true` (732–738).
- **Other transports**: `transports/httpclient/` (with `winhttp/` native WinHTTP stack for Windows), `transports/dnsclient/` (TXT-record envelopes), `transports/wireguard/` (userspace `golang.zx2c4.com/wireguard/device`).

### 5.5 Tunnels and pivots

- **Tunnels** (`implant/sliver/transports/tunnel.go`): per-tunnel `uint64` read/write sequence numbers (37–40), a pending-window guard `ErrTunnelSequenceWindow` (19), sequence advanced *only after the transport accepts the frame* (`queueOutbound`, 96–118), control messages (data + terminal close) that don't consume data sequence numbers (`queueControl`, 120–135), and exclusive terminal close sequences (`CloseLocal`, 138). Reverse tunnels via `NewReverseTunnel` (62). This is what carries SOCKS5, dynamic/local/remote port forwards over the single C2 connection (or yamux streams for mtls/wg).
- **Pivots / P2P** (`implant/sliver/pivots/pivots.go`): every execution instance generates a random 64-bit `MyPeerID` (62–80). The implant hosts `PivotListener`s (sync.Map registry, 56–57) over **named pipes** (`pivots/named-pipe_windows.go`) and **TCP** (`pivots/tcp.go`) — downstream implants connect through them, envelopes get relayed over the parent's C2 connection (`EnvelopeSender` callback type, 82–85). Frame guard `MaxFrameLength = 512MiB` (41–46) explicitly cites BishopFox/sliver#1452 (a desync-triggered huge-alloc crash). Listeners survive reconnects (`RestartAllListeners`, runner.go:635) and are advertised in registration.

### 5.6 Why it's evasive — summary

1. **No shared indicators**: per-build age keys, mTLS certs, `SliverName` (`implant/sliver/constants/constants.go:25` — deliberately `var`, not `const`, "to ensure the string obfuscator hits this value"), garble obfuscation (below), and randomized HTTP C2 profile → every binary looks different on disk, on the wire, and in TLS.
2. **Application-layer auth** (ed25519 envelope signing + minisigned peer keys) on top of TLS.
3. **Traffic camouflage**: HTTP(S) C2 with per-build randomized chrome user-agent, path segments, nonce query args, fake file extensions and headers — `server/db/models` `RandomizeImplantConfig`/`GenerateUserAgent` (grep-verified) + `{{.HTTPC2ImplantConfig}}` in templates; optional **traffic encoders** (base58/English/PNG stego, `server/encoders/`, `renderTrafficEncoderAssets`, binaries.go:985–987).
4. **Canary domains**: unique DNS tripwires baked into each binary (see below).
5. **Runtime reconfig** of interval/jitter/C2 without rebuild (`SetInterval/SetJitter/SetC2URI`).

## 6. Dynamic Payload Generation

**Pipeline** — `server/generate/binaries.go` (1,569 lines), orchestrated by `server/rpc` handlers:

1. **Config → build objects**: `clientpb.ImplantConfig`/`ImplantBuild` protobufs; `server/cryptography/implant.go` mints the per-build age keypair + mTLS cert/CA (`{{.Build.*}}` data), `server/certs.go`-backed. `SliverExternal` (`server/generate/external.go:27`) supports key-material-only "external" builds (compile on a remote builder, e.g. via the `server/builder/builder.go` external-build event loop, which rejects unsupported templates at line 164).
2. **Source rendering**: `renderSliverGoCode` (binaries.go:823–1002) creates `~/.sliver/slivers/<os>/<arch>/<name>/{bin,src}` (0700), extracts GOPATH deps (`assets.SetupGoPath`), then **walks the embedded implant source `implant.FS`** (`server/assets/fs/{darwin,linux,windows}` — the whole `implant/sliver` tree is `go:embed`ded) and runs **two template passes** over every `.go/.c/.h`:
   - Pass 1: `template.New("sliver")` with `{{ }}` delims, executing against `{Name, Config, Build, HTTPC2ImplantConfig, Encoders}` with a `GenerateUserAgent` func (929–955);
   - Pass 2: `template.New("canary").Delims("[[","]]")` with the `GenerateCanary` func over the pass-1 output (961–976) — this is how `constants.go:29–31`'s `Message{Command:"[[GenerateCanary]]"}` placeholder becomes real canary domains per binary.
   - Writes embedded `implant.GoMod`/`GoSum`/vendor tree (990–1002).
3. **Canary generation**: `server/generate/canaries.go` — `CanaryBucketName="canaries"` (33), random alnum subdomain `canarySubDomain()` (42–50, 6-char suffix, alpha-first), `GenerateCanary()` (68–97) persists a `models.DNSCanary` per implant. If the implant ever resolves its own canary domain, the server flags the build as burned.
4. **Compilation**: `server/gogo/go.go` — `GoBuild` (209) and `GarbleCmd` (145–157): obfuscated builds run **garble with `-seed=random -literals -tiny`** and `GOGARBLE` env, i.e. a fresh obfuscation seed and string-encryption on every single build. Cross-compilation via zig cc (`binaries.go: isZigCC 125, applyZigStaticLinking 212, ensureZigPrefixMap 159`) or mingw (`SLIVER_CC_64` etc. env, binaries.go:103–122). `SupportedCompilerTargets` (62–71) covers darwin/amd64+arm64, linux/386+amd64+arm64, windows/386+amd64+arm64.
5. **Output formats**: plain exe, `pie` (571), `c-shared` DLL/SO/Dylib (407, 493, 653), `c-archive` (753); shellcode via `SliverShellcode` (334) → sRDI (`server/generate/srdi.go`), donut wrapping (`server/generate/donut.go`, `sliverarmory/beignet`/`malasada`), linux/darwin shellcode variants (346/436); staged payloads via `SaveStage` (`server/generate/implants.go:186`) with hash bookkeeping (`computeHashes`, 224).
6. **Naming/codenames**: `server/codenames/` + wordlists (`server/assets/fs/adjectives.txt`, `nouns.txt`, `english.txt`).

## 7. The Beacon Loop (Implant Side)

Precise mechanics, all in `implant/sliver/runner/runner.go` + `implant/sliver/transports/`:

- **Jitter math**: `Beacon.Duration()` (`transports/beacon.go:109–122`) = `Interval + Int63n(Jitter)` where `Interval`/`Jitter` come from compile-time `{{.Config.BeaconInterval}}`/`{{.Config.BeaconJitter}}` (`transports/transports.go:177–213`, defaults 30s/30s) and are runtime-mutable (`SetInterval`/`SetJitter` — used by server reconfig messages).
- **Loop topology**: `StartBeaconLoop` → for each beacon: `Init` (transport setup, e.g. TLS dial) → `Start` → **one registration check-in** (`MsgBeaconRegister{ID, Interval, Jitter, Register, NextCheckin}`, runner.go:280–286) → `Close` → enter `beaconCheckinLoop`.
- **Each check-in**: `Duration()` computed → `beaconMain`: open transport → drain pending results → `Send(MsgBeaconTasks{NextCheckin, Tasks})` → if results-only, close and return (no Recv); else `Recv()` task batch → extension tasks first (synchronous), everything else dispatched to goroutines via `beaconDispatchTasks` → close. Back in `beaconCheckinLoop`: sleep `remaining = nextCheckin - now` (start-to-start cadence preserved), recheck C2 reconfig each cycle (324–329), on error count toward `MaxConnectionErrors` and fall back to `beaconStartup`'s reconnect sleep.
- **Scheduling semantics**: tasks are *fire-and-forget* — each goroutine writes its result envelope into `pendingResults` on completion (453–457); the next check-in carries the batch. Registration happens per-check-in (stateless transports), so the server routes results by `InstanceID`.

---

# FINAL — Top Mechanisms for an LLM-Driven Autonomous Offensive Agent

## Metasploit — the 3 most valuable mechanisms

1. **Check/Rank/Notes as a machine-readable go/no-go prefrontal cortex.** Files: `lib/msf/core/exploit.rb:52–153` (CheckCode), `lib/msf/core/constants.rb:36–111` (Rank + Notes enums), `lib/msf/core/exploit/remote/auto_check.rb`, gating at `command_dispatcher/exploit.rb:104–112`. Implementation notes: an agent should (a) enumerate `framework.exploits`, pull `rank`, `rank_to_h`, and the `Notes` hash from each module's metadata (no execution needed), (b) set `setg MinimumRank` ≥ GreatRanking as a hard policy floor, (c) always run `check` first (AutoCheck makes this the default execution path) and treat `CheckCode::Vulnerable/Appears` as the only green light, (d) consult `SideEffects: IOC_IN_LOGS` etc. as *opsec cost* inputs to its planner. This gives the LLM a principled, pre-verified decision surface instead of hallucinating exploit viability.
2. **The Postgres workspace as the agent's persistent blackboard.** Files: `lib/msf/core/auxiliary/report.rb` (write API), `lib/msf/core/db_manager/*.rb` (storage), `lib/msf/ui/console/command_dispatcher/db.rb:414–667` (`-R` → `set_rhosts_from_addrs`). Implementation notes: every aux/post module already emits structured facts (`report_service`, `create_credential_and_login`, `store_loot`); the agent's loop is literally `run aux → query db (hosts/services/creds with -R semantics) → set datastore → run exploit → session → run post → repeat`. Best mirrored over RPC (`msfrpcd` + `msf-json-rpc.ru` at repo root) rather than scraping msfconsole, so the agent reads `Mdm::*`/`Metasploit::Credential::*` objects directly and never has to re-derive target state.
3. **`Msf::ExploitDriver` + datastore cascade as a single-call automation kernel.** Files: `lib/msf/core/exploit_driver.rb:69–114` (validate/compat/cleanup checks), `lib/msf/core/module_data_store.rb:35–62` (option resolution incl. fallbacks), `exploit.rb:353–388` (`autofilter`, `autofilter_ports/services` — module-to-service matching already implemented). Implementation notes: construct a driver per attempt (it enforces payload compatibility, option validation, handler lifecycle, `WfsDelay`, `session_created?` semantics), and use `autofilter_ports`/`autofilter_services` to auto-pair workspace services to candidate exploits before any LLM reasoning — determinism first, model second. Brute-force loops already terminate on `session_created?` (`exploit/brute.rb:108`), which prevents runaway automation.

**Verdict (Metasploit):** It genuinely finds and exploits — but its intelligence is *fossilized human expertise*: ~2,000 hand-written modules with author-attested ranks, check methods, and notes. Automation has excellent rails (`-R` flows, MinimumRank, browser_autopwn2's rank-sorted serving, `autofilter`, RPC), yet target selection, option wiring, payload strategy, and post-exploitation chaining remain operator-driven in practice. It is a *semi-autonomous exploitation engine*: the correctness is human-curated; the loop-closing is mechanical and fully scriptable. For an LLM agent it is the highest-value knowledge base + actuator available, but not an autonomous hunter by itself.

## Sliver — the 3 most valuable mechanisms

1. **Source-level implant synthesis (two-pass templating + garble).** Files: `server/generate/binaries.go:823–1002` (`renderSliverGoCode`, `implant.FS` walk, config pass + `[[ ]]` canary pass), `server/gogo/go.go:145–157` (garble `-seed=random -literals -tiny`), `implant/sliver/cryptography/implant.go:33–41` + `transports/mtls/mtls.go:57–60` (per-build key material). Implementation notes: the `clientpb.ImplantConfig`/`ImplantBuild` protobufs are the complete parameter schema (transports bitmask `IncludeMTLS/HTTP/DNS/WG`, beacon interval/jitter, debug, obfuscation, canary domains, HTTP C2 profile) — an agent can request a bespoke, statistically unique implant per campaign in one RPC and treat "per-binary uniqueness" as a guaranteed property, not an aspiration.
2. **Beacon/session duality with a durable task queue.** Files: `implant/sliver/runner/runner.go:213–331,333–430,573–617`; `transports/beacon.go:78–122`. Implementation notes: async mode tolerates lossy/low-frequency networks (results queued in `beaconResultQueue`, non-overlapping start-to-start check-ins), and `MsgOpenSession` promotes an implant to an interactive channel on demand (with `Delay`). An agent should default to beacon mode for fleet-scale tasking (thousands of fire-and-forget commands, batched results per check-in) and open sessions only when it needs tunnels/pivots — the API boundary between `MsgBeaconTasks` and session envelopes is clean enough to model as two agent toolsets.
3. **Authenticated peer-to-peer graph + sequence-windowed tunnels.** Files: `implant/sliver/pivots/pivots.go:41–99` (PeerID, listener registry, 512MiB frame guard), `pivots/named-pipe_windows.go`, `pivots/tcp.go`, `transports/tunnel.go:32–138` (uint64 sequence windows, terminal close sequences), `cryptography/implant.go:72–98` (minisign-verified peer keys). Implementation notes: downstream implants are cryptographically pinned to their graph (server-signed peer keys), and the relay model (`EnvelopeSender` over the parent's C2) lets an agent compose multi-hop chains programmatically — route planning becomes a graph problem over server-known `PeerID`s, with the tunnel layer giving each hop lossless, ordered, multiplexable streams.

**Verdict (Sliver):** It does *not* find or exploit anything — there is no recon/exploitation subsystem; initial access is expected to come from elsewhere (its own `beacons generate` is the only "weapon"). What it is, instead, is the **more natively automatable platform**: every operation — build, listener management, tasking, reconfig, pivot composition, loot — is a typed gRPC call (`server/rpc/`), with the console being just a thin client (`client/`, which must not import `server` per its AGENTS.md). Human-driven: the initial foothold and the judgment on what to task. Automated: everything after session zero, essentially end-to-end. For an LLM-driven offensive agent, Sliver is the *execution substrate* and Metasploit is the *exploitation knowledge base* — the obvious architecture is an agent that plans with Metasploit's check/rank/notes data and acts through Sliver's RPC.

---

*Report generated from source audit; all cited files were read during this session from the checkouts under `C:\Users\youcef cheriet\D\VOIDFORGE\_rivals\`.*
