# LAB ACCEPTANCE REPORT — auth_state_engine v1.0.0

*Cible : `http://127.0.0.1:9443` — run du 2026-08-31 01:43:21.*

*Chaque verdict CAUGHT/MISSED est décidé par le comportement HTTP observé — rien n'est affirmé sans PoC rejouable.*


**Score : 7/7 défauts détectés.**


| Défaut | Verdict | Moniteur | Finding |
|---|---|---|---|
| D1 | CAUGHT ✅ | BindingMonitor.run_pkce | VF-AUTH-001 |
| D2 | CAUGHT ✅ | NoSkipMonitor + BindingMonitor (state) | VF-AUTH-002 |
| D3 | CAUGHT ✅ | NoReplayMonitor | VF-AUTH-003 |
| D4 | CAUGHT ✅ | redirect_validation probe | VF-AUTH-004 |
| D5 | CAUGHT ✅ | EntropyMonitor | VF-AUTH-005 |
| D6 | CAUGHT ✅ | MixupMonitor + BindingMonitor.run_audience | VF-AUTH-006 |
| D3-race | CAUGHT ✅ | race harness (executed) | VF-AUTH-008 |

## Détail par défaut

### D1 — CAUGHT ✅

- **Moniteur** : BindingMonitor.run_pkce
- **Finding** : VF-AUTH-001 (severity: high)
- **Claim** : code redeemable with code_verifier ABSENT although code_challenge was sent at authorize
- **authorize** : `{"request": "GET /authA/authorize?login=victime&redirect_uri=https%3A%2F%2Fapp.example%2Fcb&state=s-v1&code_challenge=DIlPZak5JkgwEzYG90Xj4zNa2-jMXtIhPmgMiw0CCIw&code_challenge_method=S256", "status": 302, "location": "https://app.example/cb?code=1f5ed647&state=s-v1", "body": {}}`
- **exchange** : `{"request": "POST /token?code=1f5ed647", "status": 200, "location": null, "body": {"access_token": "af9140a7207e29226b5a0fbd7eff350fc51591c59f9a3d69bbfb0e31e56b8a7f", "token_type": "Bearer", "iss": "https://issuer-a.example"}}`
- **Claim** : code redeemable with code_verifier ABSENT although code_challenge was sent at authorize

### D2 — CAUGHT ✅

- **Moniteur** : NoSkipMonitor + BindingMonitor (state)
- **Finding** : VF-AUTH-002 (severity: critical)
- **Claim** : server issues code and echoes an attacker-chosen state without ANY session binding; machine has no state_verify transition (no-skip P1 gap)
- **authorize** : `{"request": "GET /authA/authorize?login=victime&redirect_uri=https%3A%2F%2Fapp.example%2Fcb&state=ATTACKER-STATE-NEVER-MINTED-9f27", "status": 302, "location": "https://app.example/cb?code=ea7ac533&state=ATTACKER-STATE-NEVER-MINTED-9f27", "body": {}}`
- **state_echoed** : `"ATTACKER-STATE-NEVER-MINTED-9f27"`
- **unbound_state_accepted** : `true`
- **Claim** : server issues code and echoes an attacker-chosen state without ANY session binding; machine has no state_verify transition (no-skip P1 gap)

### D3 — CAUGHT ✅

- **Moniteur** : NoReplayMonitor
- **Finding** : VF-AUTH-003 (severity: high)
- **Claim** : same code exchanged twice → two distinct tokens
- **exchange_1** : `200`
- **exchange_2** : `200`
- **distinct_tokens** : `true`
- **token1_prefix** : `"ae95351e1b1b6f4c"`
- **token2_prefix** : `"63a1c0efd55f7a66"`
- **Claim** : same code exchanged twice → two distinct tokens

### D4 — CAUGHT ✅

- **Moniteur** : redirect_validation probe
- **Finding** : VF-AUTH-004 (severity: high)
- **Claim** : prefix validation accepted evil sibling domain — code + state leak to attacker-controlled origin
- **authorize** : `{"request": "GET /authA/authorize?login=victime&redirect_uri=https%3A%2F%2Fapp.example%2Fcb.evil.example&state=s-v4", "status": 302, "location": "https://app.example/cb.evil.example?code=5b23fb33&state=s-v4", "body": {}}`
- **location** : `"https://app.example/cb.evil.example?code=5b23fb33&state=s-v4"`
- **leaked_code_prefix** : `"5b23fb33"`
- **Claim** : prefix validation accepted evil sibling domain — code + state leak to attacker-controlled origin

### D5 — CAUGHT ✅

- **Moniteur** : EntropyMonitor
- **Finding** : VF-AUTH-005 (severity: high)
- **Claim** : H = L·log2|C| = 32.0 bits (< 160) on 100 live codes — pool Shannon 31.9 bits/code
- **entropy_report** : `{"label": "authorization code", "charset": "hex", "length": 8, "nominal_bits": 32.0, "empirical_bits_sample": 1.9, "min_bits": 160.0, "verdict": "FAIL", "method": "H = L·log2|C|", "empirical_pool_bits_per_code": 31.9}`
- **distinct_of_sample** : `"100/100"`
- **sample_codes** : `["dfe7fdd7", "551a9d80", "7b50b502", "3cbf4731", "a50bde83"]`
- **Claim** : H = L·log2|C| = 32.0 bits (< 160) on 100 live codes — pool Shannon 31.9 bits/code

### D6 — CAUGHT ✅

- **Moniteur** : MixupMonitor + BindingMonitor.run_audience
- **Finding** : VF-AUTH-006 (severity: critical)
- **Claim** : token issued by issuer-B accepted by the resource server of issuer-A (no iss/aud enforcement — mix-up surface)
- **rs_exchange** : `{"request": "GET /api/user", "status": 200, "location": null, "body": {"sub": "victime", "iss": "https://issuer-b.example", "note": "issued by whoever — nobody checks"}}`
- **token_iss** : `"https://issuer-b.example"`
- **Claim** : token issued by issuer-B accepted by the resource server of issuer-A (no iss/aud enforcement — mix-up surface)

### D3-race — CAUGHT ✅

- **Moniteur** : race harness (executed)
- **Finding** : VF-AUTH-008 (severity: high)
- **Claim** : concurrent exchanges of ONE code all succeeded
- **race** : `{"mode": "executed_threads", "threads": 16, "success_2xx": 16, "distinct_tokens": 16, "wall_ms": 535.3, "model": "P = 1−(1−p)^k per attempt (dossier §6.5)", "interpretation": "single-use guard ABSENT — open door, not a window", "bodies_sample": [{"access_token": "88d21a473a0dc488596fb8ce6903a59744f62bb59a8c0a2053967c19ef622163", "token_type": "Bearer", "iss": "https://issuer-a.example"}, {"access_token": "424a50a594cf73b623776475c6eaf6b17fe0463f54bc421a2399f4bf2e4338b8", "token_type": "Bearer", "iss": "https://issuer-a.example"}]}`
- **Claim** : concurrent exchanges of ONE code all succeeded

## Machine inférée (traces live)

- méthode : prefix_tree (live traces)
- états : 6 — arêtes : 11
- alphabet : ['authorize', 'code_consume', 'token_present']

## Race harness (exécuté)

```json
{
  "mode": "executed_threads",
  "threads": 16,
  "success_2xx": 16,
  "distinct_tokens": 16,
  "wall_ms": 535.3,
  "model": "P = 1\u2212(1\u2212p)^k per attempt (dossier \u00a76.5)",
  "interpretation": "single-use guard ABSENT \u2014 open door, not a window",
  "bodies_sample": [
    {
      "access_token": "88d21a473a0dc488596fb8ce6903a59744f62bb59a8c0a2053967c19ef622163",
      "token_type": "Bearer",
      "iss": "https://issuer-a.example"
    },
    {
      "access_token": "424a50a594cf73b623776475c6eaf6b17fe0463f54bc421a2399f4bf2e4338b8",
      "token_type": "Bearer",
      "iss": "https://issuer-a.example"
    }
  ]
}
```

## verdict() — contrat JSON

```json
{
  "tool": "auth_state_engine",
  "version": "1.0.0",
  "target": {
    "url": "http://127.0.0.1:9443",
    "flow": "oauth2_code",
    "mode": "lab_acceptance"
  },
  "exploitable": true,
  "summary": "8 primary finding(s) (+4 corroboration) — 12 reproduced live",
  "machine": {
    "inference": "prefix_tree (live traces)",
    "states": 6,
    "edges": 11,
    "alphabet": [
      "authorize",
      "code_consume",
      "token_present"
    ]
  },
  "findings": [
    {
      "id": "VF-AUTH-001",
      "severity": "high",
      "title": "Grant accepted without its proof of possession / outside its audience",
      "template": "binding_preservation",
      "flaw": "D1",
      "reproduced": true,
      "evidence": {
        "claim": "code redeemable with code_verifier ABSENT although code_challenge was sent at authorize",
        "authorize": {
          "request": "GET /authA/authorize?login=victime&redirect_uri=https%3A%2F%2Fapp.example%2Fcb&state=s-v1&code_challenge=DIlPZak5JkgwEzYG90Xj4zNa2-jMXtIhPmgMiw0CCIw&code_challenge_method=S256",
          "status": 302,
          "location": "https://app.example/cb?code=1f5ed647&state=s-v1",
          "body": {}
        },
        "exchange": {
          "request": "POST /token?code=1f5ed647",
          "status": 200,
          "location": null,
          "body": {
            "access_token": "af9140a7207e29226b5a0fbd7eff350fc51591c59f9a3d69bbfb0e31e56b8a7f",
            "token_type": "Bearer",
            "iss": "https://issuer-a.example"
          }
        },
        "token_issued": true
      },
      "dedup": {
        "role": "primary"
      }
    },
    {
      "id": "VF-AUTH-002",
      "severity": "critical",
      "title": "Protected transition reachable without required proof (step-skip)",
      "template": "no_skip",
      "flaw": "D2",
      "reproduced": true,
      "evidence": {
        "claim": "server issues code and echoes an attacker-chosen state without ANY session binding; machine has no state_verify transition (no-skip P1 gap)",
        "authorize": {
          "request": "GET /authA/authorize?login=victime&redirect_uri=https%3A%2F%2Fapp.example%2Fcb&state=ATTACKER-STATE-NEVER-MINTED-9f27",
          "status": 302,
          "location": "https://app.example/cb?code=ea7ac533&state=ATTACKER-STATE-NEVER-MINTED-9f27",
          "body": {}
        },
        "state_echoed": "ATTACKER-STATE-NEVER-MINTED-9f27",
        "unbound_state_accepted": true
      },
      "dedup": {
        "role": "primary"
      }
    },
    {
      "id": "VF-AUTH-003",
      "severity": "high",
      "title": "Single-use token consumed more than once (non-atomic guard)",
      "template": "no_replay",
      "flaw": "D3",
      "reproduced": true,
      "evidence": {
        "claim": "same code exchanged twice → two distinct tokens",
        "exchange_1": 200,
        "exchange_2": 200,
        "distinct_tokens": true,
        "token1_prefix": "ae95351e1b1b6f4c",
        "token2_prefix": "63a1c0efd55f7a66"
      },
      "dedup": {
        "role": "primary"
      }
    },
    {
      "id": "VF-AUTH-004",
      "severity": "high",
      "title": "redirect_uri validated by prefix — code leakage path",
      "template": "redirect_validation",
      "flaw": "D4",
      "reproduced": true,
      "evidence": {
        "claim": "prefix validation accepted evil sibling domain — code + state leak to attacker-controlled origin",
        "authorize": {
          "request": "GET /authA/authorize?login=victime&redirect_uri=https%3A%2F%2Fapp.example%2Fcb.evil.example&state=s-v4",
          "status": 302,
          "location": "https://app.example/cb.evil.example?code=5b23fb33&state=s-v4",
          "body": {}
        },
        "leaked_code_prefix": "5b23fb33",
        "location": "https://app.example/cb.evil.example?code=5b23fb33&state=s-v4"
      },
      "dedup": {
        "role": "primary"
      }
    },
    {
      "id": "VF-AUTH-005",
      "severity": "high",
      "title": "Token below the entropy floor (H = L·log2|C| < min)",
      "template": "entropy_floor",
      "flaw": "D5",
      "reproduced": true,
      "evidence": {
        "claim": "H = L·log2|C| = 32.0 bits (< 160) on 100 live codes — pool Shannon 31.9 bits/code",
        "entropy_report": {
          "label": "authorization code",
          "charset": "hex",
          "length": 8,
          "nominal_bits": 32.0,
          "empirical_bits_sample": 1.9,
          "min_bits": 160.0,
          "verdict": "FAIL",
          "method": "H = L·log2|C|",
          "empirical_pool_bits_per_code": 31.9
        },
        "distinct_of_sample": "100/100",
        "sample_codes": [
          "dfe7fdd7",
          "551a9d80",
          "7b50b502",
          "3cbf4731",
          "a50bde83"
        ]
      },
      "dedup": {
        "role": "primary"
      }
    },
    {
      "id": "VF-AUTH-006",
      "severity": "critical",
      "title": "Token accepted outside its bound issuer (mix-up surface)",
      "template": "issuer_confinement",
      "flaw": "D6",
      "reproduced": true,
      "evidence": {
        "claim": "token issued by issuer-B accepted by the resource server of issuer-A (no iss/aud enforcement — mix-up surface)",
        "authorize_issuer_b": {
          "request": "GET /authB/authorize?login=victime&redirect_uri=https%3A%2F%2Fapp.example%2Fcb&state=s-v6",
          "status": 302,
          "location": "https://app.example/cb?code=458fdb10&state=s-v6",
          "body": {}
        },
        "token_iss": "https://issuer-b.example",
        "rs_exchange": {
          "request": "GET /api/user",
          "status": 200,
          "location": null,
          "body": {
            "sub": "victime",
            "iss": "https://issuer-b.example",
            "note": "issued by whoever — nobody checks"
          }
        },
        "rs_note": "issued by whoever — nobody checks"
      },
      "dedup": {
        "role": "primary"
      }
    },
    {
      "id": "VF-AUTH-007",
      "severity": "high",
      "title": "Grant accepted without its proof of possession / outside its audience",
      "template": "binding_preservation",
      "flaw": "D6",
      "reproduced": true,
      "evidence": {
        "claim": "binding preservation violated: τ.iss ∉ allowed(RS)",
        "token_iss": "https://issuer-b.example",
        "allowed": [
          "https://issuer-a.example"
        ],
        "poc": {
          "request": "GET /api/user",
          "status": 200,
          "location": null,
          "body": {
            "sub": "victime",
            "iss": "https://issuer-b.example",
            "note": "issued by whoever — nobody checks"
          }
        }
      },
      "dedup": {
        "role": "primary"
      }
    },
    {
      "id": "VF-AUTH-008",
      "severity": "high",
      "title": "Single-use token consumed more than once (non-atomic guard)",
      "template": "no_replay",
      "flaw": "D3-race",
      "reproduced": true,
      "evidence": {
        "claim": "concurrent exchanges of ONE code all succeeded",
        "race": {
          "mode": "executed_threads",
          "threads": 16,
          "success_2xx": 16,
          "distinct_tokens": 16,
          "wall_ms": 535.3,
          "model": "P = 1−(1−p)^k per attempt (dossier §6.5)",
          "interpretation": "single-use guard ABSENT — open door, not a window",
          "bodies_sample": [
            {
              "access_token": "88d21a473a0dc488596fb8ce6903a59744f62bb59a8c0a2053967c19ef622163",
              "token_type": "Bearer",
              "iss": "https://issuer-a.example"
            },
            {
              "access_token": "424a50a594cf73b623776475c6eaf6b17fe0463f54bc421a2399f4bf2e4338b8",
              "token_type": "Bearer",
              "iss": "https://issuer-a.example"
            }
          ]
        }
      },
      "dedup": {
        "role": "primary"
      }
    },
    {
      "id": "VF-AUTH-009",
      "severity": "critical",
      "title": "Protected transition reachable without required proof (step-skip)",
      "template": "no_skip",
      "property": "□(code_consume → ◇state_verify)",
      "trace": "d2-state-unbound",
      "evidence": {
        "gap": "machine-gap vs IDEAL_REQUIRED_EDGES: ['authorize'] --state_verify--> ? (ideal edge absent from observed machine)",
        "observed_sequence": [
          "authorize",
          "code_consume"
        ]
      },
      "flaw": "D2(monitor-pass)",
      "reproduced": true,
      "dedup": {
        "role": "corroboration",
        "of": "VF-AUTH-002"
      }
    },
    {
      "id": "VF-AUTH-010",
      "severity": "high",
      "title": "Grant accepted without its proof of possession / outside its audience",
      "template": "binding_preservation",
      "property": "□(grant(code) → ∃verifier: SHA256(verifier)=challenge ∧ code↔challenge bound)",
      "trace": "d1-pkce-binding",
      "evidence": {
        "verifier_sent": false,
        "note": "code redeemed with NO proof of possession",
        "poc": {
          "authorize": {
            "request": "GET /authA/authorize?login=victime&redirect_uri=https%3A%2F%2Fapp.example%2Fcb&state=s-v1&code_challenge=DIlPZak5JkgwEzYG90Xj4zNa2-jMXtIhPmgMiw0CCIw&code_challenge_method=S256",
            "status": 302,
            "location": "https://app.example/cb?code=1f5ed647&state=s-v1",
            "body": {}
          },
          "exchange": {
            "request": "POST /token?code=1f5ed647",
            "status": 200,
            "location": null,
            "body": {
              "access_token": "af9140a7207e29226b5a0fbd7eff350fc51591c59f9a3d69bbfb0e31e56b8a7f",
              "token_type": "Bearer",
              "iss": "https://issuer-a.example"
            }
          }
        }
      },
      "flaw": "D1(monitor-pass)",
      "reproduced": true,
      "dedup": {
        "role": "corroboration",
        "of": "VF-AUTH-001"
      }
    },
    {
      "id": "VF-AUTH-011",
      "severity": "high",
      "title": "Single-use token consumed more than once (non-atomic guard)",
      "template": "no_replay",
      "property": "□(consume(c) → X□¬consume(c))",
      "trace": "d3-code-replay",
      "evidence": {
        "event": "code_consume",
        "token_id": "1dd32c78",
        "successful_consumes": 2
      },
      "impact": "non-atomic single-use guard — race window (dossier §6.5: P = 1−(1−p)^k)",
      "flaw": "D3(monitor-pass)",
      "reproduced": true,
      "dedup": {
        "role": "corroboration",
        "of": "VF-AUTH-003"
      }
    },
    {
      "id": "VF-AUTH-012",
      "severity": "critical",
      "title": "Token accepted outside its bound issuer (mix-up surface)",
      "template": "issuer_confinement",
      "property": "□(token_use(u,τ) → τ.iss ∈ allowed(route))",
      "trace": "d6-mixup-audience",
      "evidence": {
        "route": "/api/user",
        "token_iss": "https://issuer-b.example",
        "allowed": [
          "https://issuer-a.example"
        ],
        "rs_note": "issued by whoever — nobody checks"
      },
      "verdict": "FOREIGN_ISSUER_TOKEN_ACCEPTED",
      "flaw": "D6(monitor-pass)",
      "reproduced": true,
      "dedup": {
        "role": "corroboration",
        "of": "VF-AUTH-006"
      }
    }
  ],
  "entropy": [
    {
      "label": "authorization code",
      "charset": "hex",
      "length": 8,
      "nominal_bits": 32.0,
      "empirical_bits_sample": 1.9,
      "min_bits": 160.0,
      "verdict": "FAIL",
      "method": "H = L·log2|C|",
      "empirical_pool_bits_per_code": 31.9
    }
  ],
  "race": {
    "mode": "executed_threads",
    "threads": 16,
    "success_2xx": 16,
    "distinct_tokens": 16,
    "wall_ms": 535.3,
    "model": "P = 1−(1−p)^k per attempt (dossier §6.5)",
    "interpretation": "single-use guard ABSENT — open door, not a window",
    "bodies_sample": [
      {
        "access_token": "88d21a473a0dc488596fb8ce6903a59744f62bb59a8c0a2053967c19ef622163",
        "token_type": "Bearer",
        "iss": "https://issuer-a.example"
      },
      {
        "access_token": "424a50a594cf73b623776475c6eaf6b17fe0463f54bc421a2399f4bf2e4338b8",
        "token_type": "Bearer",
        "iss": "https://issuer-a.example"
      }
    ]
  }
}
```

---
*Fin du rapport d'acceptance. Prochain palier : L* actif (AALpy) en v2 (à confirmer).*
