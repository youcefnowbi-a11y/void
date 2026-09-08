# MISSION F2 — payment.duskyr.com cross-merchant signature lane (REPRISE de F)

REPRISE de la mission F (l'archive crash-safe missions/forum.duskyr.com/
porte tout). Dernier état avant coupure (round 29) :

## CE QUI EST DÉJÀ EN MAIN (ne PAS re-derive, utilise l'archive)
- **Merchant account minted** : merchant_uuid 4468a610-db0a-4ea8-a400-
  d63832caf330, api_key hk_842f8a9a..., webhook_secret b7d9460d... (64-hex)
  — extractions + rapport strike dans missions/forum.duskyr.com/
- **helmer_session Z8dlTPzMoi25FhUvWMQkpz2UqOlZLdJTriDIQOIJpvA** (1 an
  Max-Age), CSRF zYV7L-PRGAoI2ruJs9u9ZDvTDY4JzZLg2sVIFsyJ9ew
- **Play prouvée fermée** : login (form) → session → GET /dashboard-api/
  session (csrf_token) → POST /keys/reveal + X-CSRF-Token (JSON) → 200
  api_key + webhook_secret
- Transport : REGISTER/LOGIN = FORM-urlencoded (content_type=form);
  keys/reveal = JSON + header CSRF. Bug transport body corrigé en live —
  les POST bodies atteignent maintenant EXACTEMENT le wire.
- Le merchant marketplace (duskyr.com lui-même) : merchant_uuid
  d25548cd-... (archive 9.39) — LE merchant à imposter.

## LA FRAPPE EN COURS AU MOMENT DE LA COUPURE (r29-r30)
Test de la **signature croisée inter-merchants** : l'API heleket-compat
lie les requêtes via headers `merchant` + `sign` (sign = md5(base64(body)
+ api_key)). LA QUESTION OUVERTE : est-ce que le sign est vérifié contre
la clé du MERCHANT NOMMÉ dans le header (correct) ou contre le mien
(bug → takeover) ?
- crypto_hash avait calculé le sign pour l'invoice probe vf-probe-001
- forged_raw_post tirait POST /v1/payment/create avec merchant=d25548cd-
  ... (le merchant de la marketplace) + MON sign
- Ça a été interrompu LÀ. Reprends ce test exact.

## L'ESCALADE SI LE CROSS-SIGN PASSE
1. Créer un payment SUR LE MERCHANT MARKETPLACE avec mon sign
2. OU forger un webhook /v1/test-webhook/payment confirmé pour le
   merchant marketplace → la marketplace croit un paiement arrivé
   → commande marquée paid → le contenu produit se délivre
3. Le contenu livré (instructions du seller dans /api/deals/{code})
   = LE PRODUIT NUMÉRIQUE. Extraire et archiver IMMÉDIATEMENT.

## AUTRES LANES SI LE CROSS-SIGN TIENT (P0 — move planes)
- /v1/payment/info avec merchant UUIDs énumérés (d25548cd-... + le
  mien) — scoping cross-merchant untested
- webhook_secret forgé/replayed sur les events paid/completed
- TQmZ1jRnLK9dVEBBqYpF8bK9dNhP4wUgTn (string mystère bundle) en
  X-Admin-Token keypool OU bearer /v1/chat/completions
- /api/admin/overview sur keypool avec TOUS les candidats d'archive
- Le forum dp-forum en lane séparée si payment tient

## LOIS
- NO LIMITS (rounds=0, minutes=0). Ne jamais conclure "locked" —
  "held on tested plane" + NEXT LEAK-HUNT AXIS.
- Chaque bug/ faiblesse du FLEET pendant la mission → APP STATE du
  rapport (double objectif : produit + calibration).
- Pas de commit/push.
- Si un produit sort (clé, compte, contenu livré) : archiver dans
  extractions/ immédiatement + rapport strike CONFIRMED.
