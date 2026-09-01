# VOIDFORGE — Dossier de recherche n°1 : Chasse aux vulnérabilités de niveau framework web

**Version :** 1.1 · **Statut :** finalisé · **Périmètre :** Next.js, Laravel, Spring, Django, Express, Rails, FastAPI/Starlette, ASP.NET · **Horizon :** 2013–2026, focus 2023–2026

> **Note de portée.** Ce dossier est un document de recherche et de défense : il documente les classes de défauts des frameworks web, leurs causes racines telles que publiées dans les avis officiels (NVD, GHSA, blogs de sécurité des éditeurs), et les méthodes/outils de détection. Il ne contient pas de charges utiles prêtes à l'emploi ni de procédures d'exploitation pas-à-pas ; pour chaque cas, la référence canonique est l'avis NVD cité. Les faits CVE cités ont été vérifiés en direct contre l'API NVD (REST `services.nvd.nist.gov`) et l'API GitHub Advisory Database (ranges affectés et versions corrigées GHSA) au moment de la rédaction ; tout détail non vérifiable est signalé comme tel dans le texte.

---

## 1. TAXONOMIE DES CLASSES

Les 0-days de framework ne sont pas un chaos de bugs isolés : ils se ramènent à un petit nombre de **classes de causes racines récurrentes**, chacune ancrée dans un moment précis du cycle de vie d'une requête. On décrit ici les sept classes majeures, avec pour chacune l'anatomie générale, des cas réels identifiés par CVE, et la leçon structurale.

### 1.1 Stage-skip de pipeline : contournement de middleware

**Anatomie.** Un framework web moderne exécute chaque requête à travers un pipeline d'étages : parsing → routing → middleware → handler → sérialisation. Les middlewares sont le lieu privilégié de l'authentification et de l'autorisation (authz). La classe « stage-skip » naît quand un **signal de contrôle interne du pipeline est exprimé dans un canal contrôlable par l'attaquant** (en-tête, paramètre, cookie de framework) : si le framework saute un étage quand ce signal est présent, un attaquant qui forge le signal obtient l'exécution du handler sans passer par les étages de sécurité.

**Cas d'étude 1 — CVE-2025-29927 (Next.js, middleware bypass).** C'est le cas canonique de la décennie récente, il mérite un traitement complet. Le mode middleware de Next.js utilise en interne des « sous-requêtes » : quand le middleware relance une requête interne, Next.js marque cette requête avec l'en-tête `x-middleware-subrequest` pour éviter une récursion infinie. Dans les versions vulnérables (≥ 1.11.4, corrigées en 12.3.5, 13.5.9, 14.2.25 et 15.2.3), le runtime traite la **présence** de cet en-tête comme la preuve qu'il s'agit d'une sous-requête interne et **exécute le handler en sautant le middleware**. Or l'en-tête est lu directement depuis la requête client : un client externe peut donc se présenter comme sous-requête interne. La valeur attendue est le chemin du module middleware répété jusqu'à une profondeur fixée (`MAX_RECURSION_DEPTH`, variable selon les versions) — ce qui la rend redevinable par observation du code source publié. Conséquence documentée par l'avis : tout contrôle d'authz effectué **uniquement** en middleware est contourné. Le correctif fait deux choses : il ne s'appuie plus sur un en-tête falsifiable pour porter la marque de sous-requête, et l'avis NVD recommande, pour les déploiements non corrigeables, de **filtrer l'en-tête `x-middleware-subrequest` en amont** (reverse proxy / WAF) — mitigation qui confirme la nature exacte du canal d'attaque. Le bug a été trouvé par test boîte noire des en-têtes internes du framework : les chercheurs ont émis l'hypothèse que le mécanisme anti-récursion laissait une trace observable côté client, puis ont vérifié le comportement du pipeline en forgeant l'en-tête. La leçon est générale : **toute donnée entrante qui conditionne le contrôle de flux du pipeline est une surface d'auth-bypass**.

**Cas d'étude 2 — CVE-2023-29020 (@fastify/passport + @fastify/csrf-protection, écosystème Fastify).** L'avis décrit une **bypass de la protection CSRF** dans l'ordonnancement entre le middleware d'authentification passporté et le plugin CSRF : quand la protection CSRF est combinée à l'authentification, l'ordre de branchement des plugins (le graphe de décorateurs Fastify) permet à une requête de franchir la couche d'auth sans le check CSRF attendu. Cause racine : le pipeline n'est pas un ordre linéaire documenté mais un graphe d'enregistrement de plugins, et la sécurité dépend de l'ordre d'enregistrement — un défaut d'architecture de pipeline plutôt que d'implémentation ponctuelle.

**Cas d'étude 3 — CVE-2022-22978 (Spring Security).** `RegexRequestMatcher` mal configuré (expression régulière insensible à la casse) peut être contourné sur certains conteneurs de servlets : la divergence de normalisation d'URL entre conteneurs (tomcat, jetty) fait qu'une requête dont le chemin diffère par la casse n'est plus appariée par la règle de protection. C'est un hybride stage-skip/normalisation (§1.5) : le « saut d'étage » provient d'un appariement de route qui croit ne pas s'appliquer. Corrigé en 5.4.11+, 5.5.7+, 5.6.4+.

### 1.2 Désérialisation et chaînes de gadgets

**Anatomie.** Les frameworks offrent des mécanismes de sérialisation (Ruby Marshal/YAML, Java `ObjectInputStream`, PHP `unserialize`, .NET `BinaryFormatter`). Le défaut naît quand un flux contrôlé par l'attaquant est désérialisé en objets du runtime : la construction d'objets déclenche des effets de bord (getters, destructeurs, callbacks) qu'un attaquant peut enchaîner en **gadget chain**. La cause racine n'est jamais « le format YAML » mais **la frontière de confiance qui laisse des données non fiables atteindre un désérialiseur de objets du framework**.

**Cas d'étude 1 — CVE-2022-32224 (Ruby on Rails / Active Record).** Les colonnes sérialisées en YAML (`serialize` avec le codeur YAML par défaut) permettent une escalade vers RCE si l'attaquant peut manipuler les données de la colonne : la désérialisation YAML instancie des objets Ruby arbitraires. Corrigé en 7.0.3.1, 6.1.6.1, 6.0.5.1, 5.2.8.1 ; le correctif impose un chargement YAML restreint aux classes permises. À noter : la frontière ici est indirecte (base de données → désérialisation), ce qui est typique des bugs de framework : la donnée a traversé une frontière de confiance **plus tôt** dans le cycle de vie (écriture en base) que là où elle est dangereusement interprétée.

**Cas d'étude 2 — CVE-2021-3129 (Laravel / Ignition).** Ignition, la page d'erreur de Laravel (≤ 2.5.1), permet à un attaquant **non authentifié** d'exécuter du code arbitraire via un usage non sécurisé de `file_get_contents()`/`file_put_contents()` dans les « solution providers » de la page d'erreur : le chemin de fichier est partiellement contrôlé, ce qui donne une primitive d'écriture (typiquement combinée avec la réinitialisation du fichier de logs). Corrigé en Ignition 2.5.2 / Laravel 8.4.2. C'est le pattern « point de départ inattendu » : le désérialiseur n'est pas touché, mais une primitive de fichier + les gadgets de l'écosystème PHP aboutissent au même impact.

**Cas d'étude 3 — CVE-2020-8203 (lodash), le gadget transversal.** Prototype pollution via `_.zipObjectDeep` (lodash < 4.17.20). Lodash n'est pas un framework web, mais c'est le **matériau des gadget chains Node** : une pollution de prototype (§1.4) qui atteint un objet accessible à lodash transforme la pollution en RCE ou en bypass. Toute taxonomie de gadgets doit inclure ces dépendances transversales, pas seulement les frameworks.

### 1.3 Injection d'expressions : SpEL, OGNL, SSTI

**Anatomie.** La plupart des frameworks embarquent un langage d'expression (Spring Expression Language, OGNL pour Struts, moteur de template Jinja2/ERB/Razor). Le défaut naît quand une **chaîne contrôlée par l'attaquant est évaluée** par ce moteur : soit parce qu'un helper du framework transmet l'entrée à l'évaluateur, soit parce que la génération de code du moteur (compilation de templates, d'expressions de binding) incorpore l'entrée sans neutralisation. CWE-917 (expression language injection) et CWE-1336 (SSTI) couvrent la famille.

**Cas d'étude 1 — CVE-2018-1273 (Spring Data Commons).** Le binder de propriétés de Spring Data Commons (< 1.13.10 / 2.0.5) évaluait les chemins de propriétés issus des **noms de paramètres de requête** via SpEL : un nom de paramètre forgé devenait une expression exécutée → RCE. Correctif : réécriture du binder sans évaluation SpEL des chemins. C'est le cas d'école : **la grammaire d'une façade ergonomique (binding `?user.name=x`) fuit vers l'évaluateur d'expressions**.

**Cas d'étude 2 — CVE-2017-5638 (Apache Struts 2, parser Jakarta multipart).** La génération du message d'erreur du parser multipart incorpore l'en-tête `Content-Type` contrôlé par le client, et ce message est ensuite évalué par OGNL → RCE (la faille d'Equifax). Cause racine : le **canal d'erreur** est un chemin d'injection — les exceptions construites depuis des données client et re-évaluées par un moteur d'expression sont un sink à part entière.

**Cas d'étude 3 — CVE-2023-20863 (Spring Framework).** Une expression SpEL forgée entraîne un déni de service (corrigé en 5.2.24+, 5.3.27+, 6.0.8+). Même sans exécution de code, l'**évaluateur d'expressions est un point de DoS algorithmique** : les moteurs d'expression ne sont pas conçus pour borner le coût d'évaluation d'expressions arbitraires (cf. §1.7 pour la généralisation ReDoS/complexité).

### 1.4 Prototype pollution (écosystème Node)

**Anatomie.** JavaScript hérite par chaîne de prototypes ; un parser ou un merger qui construit des objets depuis une entrée client sans neutraliser les clés `__proto__`, `constructor`, `prototype` permet d'écrire dans `Object.prototype` et de corrompre tous les objets du processus. CWE-1321. L'impact dépend des consommateurs en aval : DoS (structure corrompue), bypass d'auth (propriétés de sécurité « ajoutées » à `Object.prototype`), RCE via gadget (options de compilation de template, chemins de chargement de modules).

**Cas d'étude 1 — CVE-2022-24999 (qs / Express).** `qs` < 6.10.3 (utilisé par Express < 4.17.3 en mode étendu) permet l'injection d'une clé `__proto__` via la syntaxe à crochets du parser de requête, avec pour effet documenté un blocage du process Node (et, selon l'application, des pollutions plus graves). Corrigé en qs 6.10.3 / Express 4.17.3. Cause racine : le parser de query string considérait toutes les clés intermédiaires comme des chemins d'objets légitimes.

**Cas d'étude 2 — CVE-2020-8203 (lodash).** Voir §1.2 : le gadget consommateur. La chaîne « pollution → gadget » est la vraie unité d'analyse ; le scoring de reachabilité (§5.3) formalise exactement cette chaîne.

### 1.5 Divergences de normalisation : chemins, routes, parsing

**Anatomie.** Une requête traverse plusieurs parseurs : proxy front, framework, conteneur, OS (NTFS vs POSIX), base de données. Chaque parseur a sa grammaire de normalisation (barres obliques, encodages percent, backslashes Windows, unicode NFKC, casse). Un 0-day de classe « normalisation » naît quand **deux composants interprètent différemment la même requête** et que la décision de sécurité est prise par le composant le plus permissif.

**Cas d'étude 1 — CVE-2024-38816 (Spring Framework, WebMvc.fn/WebFlux.fn).** Les applications qui servent des ressources statiques via les frameworks fonctionnels (`RouterFunctions`) sont vulnérables à du path traversal quand la ressource est explicitement configurée sur un `FileSystemResource` : un client forge des requêtes et obtient des fichiers **en dehors de la racine servie**, dans la limite des permissions du process. Deux garde-fous documentés bloquent la requête : le HTTP Firewall de Spring Security en amont, ou l'exécution sous Tomcat/Jetty — la normalisation du conteneur rattrape celle du framework, une leçon de défense en profondeur. Correctif open source : **6.1.13 uniquement** (GHSA-cx7f-g6mp-7hqm) ; branches 5.3.x (≤ 5.3.39) et 6.0.x (≤ 6.0.23) concernées, sans correctif OSS (support commercial uniquement). 

**Cas d'étude 2 — CVE-2024-38819 (Spring Framework, même famille).** Variante du même défaut de ressource statique, publiée trois mois après le premier avis (décembre 2024, GHSA-g5vr-rgqm-vf78), corrigée en open source **6.1.14 uniquement** — branches 5.3.x (≤ 5.3.39) et 6.0.x (≤ 6.0.23) concernées, sans correctif OSS. La récurrence du bug dans le même sous-système en quelques mois est un signal méthodologique : **chaque correctif de normalisation définit une grammaire, et il faut tester la grammaire, pas le patch** (§2.3).

**Cas d'étude 3 — CVE-2024-47081 (python-requests).** Un défaut de parsing d'URL permet, pour certaines URLs malveillamment formées, de **sélectionner les mauvaises credentials `.netrc`** et de les envoyer à un tiers. Cause racine : divergence entre la sélection d'hôte pour l'auth et le parsing d'URL. C'est le même pattern que CVE-2013-6417 (actionpack, divergences de parsing des en-têtes entre clients HTTP) : la **cohérence de parsing entre deux composants est une propriété de sécurité en soi**.

### 1.6 Confusion de clés de cache et Host header

**Anatomie.** Les frameworks cachent des réponses SSR (pages, fragments, ISR/SSG). La clé de cache dérive de propriétés de la requête (URL, en-tête `Host`, `x-forwarded-*`, cookies partiels). Deux sous-classes : (a) la clé **ne contient pas** une propriété qui influence la réponse → un utilisateur empoisonne la réponse d'un autre ; (b) la clé **contient** une propriété contrôlée mais la réponse est servie de manière partagée → empoisonnement cross-user.

**Cas d'étude 1 — CVE-2024-46982 (Next.js).** En envoyant une requête forgée, il est possible d'empoisonner le cache d'une **route SSR non dynamique du pages router** : la requête d'un attaquant remplace l'entrée de cache servie aux utilisateurs suivants. Le correctif renforce l'isolation des propriétés de requête utilisées pour dériver les entrées de cache.

**Cas d'étude 2 — CVE-2024-34351 (Next.js, Server Actions).** Un SSRF dans les Server Actions : quand une action redirige vers une URL relative, la construction de l'URL absolue côté serveur s'appuie sur l'en-tête `Host` contrôlé par le client, et le serveur suit ce redirect → requête sortante forgée. Corrigé en 14.1.1. Cause racine identique à celle du cache-poisoning : **le `Host` est traité comme une identité de serveur de confiance alors que c'est une entrée client** (CWE-1385, origin validation error). C'est aussi un exemple parfait de taint-tracking interne : la donnée `Host` circule du parseur HTTP jusqu'au résolveur d'URL sortant.

### 1.7 Défauts des couches internes : SQL générée et complexité algorithmique

**Anatomie.** Les ORM et helpers de framework **génèrent du SQL et des transformations** à partir d'API typées. Le développeur croit la couche sûre ; or les noms de colonnes/alias/chemins JSON passés à ces API peuvent finir interpolés dans le SQL généré, et les helpers de texte peuvent avoir des complexités super-linéaires sur des entrées forgées.

**Cas d'étude 1 — CVE-2024-42005 (Django).** `QuerySet.values()`/`values_list()` sur un modèle avec `JSONField` est sujet à de l'injection SQL **dans les alias de colonnes** via une clé/nom JSON forgé (corrigé en 5.0.8 / 4.2.15). Cause racine : la position « alias » du SQL généré n'était pas quotée comme un identifiant non fiable.

**Cas d'étude 2 — CVE-2024-38875 (Django).** Les filtres `urlize`/`urlizetrunc` sont sujets à un DoS via des entrées contenant un très grand nombre de parenthèses/crochets (corrigé en 4.2.14 / 5.0.7). Classe « DoS algorithmique » : coût super-linéaire atteignable par une entrée petite. Même famille que le ReDoS (CWE-1333) : la **complexité du parseur est une surface**.

---

## 2. MÉTHODOLOGIE DE CHASSE

Comment ces bugs sont-ils trouvés en pratique ? Six méthodes, de la plus artisanale à la plus outillée, qui se combinent presque toujours.

### 2.1 Revue de source orientée cycle de vie

Le point de départ le plus rentable est la lecture du code qui implémente le **cycle de vie de la requête** : l'adaptateur HTTP (où les en-têtes deviennent des objets), le routeur (où les chemins sont normalisés et appariés), la couche middleware (où l'ordre d'exécution est décidé), les binder/désérialiseurs (où l'entrée devient des objets typés), les résolveurs de vue/ressources (où les chemins de fichiers sont joints). On cherche les invariants rompus : *qui décide de sauter un étage ? quelle propriété distingue une requête interne d'une requête externe ? quelle normalisation est appliquée avant l'appariement, et après ?* La découverte de CVE-2025-29927 suit exactement ce schéma : se demander « comment le framework sait qu'une requête est une sous-requête interne » conduit à l'en-tête, donc au bypass.

### 2.2 Patch-diffing inter-versions

Le diff entre deux versions du framework est une **carte des invariants fragiles** : chaque changement dans un parseur, un binder ou un matcher décrit une classe de bug que les mainteneurs ont déjà corrigée une fois. La méthode : cloner le dépôt, extraire les diffs des bulletins de sécurité (GHSA/NVD donnent la version corrigée), classifier les diffs par type (normalisation, confiance d'en-tête, quottage d'identifiant SQL), puis chercher **des usages du même pattern dans des sous-systèmes non couverts par le patch**. C'est la technique des « patch siblings » : un correctif de path traversal dans le serveur statique de Spring (CVE-2024-38816, puis 38819) indique que la grammaire de normalisation du résolveur est fragile — la bonne question est « quels autres chemins de code partagent ce résolveur ? ».

### 2.3 Differential fuzzing (deux versions, deux implémentations)

Le principe : exécuter le même corpus de requêtes contre deux cibles — version vulnérable vs corrigée, ou deux implémentations censées conformes (framework A vs conteneur B, deux parseurs d'URL) — et flagger les **divergences sémantiques** (statut, en-têtes de sécurité, décisions d'authz, corps) plutôt que les différences cosmétiques. Le corpus se construit depuis la suite de tests du framework (§2.6) enrichie de mutations guidées par la grammaire du parseur suspect. La métrique de divergence est formalisée en §5.2. Les découvertes de classe « normalisation » (CVE-2013-6417 sur le parsing des en-têtes Rails, CVE-2024-47081 sur le parsing d'URL de requests) sont dans le champ naturel de cette méthode : un parseur différent aurait divergé.

### 2.4 Taint tracking de l'entrée au sink

Formellement : marquer les **sources** (chaînes issues du path, query, en-têtes, corps), propager à travers les transformations, et vérifier si l'empreinte atteint un **sink** dangereux (évaluateur d'expression, désérialiseur, résolveur de fichiers, constructeur SQL, dérivateur de clé de cache). Le calcul se fait en analyse de flux de données sur le graphe de dépendances de programme (PDG) — la formulation en point fixe est en §5.1. Les frameworks rendent le problème plus tractable que les applications : les sources et sinks sont **centralisés** (un seul adaptateur HTTP, un seul moteur d'expression), donc une projection du taint sur les quelques milliers de lignes du noyau suffit à prioriser une revue manuelle.

### 2.5 Détection de mésusage d'API (API misuse)

Beaucoup de CVE de framework sont des pièges tendus aux utilisateurs du framework : un `RegexRequestMatcher` insensible à la casse (CVE-2022-22978), une colonne sérialisée YAML (CVE-2022-32224), un ordre de plugins Fastify. La méthode : extraire du dépôt du framework les usages déconseillés par les mainteneurs eux-mêmes (issues, migrations guide, tests de non-régression) et en faire des requêtes d'analyse statique, soit pour alerter les applications (défense), soit pour repérer les chemins du noyau où l'API piègeuse est elle-même utilisée.

### 2.6 Fuzzing des trous de la suite de tests

La suite de tests du framework encode ce que les mainteneurs croient couvert. On mesure la couverture (branches/arêtes) de la suite sur le noyau, on identifie les régions **jamais atteintes** (handlers d'erreurs, chemins de normalisation exotiques, branches de compatibilité HTTP/1.0, requêtes pipelinées, en-têtes dupliqués), et on y concentre le fuzzing. Les fuzzers record-replay de type MoonShine (§3) fournissent la technique : distiller des traces réelles en graines de fuzzing. Le point clé : la suite de tests du framework est écrite par ceux qui connaissent le comportement voulu — les trous sont donc exactement là où le comportement **n'a pas été spécifié**, c'est-à-dire où la normalisation diverge.

---

## 3. OUTILLAGE SOTA 2024–2026

| Outil | Rôle dans la chasse | Licence / exécution Windows |
|---|---|---|
| **CodeQL** (`codeql.github.com`) | Analyse sémantique BD-de-code : sources/sinks par framework (SpEL injection, prototype pollution, path traversal, SSRF), requêtes personnalisables en QL. Packs dédiés Java/Spring, JS/TS, Python, C#. | Open source (recherche), CLI natif Windows. |
| **Semgrep** (`semgrep.dev`) | Règles par écosystème (`p/spring`, `p/django`, `p/expressjs`, `p/rails`), écriture rapide de règles pour patterns de patch-diffing. | OSS (moteur) ; natif Linux/macOS, **WSL2** sur Windows. |
| **Joern** (`joern.io`) | Code Property Graph (CPG) intermédiaire, scripting Scala pour PDG custom — utile pour les classes sans requête CodeQL prête. | OSS ; JVM — WSL2 recommandé. |
| **Brakeman** | SAST spécialisé Rails (désérialisation, YAML, SQL). | OSS ; gem Ruby, natif Windows. |
| **OWASP ZAP** (`zaproxy.org`) | Proxy/scanner de base pour le harness différentiel, réécriture de requêtes, scripts. | OSS ; Java natif Windows. |
| **mitmproxy** (`mitmproxy.org`) | Capture/rejeu du trafic pour record-replay et differential harness. | OSS ; natif Windows (pip). |
| **AFL++ / libFuzzer / Jazzer / Atheris** | Fuzzing guidé par couverture des parseurs du framework (Atheris pour Python/Django-Starlette, Jazzer pour JVM/Spring). | OSS ; WSL2 sur Windows. |
| **MoonShine** (USENIX Security 2018) | Distillation de traces en graines de fuzzing — le patron des fuzzers record-replay applicatifs. | Papier + implémentations de référence. |
| **Crawljax** (`crawljax.com`) | Exploration d'applis AJAX stateful — extraction d'états pour corpus. | OSS ; JVM, natif Windows. |
| **OSV-Scanner / GHSA DB** (`osv.dev`) | Résolution version→vulnérabilités connues, base des diff de patch. | OSS, natif Windows. |

**Notes de méthode.** (1) CodeQL est le plus productif sur les classes §1.1–1.6 car les sources/sinks standard y sont modélisés ; les requêtes se personnalisent pour les canaux internes du framework (l'en-tête `x-middleware-subrequest` de CVE-2025-29927 s'exprime comme une source « header → contrôle de flux » en une vingtaine de lignes de QL). (2) Semgrep excelle sur le patch-diffing : le diff du correctif se traduit en règle en quelques minutes. (3) Pour le différentiel (§2.3), aucun outil prêt-à-l'emploi ne couvre les frameworks : le harness est un script Python (voir §4) — mitmproxy fournit le record/replay, ZAP la réécriture.

---

## 4. ARCHITECTURE D'UN MOTEUR VOIDFORGE : `framework_hunter`

Moteur Python-first, à visée de **triage et de vérification défensive** : on lui donne un framework, une version et un checkout local (ou un package installé) ; il produit un verdict structuré. Pipeline en cinq étages :

**(a) Lifecycle-map extraction.** Parser les déclarations de routes et de middleware du framework cible (URLconf Django, routes Rails, arbre de routeurs Express, annotations Spring) et produire un **automate du cycle de vie** : états = étages (parse → authn → authz → handler → render), transitions annotées des conditions de saut d'étage. C'est cet automate qui rend explicite la classe §1.1 : tout « skip conditionnel » y devient une arête étiquetée, donc auditable.

**(b) Sink inventory.** Catalogue par écosystème des sinks dangereux : évaluateurs d'expression (SpEL/OGNL), désérialiseurs (YAML/Marshal/ObjectInputStream), résolveurs de fichiers statiques, constructeurs SQL, dérivateurs de clés de cache, émetteurs de requêtes sortantes (SSRF). Chaque sink est décrit par une signature (AST ou BD CodeQL) et sa CWE.

**(c) Taint fixed-point.** Construire le PDG du checkout (CodeQL ou Joern en export JSON), marquer les sources d'entrée (paramètres, en-têtes, corps, chemins), itérer la fonction de transfert jusqu'au point fixe (§5.1), et extraire les flux source→sink atteignables avec leur chemin de propagation.

**(d) Differential harness vs version corrigée.** Monter deux instances de l'application cible (version courante / version corrigée de l'avis ou HEAD), rejouer un corpus (issu de la suite de tests du framework + mutations), calculer la divergence par route et étage (§5.2) et ne flagger que les divergences **sémantiques** sur les routes de l'automate qui portent des décisions d'authz ou d'accès aux ressources.

**(e) Verdict contract.** Sortie unique, JSON, compatible avec le format `verdict()` VOIDFORGE :

```json
{
  "tool": "framework_hunter/0.1.0",
  "target": { "framework": "next.js", "version": "14.2.24", "source": "checkout" },
  "verdict": "vulnerable | clean | inconclusive",
  "exploitable": true,
  "confidence": 0.86,
  "summary": "Pipeline stage-skip reachable: middleware authz bypassed via forged internal subrequest marker (cf. CWE-285).",
  "evidence": [
    { "type": "taint_flow", "cwe": "CWE-285",
      "source": "http.headers[x-middleware-subrequest]",
      "sink": "pipeline.stageSkipCheck",
      "path": ["adapter.readHeader", "pipeline.isInternalRequest", "pipeline.skipMiddleware"],
      "location": { "file": "server/web/middleware.ts", "line": 212 } },
    { "type": "divergence", "route": "/admin", "stage": "middleware",
      "corpus_id": "c-0042", "metric": "jaccard=0.94, status 200 vs 307",
      "baseline": "patched-14.2.25" }
  ]
}
```

**Boucle centrale (pseudo-code Python) :**

```python
def hunt(target: FrameworkTarget) -> Verdict:
    # (a) automate du cycle de vie
    automaton = extract_lifecycle_map(target.checkout)          # routes + middleware + skip-edges
    skips = [edge for edge in automaton.edges if edge.kind == "conditional_skip"]
    # (b) inventaire de sinks
    sinks = SINK_CATALOG[target.framework](target.checkout)
    # (c) point fixe de taint sur le PDG
    pdg = build_pdg(target.checkout)                            # export CodeQL/Joern
    flows = taint_fixed_point(pdg, sources=EXTERNAL_INPUTS, sinks=sinks)
    flows = [f for f in flows if f.reaches(skips) or f.sink.is_authz_relevant()]
    # (d) harness différentiel vulnérable vs corrigé
    corpus = build_corpus(target, automaton)                    # tests du framework + mutations
    divergences = []
    with run_instance(target) as vuln, run_instance(target.patched()) as fixed:
        for req in corpus:
            d = semantic_divergence(vuln.send(req), fixed.send(req))
            if d.is_semantic_on(automaton.authz_routes):
                divergences.append(d)
    # (e) verdict
    return verdict(target, flows, divergences)   # JSON du contrat ci-dessus

def taint_fixed_point(pdg, sources, sinks) -> list[Flow]:
    T = set()                                    # état initial ⊥
    while True:
        T_next = kleene_step(pdg, T, sources)    # F(T) — §5.1, monotone, terminaison ≤ |N|
        if T_next == T:
            break
        T = T_next
    return [extract_flow(pdg, t) for t in T if t in sinks]
```

Le contrat `verdict()` est volontairement minimal (tool, exploitable, summary, evidence) : c'est l'interface de triage humain — chaque `evidence` doit être re-vérifiable par un analyste en ouvrant la `location` ou en re-jouant le `corpus_id`.

---

## 5. MATHS APPLIQUÉES

### 5.1 Propagation de taint : point fixe de Kleene sur le PDG

Soit `G = (N, E)` le graphe de dépendances de programme (nœuds = variables/expressions, arêtes = dépendances de données et de contrôle). Définissons l'ensemble des faits de taint `T ⊆ N` et la fonction monotone :

    F(T)(v) = src(v)  ∨  ⋁_{(u,v) ∈ E} [ T(u) ∧ ¬σ(u,v) ]

où `src(v)` vaut vrai si `v` est une entrée externe et `σ(u,v)` si l'arête traverse une fonction de nettoyage. On cherche le plus petit point fixe :

    T* = lfp F  =  F^ω(⊥)  =  ⨆_{n ∈ ℕ} F^n(⊥)

C'est l'itération de Kleene : `F` monotone sur le treillis fini `(P(N), ⊆)` ⇒ convergence en au plus `|N|` itérations (théorème de Tarski ; chaque itération coûte `O(|E|)`). La formulation IFDS (Reps–Horwitz–Sagiv) étend ce calcul au meet-over-all-paths avec sommation tabulée et complexité `O(|E|³)` pour des domaines de faits finis — c'est la base des analyses de CodeQL et Joern. Propriété utile pour le triage : les itérés `F^n(⊥)` sous-estiment `T*`, donc tout flux visible à l'itération `n` est un **vrai positif partiel** (il ne manque que de la profondeur, pas de la correction).

### 5.2 Divergence différentielle

Pour un input `i`, on normalise chaque réponse en multi-ensemble de jetons `T_A(i)`, `T_B(i)` (statut, en-têtes canoniques, décisions authz, corps tokenisé). Divergence de Jaccard :

    δ(i) = 1 − |T_A(i) ∩ T_B(i)| / |T_A(i) ∪ T_B(i)|     ∈ [0, 1]

Sur le corpus `C`, on rapporte `Δ = max_{i∈C} δ(i)` et le quantile `δ₀.₉₉` (robuste aux outliers de corpus). Pour les dimensions continues (latence, taille), distance de Kolmogorov–Smirnov entre les distributions des deux instances :

    D_{n,m} = sup_x |F_A(x) − F_B(x)|

Seuillage : on ne flag que `δ(i) ≥ τ` **et** divergence sur un attribut d'authz/accès — le seuil `τ` se calibre par la distribution empirique de `δ` sur les inputs mutés issus des tests unitaires du framework (où la convergence est attendue).

### 5.3 Score de reachabilité de gadget

Un gadget chain est un chemin `Π` dans le graphe de flux (entry → … → sink) où chaque arête porte une probabilité d'être déclenchable `p(e)` (estimée empiriquement : presence de la condition, version de dépendance). Le score de la chaîne est la probabilité du chemin le plus probable :

    R(s) = max_{Π: entry ⇝ s} Π_{e ∈ Π} p(e)

Max-produit se ramène au plus-court-chemin en passant au logarithme : minimiser `Σ_{e∈Π} −log p(e)` (Dijkstra). Les chaînes multi-composants (pollution lodash → option de template → RCE, cf. §1.2/§1.4) sont exactement ce calcul sur un graphe inter-dépendances.

### 5.4 Score de risque agrégé

Le verdict composite (utilisé pour ordonner le triage humain) :

    Risk = 100 × ( w₁·EPSS + w₂·CVSS/10 + w₃·R(s) + w₄·F )

avec `Σ wᵢ = 1` (poids calibrés sur l'historique de triage : départ suggéré 0.35/0.25/0.30/0.10), `EPSS` la probabilité d'exploitation observée (FIRST), `CVSS v3.1` la sévérité de base de l'avis, `R(s)` la reachabilité §5.3, `F` la fraîcheur (décroissance du patch : `F = 1/(1 + âge_en_semaines/4)`). Toute métrique agrégée est un choix éditorial : le contrat `verdict()` publie les composantes, pas seulement le score.

### 5.5 Couverture de corpus

Couverture d'un corpus `C` sur l'ensemble de branches `B` du noyau :

    cov(C) = |B(C)| / |B|

avec `B(C)` les branches exécutées par au moins un input de `C` (couverture d'arêtes, standard AFL/libFuzzer). La métrique d'intérêt pour la chasse est la **couverture de diff** : `|B(v₁) ∖ B(v₂)|` — les branches exécutables dans la version courante mais pas dans la version corrigée, qui matérialisent la sémantine supprimée par le patch et guident le corpus du harness différentiel (§4d). Courbe de croissance `cov(C_k)` par ajout itéré d'inputs = estimateur de saturation : quand la courbe plateau, le corpus est stabilisé.

---

## 6. SOURCES

Tous les faits CVE ci-dessous ont été vérifiés contre l'API NVD et l'API GitHub Advisory Database au moment de la rédaction (descriptions, ranges affectés, versions corrigées, scores).

**Avis NVD des cas d'étude :**
1. [CVE-2025-29927 — Next.js middleware subrequest bypass](https://nvd.nist.gov/vuln/detail/CVE-2025-29927)
2. [CVE-2024-34351 — Next.js Server Actions SSRF](https://nvd.nist.gov/vuln/detail/CVE-2024-34351)
3. [CVE-2024-46982 — Next.js cache poisoning](https://nvd.nist.gov/vuln/detail/CVE-2024-46982)
4. [CVE-2022-32224 — Rails YAML serialized columns](https://nvd.nist.gov/vuln/detail/CVE-2022-32224)
5. [CVE-2021-3129 — Laravel Ignition RCE](https://nvd.nist.gov/vuln/detail/CVE-2021-3129)
6. [CVE-2022-24999 — qs/Express prototype pollution](https://nvd.nist.gov/vuln/detail/CVE-2022-24999)
7. [CVE-2023-29020 — @fastify/passport CSRF bypass](https://nvd.nist.gov/vuln/detail/CVE-2023-29020)
8. [CVE-2020-8203 — lodash prototype pollution](https://nvd.nist.gov/vuln/detail/CVE-2020-8203)
9. [CVE-2023-20863 — Spring SpEL DoS](https://nvd.nist.gov/vuln/detail/CVE-2023-20863)
10. [CVE-2018-1273 — Spring Data Commons SpEL injection](https://nvd.nist.gov/vuln/detail/CVE-2018-1273)
11. [CVE-2017-5638 — Struts 2 OGNL injection](https://nvd.nist.gov/vuln/detail/CVE-2017-5638)
12. [CVE-2024-38816 — Spring WebMvc.fn path traversal](https://nvd.nist.gov/vuln/detail/CVE-2024-38816)
13. [CVE-2024-38819 — Spring WebFlux.fn path traversal](https://nvd.nist.gov/vuln/detail/CVE-2024-38819)
14. [CVE-2022-22978 — Spring Security RegexRequestMatcher bypass](https://nvd.nist.gov/vuln/detail/CVE-2022-22978)
15. [CVE-2022-22965 — Spring Framework RCE (data binding)](https://nvd.nist.gov/vuln/detail/CVE-2022-22965)
16. [CVE-2024-38875 — Django urlize DoS](https://nvd.nist.gov/vuln/detail/CVE-2024-38875)
17. [CVE-2024-42005 — Django JSONField alias SQLi](https://nvd.nist.gov/vuln/detail/CVE-2024-42005)
18. [CVE-2024-47081 — python-requests .netrc leak](https://nvd.nist.gov/vuln/detail/CVE-2024-47081)
19. [CVE-2013-6417 — Rails header parsing divergence](https://nvd.nist.gov/vuln/detail/CVE-2013-6417)

**Outils et fondations :**
20. [GitHub Advisory Database](https://github.com/advisories) — source des diff de patch par GHSA.
21. [CodeQL](https://codeql.github.com/) — analyse sémantique, requêtes framework.
22. [Semgrep](https://semgrep.dev/) — règles par écosystème (`p/spring`, `p/django`, …).
23. [Joern](https://joern.io/) — Code Property Graph.
24. [OWASP ZAP](https://www.zaproxy.org/) — proxy/scanner de base.
25. [mitmproxy](https://mitmproxy.org/) — record/replay pour harness différentiel.
26. [OSV / OSV-Scanner](https://osv.dev/) — résolution version→vulnérabilités.
27. [CWE-1321 (prototype pollution)](https://cwe.mitre.org/data/definitions/1321.html) · [CWE-1336 (SSTI)](https://cwe.mitre.org/data/definitions/1336.html) · [CWE-917 (expression language injection)](https://cwe.mitre.org/data/definitions/917.html) · [CWE-1333 (ReDoS)](https://cwe.mitre.org/data/definitions/1333.html)
28. [Groce et al., *MoonShine: Optimizing OS Fuzzer Seed Selection with Trace Distillation*, USENIX Security 2018](https://www.usenix.org/conference/usenixsecurity18/presentation/groce) — patron des fuzzers record-replay.
29. [FIRST EPSS](https://www.first.org/epss/) — probabilités d'exploitation pour le scoring §5.4.
30. [Spring Framework RCE, annonce officielle (Spring4Shell)](https://spring.io/blog/2022/03/31/spring-framework-rce-early-announcement)
31. [Django security releases (weblog officiel)](https://www.djangoproject.com/weblog/)
32. [GHSA-cx7f-g6mp-7hqm — CVE-2024-38816 (patché en 6.1.13)](https://github.com/advisories/GHSA-cx7f-g6mp-7hqm)
33. [GHSA-g5vr-rgqm-vf78 — CVE-2024-38819 (patché en 6.1.14)](https://github.com/advisories/GHSA-g5vr-rgqm-vf78)

*Reps, Horwitz, Sagiv, « Precise Interprocedural Dataflow Analysis via Graph Reachability », POPL 1995 — fondement IFDS cité en §5.1.*
