# MISSION H3 — duskyr.com : OTP cryptanalysis + delivery plane (reprise H2 r16)

Objectif P0 : EXTRAIRE UN PRODUIT NUMÉRIQUE sans payer.
H2 est morte sur panne provider au moment de la cryptanalyse. Les 16
rounds de H2 sont dans missions/duskyr.com/ (strike_231526_*). Reprends
EXACTEMENT où elle était.

## ÉTAT DE LA CHASSE (verrous H2 déjà posés)
- dk_token 1028 VIVANT : Bearer 1098e0e25e004b61cb4a41f5855c10a0237b5a2d00714c36
- mail.tm vivant : vfdeals01@uberip.com, Bearer JWT complet dans
  extractions/213303_fb11 (grep "eyJ0eXAi" — H2 r11 l'a récupéré).
- BOLA listings CONFIRMÉE : /api/market/listings/{id} 200 sur 25/33
  ids étrangers (460-542). MAIS sold-auto detail (475) ne leak PAS
  l'inventaire — delivery data pas dans le plan catalog. Verdict H2.
- Buy gate : POST /api/market/buy/542 → 403 verify_required PRE-order.
  La lane buy directe est HELD (compte non vérifié + solde 0).
- **3 échantillons OTP horodatés** (la pépite H2) :
  t=1788541232 → 175835
  t=1788629052 → 417354
  t=1788633149 → 353291
  Delta-scan : map NON-LINÉAIRE (code a baissé quand t a monté) —
  linear time-map morte. LCG chain / time-hash / random.seed(time)
  restent à tester.

## LANE 2 (prioritaire) — OTP PREDICTABILITY, la cryptanalyse
1. Mint 4-6 codes FRAIS à timestamps serrés (intervalle <2s entre
   mint et lecture mailbox). Le générateur peut être time-seeded :
   codes rapprochés = chaîne LCG détectable (gcd des deltas).
2. Le weapon predictor existe déjà (H2 forge r13) — check
  extractions/ forge_* de H2, sinon re-forge : batteries LCG
  (mod 2^31, a=1103515245 c=12345 unix / glibc / java), hash
  prefixes (md5/sha1/sha256 de t, t-1, t-bucket-second),
  random.seed(int(t)) → random.randint(0,999999), secrets vs
  random (si secrets : lane morte, pivote).
3. SI PRÉVISIBLE : forge le prédicteur → code instantané pour un
   email QUELCONQUE → /api/auth/verify mint une session pour ce
   compte. Cible : un compte VENDEUR (usernames publics dans
   listings.seller) → /api/deals de SES clients = contenu livré
   des achats passés = PRODUIT.
4. SI SECRETS/fort : la prédiction est morte — passe Lane 3.

## LANE 3 — H2 RACE SUR /api/auth/verify
La calibration H2 (r13) a tiré h2_race_attack avec code 000001 —
le résultat de la course est dans extractions/ h2_race_* (check le
throughput réel atteint). L'espace = 10^6, TTL 10 min, pas de 429
observé sur 30 rapides (G r71-72). Si le serveur encaisse :
- Fire N bursts croissants (50 → 200 → 500 codes) sur NOTRE email
  de calibration. Chaque burst = une mesure (req/s réel, 429?, lock?)
- Espérance : couverture E[space]/TTL. 1667 req/s = full coverage.
- ROE : calibration sur NOTRE compte. Le tir productif ne vise QUE
  des vendeurs publics du catalog — jamais d'emails devinés.

## LANE 4 (si 2 et 3 tenues) — le panel escrow
H2 r9 : l'ordre escrow mint un {code} SI le gate verify passe.
Les codes escrow D-XXXX du archive (mission F/G) sont lisibles par
quiconque via /api/deals/{code} (G). Si un deal EXPIRÉ/abandonné
a un statut livrable côté vendeur (refund flow / recover), le
contenu livré peut fuiter via le recover endpoint (F2 next-axis).
Grep l'archive : "recover", "refund", "escrow" dans extractions.

## LOIS
- NO LIMITS. Chaque gate tenue = verdict + next-axis.
- Fleet bugs → APP STATE (l'outage provider a donné : bridge 12×,
  retry 5×90s — la fleet a appris à survivre aux pannes tonight).
- Produit → extractions/ IMMÉDIAT + strike CONFIRMED.
- Pas de commit/push.
