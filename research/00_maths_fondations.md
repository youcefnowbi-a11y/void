# 00 — FONDATIONS MATHÉMATIQUES : les trois montagnes

*Campagne 0days difficiles — squelette formel unificateur. Les trois dossiers
spécialisés s'y rattachent : dossier_1 (frameworks), dossier_2 (memory corruption),
dossier_3 (auth flows).*

---

## 0. La vue unificatrice

Les trois classes difficiles partagent UNE même forme abstraite :

> **Trouver un état atteignable que le système interdit pourtant.**

| Classe | L'état interdit | Le modèle formel | La méthode d'énumération |
|---|---|---|---|
| Framework 0days | un chemin du pipeline qui saute une étape de sécurité | graphe de dépendances + automates du lifecycle | taint fixe-point + différentiel |
| Memory corruption | une écriture hors de l'objet alloué | layout mémoire + contraintes d'allocation | fuzzing coverage-guidé + concolic |
| Auth flows | l'accès à la ressource sans chaîne de preuve complète | automate produit (client × serveur × tokens) | apprentissage d'automate + monitors LTL |

La différence n'est pas la cible, c'est **l'espace d'états** et **comment on
l'énumère** sans explosion combinatoire. Chaque section donne le modèle, les
propriétés, et le calcul du coût.

---

## 1. AUTH FLOWS — automates de session (dossier_3)

### 1.1 Le modèle

Un flux d'authentification est un automate :

```
A = (S, Σ, δ, s₀, F)
  S : états (anonyme, identifié, MFA-pending, session-active, …)
  Σ : alphabet d'entrées (requêtes HTTP, tokens soumis, redirs suivies)
  δ : S × Σ → S, la transition (partielle — certaines entrées sont rejetées)
  s₀ : l'état initial ;  F ⊆ S : états « ressource sensible accessible »
```

**Le modèle d'attaquant** : Σ = Σ_legit ∪ Σ_a, où Σ_a sont les entrées que
l'attaquant contrôle (tokens volés, requêtes forgées, ordre altéré). Le bug
existe ssi :

```
∃ chemin s₀ →* s,  s ∈ F,  dont la trace ne contient PAS de preuve
complète de la chaîne requise (identité + MFA + binding de session).
```

### 1.2 Les propriétés LTL à monitorer

Quatre templates couvrent la quasi-totalité des CVEs de flux — no-skip, no-replay, binding-preservation, entropy-floor. Le dossier 3 (§2) étend cette famille à **sept propriétés** en ajoutant issuer-confinement, redirect-confinement et epoch-invalidation ; cette section présente le socle, le dossier 3 la famille complète.

- **No-skip** : `□(état_N+1 → ◇ preuve_N)` — l'étape N+1 exige la preuve de N.
  (Bypass MFA = atteindre F sans la transition MFA.)
- **No-replay** : `□(consommation(c) → ¬◇ consommation(c))` — un code à usage
  unique ne se consomme qu'une fois. (Race = fenêtre temporelle où δ n'a pas
  encore marqué c consommé.)
- **Binding-preservation** : tout token τ porte une liaison
  `τ = (subject, scope, epoch, audience, issuer)` ; la propriété dit que
  `grant(τ, s)` implique `subject(τ) = subject(s)`. (Mix-up = issuer(τ) ≠ issuer
  attendu par l'état ; IDP confusion = audience croisée.)
- **Entropy-floor** : `H(param) ≥ B` bits (state ≥ 128, code ≥ 160). Calcul :
  `H = L·log₂(|charset|)` ; borne d'anniversaire pour une collision : essais
  `≈ 2^(H/2)`.

### 1.3 L'automate produit et l'explosion d'états

Le vrai système est le produit :

```
P = A_client × A_serveur × A_tokens,   |P| ≤ |S_c|·|S_s|·|S_t|
```

Avec |S| ~ 10-40 par machine et Σ_a de taille |Σ_a|, l'énumération naïve coûte
`O(|P|·|Σ_a|)`. Deux réductions la rendent praticable :

1. **Quotienting par bisimulation** : deux états sont équivalents s'ils
   acceptent les mêmes extensions de traces (même futures possibles). On
   fusionne via partition refinement — coût `O(|Σ|·|S|·log|S|)` par itération.
2. **États symboliques** : chaque état porte un ensemble de contraintes φ
   (présence/absence de cookie, valeur du state, epoch du token) plutôt qu'une
   valuation concrète. Le monitor LTL s'évalue sur les contraintes ; une
   violation = φ satisfiable ∧ propriété violée → on demande à un solveur
   SMT (Z3) un chemin concret qui matérialise l'attaque.

### 1.4 Inférence de l'automate (on ne lit pas le code de la cible)

Approche **apprentissage actif** (L*/Angluin) : on interroge la cible comme une
boîte noire — membership queries (envoie la séquence, observe l'état via
sondes : message d'erreur, cookie, redirect) → table d'observation → automate
candidat → contre-exemple par equivalence query → raffinement. Complexité
pratique : quelques centaines de requêtes pour un flux OAuth standard. C'est
LA technique qui rend le moteur scriptable sans source.

---

## 2. MEMORY CORRUPTION — les maths du fuzzing binaire (dossier_2)

### 2.1 Le feedback de couverture

Le fuzzer maintient un bitmap des arcs (edges) du CFG exécutés. Fitness d'un
seed = nouveaux arcs découverts. La boucle :

```
corpus C ; boucle : choisir seed s ∈ C → muter → exécuter →
  si nouveaux arcs : C ← C ∪ {s'} ; sinon rejeter
```

### 2.2 Ordonnancement = bandit multi-bras

Choisir le seed qui mute est un problème d'exploration/exploitation. **UCB1** :

```
s* = argmax_{s ∈ C} [ Q(s) + c·√(2·ln t / n_s) ]
  Q(s) : récompense moyenne (nouveaux arcs / exécutions du seed)
  n_s  : nombre d'utilisations de s ;  t : total d'exécutions
```

Variante **Thompson sampling** : posterior Beta(α_s, β_s) par seed, on tire au
sort et on prend le max — meilleur en pratique quand les récompenses sont
rares (c'est le cas : un nouveau edge est rare).

### 2.3 Les power schedules (énergie de mutation)

AFL-family attribue à chaque seed une énergie de mutation (nombre de cycles
havoc) :

```
E(s) = E_min + (E_max − E_min) · f(cov(s))
  f linéaire décroissant (FAST) : les seeds « faciles » consomment vite
  f ∝ 1/t^α (COE) : cut-off exponentiel des seeds épuisés
```

L'équilibre : trop d'énergie sur les seeds matures = temps perdu ; trop peu =
zones inexplorées. La formule optimale dépend de la distribution des arcs
(difficiles = clusters profonds) — d'où l'intérêt des schedules adaptatifs
(MOPT : la distribution des opérateurs de mutation elle-même est apprise par
PSO — particle swarm optimization sur les probabilités π_mutation).

### 2.4 La contrainte branchée : RedQueen et concolic

Les comparaisons (`if x == MAGIC`) bloquent le fuzzing naïf : probabilité
d'uniforme `2^-32`. Deux remèdes :

- **RedQueen** : instrumenter les comparaisons, détecter que l'input contient
  des octets proches de la constante comparée, et substituer la valeur
  directement (colorisation + correspondance de position). Effectivement une
  propagation de contrainte à coût quasi nul.
- **Concolic** : accumuler le chemin φ = ∧ des branches prises ; pour forcer la
  branche non prise : résoudre φ ∧ ¬b_i avec un solveur SMT. Coût exponentiel
  dans le pire cas — c'est pourquoi on le réserve aux blocages locaux
  (hash-checks, magic numbers) après épuisement des mutations statistiques.

### 2.5 La fenêtre UAF et le grooming

Use-after-free : la corruption réussit ssi un objet contrôlé par l'attaquant
réutilise le chunk libéré. Modèle :

```
W = t_realloc − t_free        (la fenêtre)
P(hit) = |allocs_attaquants(size-class(c))| / |allocs_totaux(size-class(c))|
```

dans la même size-class (tcache LIFO pour glibc, LFH buckets pour Windows).
Le **grooming** rend ce dénominateur déterministe : séquencer les allocations
pour vider le bin, puis le remplir d'objets attaquants → P(hit) → 1. Les
protections modernes (safe-linking glibc, XFG Windows) déplacent le problème :
le modèle doit les inclure (safe-linking = mangle du pointeur `p ^ (addr >> 12)`
— il faut connaître l'adresse de pile/heap pour forger, d'où les primitives de
leak d'abord).

### 2.6 Triage et exploitabilité

Un crash n'est pas une CVE. Le rangage :

```
grade = w1·[contrôle RIP] + w2·[contrôle des registres/pointeurs] +
        w3·[contrôle des données écrites] − w4·[conditions prérequises fragiles]
```

(l'arbre canonique : SIGSEGV sur PC contrôlable > write-what-where >
déréférencement contrôlé > crash « data-only ».) Dédup : stack-hash du
backtrace symbolisé + hash du contexte d'allocation.

---

## 3. FRAMEWORK 0DAYS — taint, différentiel, gadgets (dossier_1)

### 3.1 Le taint comme point fixe de Kleene

Sur le graphe de dépendances PDG = (V, E) :

```
taint(v) = src(v) ∪ ⋃_{(u→v) ∈ E} propag(u → v, taint(u))
```

itération de Kleene sur le treillis des parties de V (monotone, terminaison
garantie — |V| itérations max, en pratique ~3-5 par SCC). Les sinks dangereux
avec taint non-sanitisé = candidats. Le raffinement : pondérer les arcs de
propagation par la force de la sanitisation rencontrée :

```
risk(sink) = Σ_{chemins p: entry→sink} e^(−Σ_{arc ∈ p} σ(arc))
  σ : 0 (aucune sanitisation) … ∞ (validation stricte)
```

### 3.2 Le différentiel comme détecteur de spécification

Deux versions A (vulnérables) et B (patchée) — ou deux implémentations de la
même spec — et un invariant I extrait de la documentation :

```
d(x) = 1  ssi  out_A(x) ⊭ I  ∨  out_B(x) ⊭ I   (violations)
divergence(A,B) = E_x[ 1(out_A(x) ≠ out_B(x)) ]  (estimée Monte-Carlo)
```

Patch-diffing : la fonction modifiée par le patch ISOLE la classe de bug —
le fuzzing dirigé vers les entrées qui atteignent cette fonction a une
probabilité de détection `p ≈ P(entrée atteint la branche modifiée)`, mesurable
sur la couverture différentielle entre les deux versions.

### 3.3 Les automates de pipeline (la classe middleware-skip)

Le lifecycle d'un framework (Next.js middleware, Spring filter chain, Django
middleware MRO) est un pipeline séquentiel :

```
req → M1 → M2 → … → Mn → handler
```

Un bug de la classe « stage-skip » = une entrée x telle que le pipeline saute
Mk (le stage d'auth) mais atteint quand même le handler :

```
∃ x : δ(x) contourne Mk ∧ handler(x) exécuté
```

C'est exactement la no-skip property de la section 1.2 — **les mêmes monitors
LTL servent aux frameworks et aux auth flows**. Le CVE Next.js 2025-29927
(header `x-middleware-subrequest` incrémenté pour faire croire à une
récursion interne) est un saut de stage déclenché par une entrée du protocole
lui-même : le monitor no-skip sur le lifecycle le détecte sans connaître la
vulnérabilité à l'avance.

---

## 4. INTÉGRATION VOIDFORGE — trois moteurs, un contrat

| Moteur | Entrée | Cœur formel | Sortie (contrat verdict) |
|---|---|---|---|
| `auth_state_engine` | URL + type de flux | L*/monitors LTL + SMT | flow_bug classe, chemin PoC, liaison violée |
| `binary_fuzzer` | binaire/parsers + corpus | UCB1 + power schedule + concolic | crash, grade d'exploitabilité, input PoC |
| `framework_hunter` | repo/package + version | taint fixe-point + différentiel | sink risqué, divergence, PoC HTTP |

Chaque moteur rend un verdict() JSON compatible avec le ledger / la Living
Graph / le rapport de puissance — la doctrine LAW OF THE REPORT s'applique
telle quelle : chaque affirmation porte sa preuve.

### Le programme des dossiers

1. dossier_1_framework_0days.md — taxonomie CVE + chasse + moteur (chercheur en cours)
2. dossier_2_memory_corruption.md — maths du fuzzing + harnesses + moteur (chercheur en cours)
3. dossier_3_auth_state_machines.md — automates + LTL + moteur (chercheur en cours)
4. Ce document — les fondations communes (fait)
5. Puis : synthèse croisée + plan d'implémentation priorisé
