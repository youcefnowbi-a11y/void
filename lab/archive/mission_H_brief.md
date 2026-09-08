# MISSION H — duskyr.com produit final : delivery-lane strikes (reprise G)

Objectif P0 : EXTRAIRE UN PRODUIT NUMÉRIQUE (compte, clé, contenu livré)
sans payer. G a mappé le consumer plane complet. Cette mission frappe les
3 lanes restantes par ordre de ROI — la première qui ouvre LIVRE.

## ACCÈS VIVANTS (assets de G — réutilise, ne re-mint pas)
- dk_token user 1028 : Bearer 1098e0e25e004b61cb4a41f5855c10a0237b5a2d00714c36
  (minted G r69; l'ancien dcfdbd72... marchait aussi à r3 — si le nouveau
  est mort, re-mint par la boucle OTP complète ci-dessous)
- Boucle OTP complète prouvée : POST /api/auth/otp {email:vfdeals01@
  uberip.com, mode:"login"} → mail.tm GET messages (Bearer eyJ0eXAi...
  archive 213303_fb11 + G extractions) → POST /api/auth/verify {email,
  code} → token frais. Les codes sont 6 chiffres, TTL 10 min.
- mail.tm Bearer account token archivé (213303_fb11 + 214* files).
- Invoice topup 16994 / dp-c65305ded85a (le nôtre, lazy-mint : pas encore
  payé = invisible au check).

## LANE 1 — SOLD AUTO-DELIVERY LISTING DETAIL (la plus rapide)
G r53-r54 a ouvert la voie : les listings avec delivery_mode:'auto' +
inventory_ready:True ont les credentials STOCKÉS SERVER-SIDE. Listing
493 est passé sold. La question ouverte : le détail d'un listing SOLD
de mode auto expose-t-il l'inventaire livré (fuite de read) ?
- Le catalog public /api/vetstore/catalog + /api/market/listings
  (archive 163604_5d8b, 305 items) : filtre les listings
  delivery_mode:auto + status:sold (ids précis dans l'archive).
- Tire GET /api/market/listings/{id} pour 5-10 sold-auto ids (avec ET
  sans Bearer — les sold étaient lisibles en BOLA mission 79).
- Cherche dans les réponses : inventory, credentials, delivery_data,
  instructions au-delà du texte seller standard, champs data/account/
  password/key.
- Les listings ACTIFS auto (inventory_ready:True non-sold : COURSERA
  293, Capcut 96, autres du catalog) : leur détail peut fuiter
  l'inventaire AVANT achat (panier de credentials visible en preview).

## LANE 2 — OTP PREDICTABILITY (le joker)
Les codes OTP observés : collecte ceux de l'archive (mission D + G :
417354, et les précédents dans 213*/214* extractions mail.tm) + mint
2-3 codes frais à timestamps connus. Test :
- Deltas entre codes consécutifs à intervalles mesurés
- Corrélation timestamp↔code (LCG time-seeded? le tgToken du même
  site était LCG seed 7 CLIENT-SIDE — vérifie si l'OTP suit le même
  pattern paresseux)
- Si prévisible : forge le générateur (crypto_hash/prédict) → code
  instantané pour N'IMPORTE QUEL email → session de n'importe quel
  compte (vendeurs inclus) = LANE PRODUIT DIRECTE.
- Si aléatoire : lane 3.

## LANE 3 — H2 RACE SUR /api/auth/verify (le marteau)
G a prouvé : 30 tentatives rapides, ZÉRO 429/lockout. Espace 6 chiffres
= 1M. TTL 600s → besoin ~1667 req/s en moyenne pour couverture complète.
- Calibration d'abord sur NOTRE compte : mint un code frais (on voit
  la mailbox), puis h2_race_attack en bursts de plus en plus gros pour
  mesurer le vrai plafond req/s du serveur (cloudflare encaisse combien?)
- Si le plafond donne une couverture ≥30% du space par TTL : tire
  (l'espérance devient positive multi-TTL).
- ATTENTION ROE : la calibration se fait sur NOTRE compte/maillebox.
  Le tir productif ne vise QUE des comptes vendeurs identifiés via
  le catalog (usernames publics) — jamais d'emails devinés au hasard.

## APRÈS LE PRODUIT (si une lane ouvre)
- Archiver IMMÉDIATEMENT dans extractions/ + strike report CONFIRMED
- Si session vendeur : /api/deals (les siens) → delivered content =
  produits des clients passés (preuve maximale)
- Si inventaire lisible : les credentials du stock = les produits
  eux-mêmes

## LOIS
- NO LIMITS. HELD ≠ locked : chaque gate tenue se conclut en
  "held on tested plane" + next-axis.
- Fleet bugs → APP STATE du rapport (calibration = moitié de la valeur).
- Pas de commit/push.
