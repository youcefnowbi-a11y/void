# CAMPAGNE CP1 — playformto.com : DIFF doctrine + MCTS + swarm (preuve de la nouvelle ère)

Objectif P0 : PREUVE D'ARCHITECTURE + extraction profonde. Le terrain
(playformto) est déjà tombé (P1/P2 : data plane anon ouvert, APK
secretKey cracké, CDN sans auth). Cette campagne teste les NOUVEAUX
ORGANES sur terrain connu :

1. LE PLAN MCTS au round 0 — chaque phase reçoit son opening book.
2. LA DOCTRINE DIFF (grimoire_query domain=diff) — chasse les
   DISAGREEMENT SURFACES que P1/P2 n'ont pas testées :
   * Cache deception : authed page + suffix trick (GRM-DIFF-0105)
   * Cookie tossing / session fixation sur les sous-domaines
   * SSRF chains via download_file_url (le backend fetch-t-il ?)
   * Race conditions sur les compteurs most_viewed (limit-overrun)
   * Shadow APIs : /v1/app/* twins (api.qckenacio.to vs
     api.coaasljda.com — DEUX backends, testés comme twins ?)
   * Prototype pollution : JSON merges sur les endpoints open_data
3. LE SWARM : les chains parallèles (recon-fresh / diff-hunt / app-twin)
   avec fenêtres de contexte fraîches.
4. LE VERIFIER adversarial attaque NOTRE propre travail.

RÈGLES : terrain déjà mappé — NE REFAIS PAS la recon P1/P2 (bundles
minés, APK unpacké, grammar connue — tout est dans
missions/playformto.com/ et missions/www.playformto.com/). Frappe
directement les lanes DIFF ci-dessus. Chaque strike = preuve
archivée. Fleet bugs → APP STATE du rapport.
