# CAMPAGNE CP4 — ÉVALATION SYSTÈME : la preuve complète de l'architecture corrigée

## OBJECTIF (EVALUATION, P0)
Ce n'est PAS une mission de chasse — c'est la VALIDATION de l'architecture
premium 3-phases avec TOUS les fixes de la session. Le terrain
(playformto.com) est connu : 105 strikes en CP1/CP2, twins
api.qckenacio.to / api.coaasljda.com, H5 keys, snowflake linkId.

## CRITÈRES DE SUCCÈS (ce que la flotte doit PROUVER)
1. **PHASE A** : le plan est SCELLÉ dans le budget (l'alarme à 75% force
   l'écriture si le recon s'étend) — plan.md avec bloc ```json chains```.
2. **PHASE B** : PlannedSwarm exécute les chains EN PARALLÈLE — events
   taggés chain:<name> en simultané, chaque chain héritant du workspace
   missions/playformto.com/ (report_write/evidence_pack VIVANTS dans les
   chains — le bug CP2 est mort).
3. **PHASE C** : le verifier porte la READ-ONLY probe lane (pas un critique
   texte), attaque les verdicts des chains avec des re-tests réels, et
   verifier_report.md est SCELLÉ (l'extraction "agent" corrigée).
4. **Rapport final** : le claim verifier déterministe annote toute
   référence d'artefact sans correspondance — 0 claims non vérifiés.

## TERRAIN (intel CP1/CP2 — à réutiliser, pas à redécouvrir)
- Twins : api.qckenacio.to / api.coaasljda.com (un cerveau, deux corps)
- H5 : oB=WhdHpjpquhgpARKSPD1rGkIlY6T2cAWd (AES-CBC event keypair) —
  forged telemetry ACCEPTÉE en CP2
- most_viewed grammar : {uid, file_type:"FILE", os, language, size, index:[]}
  → 55KB PII cross-users en CP2
- XFF geo-spoof : country override trusted end-to-end
- race_smash 40/40 sans dedup ; h5_event plaintext ingestion
- Lanes restantes de CP2 : per-video secretKey channel (APK authentifié),
  tenant access_id hunt, les reads dérivés des access_id catalogs

## RÈGLES
- MCTS r0, DIFF avant brute-force, batch 5x, digest épisodique = index.
- Les chains testent des LANES DIFFÉRENTES (pas de doublon de travail).
- Chaque chain scelle ses findings dans le workspace partagé.
- Le verifier RE-TESTE au moins 3 claims des chains avec la probe lane.

## LIVRABLE
plan.md + chains parallèles + verifier_report.md + rapport final avec
0 claims non vérifiés — la stack complète, de bout en bout.
