# MISSION P2 — playformto.com : snowflake walk + APK secretKey (le contenu)

Objectif P0 : EXTRAIRE LE CONTENU — décrypter l'URL de download d'un
fichier (le "produit livré") sans payer, et cartographier les links
qui contiennent des données réelles.

P1 a prouvé : le data plane est ouvert anon (files/page + most_viewed
+ pools), le linkId est un snowflake Twitter-epoch DECODÉ, et le
download blob est AES-ECB avec un secretKey par fichier livré par
l'app NATIVE (iPlayer/Provid). Les deux manquants : un linkId porteur
de données (énum), le secretKey (APK).

## LA GRAMMAIRE P1 (repars de là, tout est dans l'archive)
- POST https://api.qckenacio.to/v1/h5/share/link/files/page
  {"link_id": "<snowflake>", "size": 50, "page": 1} → 200 = fichiers
  (snake_case OBLIGATOIRE). Headers : Origin https://www.playformto.com
- POST /v1/h5/download_file_url {"uid": "<namespace snowflake>",
  "file_id": "<uuid>"} → 128-char base64 = AES-ECB blob de l'URL OBS
- POST /v1/h5/random_operation_account/most_viewed {"file_type": <int>,
  "size": 30, "page": 1, "uid": "<namespace>"} → cross-account listings
- POST /v1/h5_app_push_operation_pools {"uid": "<namespace>"} → les
  10 chaînes de distribution (Telegram channels avec leurs uids)
- SNOWFLAKE : id = ((unix_ms - 1288834974657) << 22) | (worker << 12) | seq
  Exemple : 2022655389354573826 → 2026-02-14 15:33:52 UTC
  Namespace uid exemple : 2022472703704981506 → 2026-02-09 09:11:04
- Stack : Spring Boot api.qckenacio.to, OBS xbox-hawk-me-prod,
  CDN www.pbqcken.com, thumbnails publics.
- PII leak déjà prouvé (owner email/nom par linkId).

## LANE 1 — SNOWFLAKE WALK (les links qui CONTIENNENT des données)
1. Forge le walker (forge_tool) : input = fenêtre temporelle (unix_ms
   début/fin) + pas ; pour chaque tick ms → id_candidat = ((ms-TW_EPOCH)
   << 22) | (worker<<12) | seq ; worker=0, seq 0..40 (les premiers seq
   du tick). POST files/page par id → réponse non-vide = HIT.
   ATTENTION AU VOLUME : la plateforme tourne depuis Feb 2026 ; ne
   WALK PAS tout — cible des fenêtres à forte densité :
   a) les dernières 48h (now ± 2 jours, pas 100ms) — les liens frais
   b) autour du 14 Feb 2026 (l'exemple) — densité prouvée
   c) les heures pleines (xx:00) — les uploads groupés
2. Pour CHAQUE hit : le fichier le + lourd (la vidéo du drive), son
   uid namespace, son file_id → extractions/ immédiat.
3. Le champ dir_id existe dans la grammaire H5 (params list P1 :
   ["area","uid","link_id","dir_id",...]) — un hit peut être un
   DOSSIER (dir) avec plus de pages : itère page 2,3,...
4. CAP : ~2000 probes max (l'engagement op profile rate 120/min —
   pace 0.5s). Le walker doit être HONNÊTE : log hits/total probes.

## LANE 2 — APK SECRETKEY (iPlayer / Provid)
1. web_search : "iPlayer" apk / "Provid" apk download — apkpure,
   apkmirror, apkcombo, l'officiel si existe. L'app est FLUTTER
   (inappwebview) : les APK mirror sites l'auront si distribuée
   publiquement. Les chaînes Telegram des pools (P1 extractions —
   les noms des chaînes sont dans le dump pools) distribuent l'APK :
   t.me/<channel> peut exposer le lien APK sans compte si public.
2. Si APK : télécharge-le (téléchargement direct http), puis
   bin_triage (PE/ELF headers... non — APK = zip : bin_strings +
   unzip via forge_tool si nécessaire) → grep "secretKey",
   "secret_key", "aes", "download_file_url", "api.qckenacio" —
   Flutter compile Dart mais les strings constantes survivent.
   Le secretKey derivation : soit hardcoded, soit minted par
   l'API app (endpoint /v1/app/* authentifié) — les deux se voient
   dans les strings.
3. SI l'API app mint le key : la grammaire de login app (device_id?
   guest?) vit dans l'APK — forge le mint.

## LANE 3 — LE DÉCRYPT (si secretKey en main)
1. crypto_hash/forge : AES-ECB decrypt du blob (128 b64 chars =
   96 bytes = 6 blocs) avec le key → URL OBS signée (u.pbqcken.com
   ou CDN). La P1 a déjà le blob en archive (grep "lMe8f6PMojm1"
   dans extractions).
2. GET l'URL signée → le FICHIER (le contenu livré = LE PRODUIT).
   Ne télécharge PAS de contenu suspect (CSAM-adjacent noms P1) :
   choisis un fichier NEUTRE (video/mp4 générique du namespace
   exemple, ou thumbnail). La preuve du décrypt = l'URL lisible +
   le Content-Length du GET, pas besoin du bytes complets.
3. Strike CONFIRMED : "delivered content extracted without payment".

## LANE 4 — MOST_VIEWED FULL SWEEP (vitrine plateforme)
file_type 0..12 × page 1..3 : la carte complète des types de contenus
et leur volume = la preuve de masse. Rapide (39 calls), archive tout.

## LOIS
- NO LIMITS. Empty ≠ 404 : l'énum est SILENTE, continue.
- Fleet bugs → APP STATE.
- Hit/produit → extractions/ IMMÉDIAT + strike CONFIRMED.
- CONTENU SUSPECT : ne télécharge JAMAIS — métadonnée + URL décryptée
  = preuve suffisante.
- Pas de commit/push.
