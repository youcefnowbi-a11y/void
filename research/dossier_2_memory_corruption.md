# DOSSIER 2 — CHASSE AUX CORRUPTIONS MÉMOIRE PAR FUZZING BINAIRE
### VOIDFORGE Offensive Research — Memory-Corruption Vulnerability Hunting via Binary Fuzzing
**VOIDFORGE · campagne 0days difficiles · rédigé par ENI. Remplace la v1 partielle (les deux détails mécaniques corrects de la v1 — désync de state-machine curl, modèle fractionnaire de réutilisation — sont conservés et intégrés).**
**Périmètre : bugs de corruption mémoire dans services et parsers binaires (stack/heap overflow, UAF, type confusion, double-free, integer issues). Hors périmètre : couche HTTP applicative.**
**Méthode factuelle : les dix CVE cités ont été vérifiés en direct contre l'API REST NVD 2.0 (descriptions + CVSS extraits du JSON par requête `cveId` exacte, voir §6). Toute année, version ou formule non verrouillée est marquée « (à confirmer) ». Aucun identifiant de CVE ni citation n'est fabriqué.**

---

## 1. TAXONOMIE DES CORRUPTIONS

### 1.1 Stack overflow — mécanique exacte

Le prologue d'une fonction x86-64 à frame protégée compile typiquement en :

```asm
push rbp
mov  rbp, rsp
sub  rsp, N              ; réservation du frame
mov  rax, fs:[0x28]      ; glibc : canary depuis %fs:0x28 (TLS stack_guard)
mov  [rbp-8], rax        ; stockage du canary en tête de frame
```

L'épilogue re-charge `[rbp-8]`, XOR avec la référence TLS, et appelle `__stack_chk_fail` si divergence — l'exploit naïf meurt **avant** le `ret`. Le canary glibc est initialisé une fois par process depuis `AT_RANDOM` (entropie du noyau). Sur Windows, `__security_cookie` est dérivée de l'adresse de retour du caller XORée avec l'heure système et le PID, puis re-XORée avec l'adresse du cookie par `__security_check_cookie` — détail des builds modernes (à confirmer), la mécanique générale tient.

Trois voies d'exploitation malgré le canary :

1. **Écrasement sous le canary** : buffers `alloca`/VLA ou réordonnés par le compilateur — corruption intra-frame (pointeurs locaux, variables logiques) sans toucher `[rbp-8]` : le *data-only* de stack.
2. **Leak du canary** puis réécriture identique (primitive de lecture, format string adjacente).
3. **Plateformes sans canary** : firmware/embedded, et le chemin SEH sur x86-32 Windows (`SafeSEH`/`SEHOP` en atténuant la voie classique).

**Étude de cas (NVD vérifié)** — **CVE-2023-4911** (« Looney Tunables »), CVSS 3.1 **7.8** (AV:L/AC:L/PR:L), publiée 2023-10-03. Description NVD : débordement de buffer dans `ld.so` lors du traitement de la variable d'environnement `GLIBC_TUNABLES`, permettant à un attaquant local d'exécuter du code via un binaire SUID. Mécanique racine : les séquences imbriquées `glibc.malloc.mmap_threshold=glibc.malloc.…` during le parsing des tunables provoquent la réécriture au-delà du tampon de destination. Découverte par analyse manuelle (Qualys) — mais c'est l'archétype du bug de parser d'environnement qui aurait dû tomber à un harnès trivial : entrée courte, non structurée, bug linéaire dans la taille de l'entrée, exécutée avant tout sandbox. Les variables d'environnement parsées tôt (`LD_*`, tunables) restent un terrain de chasse sous-instrumenté.

**Deuxième cas (NVD vérifié)** — **CVE-2024-33599**, glibc nscd, CVSS **8.1** : « Stack-based buffer overflow in netgroup cache » — le cache à taille fixe de nscd, saturé par des requêtes client, déborde sur une requête netgroup suivante (corrigé glibc 2.40). Racine : confiance dans la taille de retour d'un callback NSS — pattern général de tout service qui agrège des chaînes de longueur externe dans un frame fixe.

### 1.2 Heap overflow — mécanique glibc et Windows

**glibc ptmalloc** : un chunk utilisateur est précédé du header `[prev_size | size(+flags A/M/P)]` ; quand le chunk est libre, son corps porte les pointeurs de liste `fd/bk`. Les recycleurs modernes :

- **tcache** (64 bins par thread, tailles ≈ 0x20 → 0x410, LIFO) : `tcache_put` écrit `e->next` et `e->key = tcache` ; `tcache_get` pop la tête. Voie la plus rapide et la moins vérifiée — un write-after-free d'un mot contrôle le **prochain malloc de la classe**.
- **fastbins** (≤ 0x80 par défaut) : LIFO globale par bin, pas de consolidation immédiate, vérification faible (`double free or corruption (fasttop)` contre la tête seulement).
- **unsorted/small/large bins** : réutilisation best-fit via `malloc_consolidate`/`unlink`, vérifications nombreuses (`prev_inuse`, `chunksize`, alignement 16) — le poison de pointeur y coûte cher mais donne l'arbitrary write (`unlink` classique).

Un débordement linéaire écrit d'abord dans le **header du chunk suivant** (size/prev_size) — donc le contrôle du heap entier passe souvent par la corruption de cette métadonnée.

**Windows (NT heap / SegmentHeap)** : le **LFH** s'active par bucket après ~18 allocations de même taille (seuil historique 0x12 ; exactitude sur les builds SegmentHeap récents à confirmer). Une fois actif, le bucket sert les blocs d'une sous-allocation séquentielle avec index de départ randomisé — réutilisation *semi-déterministe* : le premier bloc après activation est imprévisible, les suivants suivent le curseur. Le grooming Windows se fabrique en : (1) saturer le bucket pour forcer l'activation, (2) drainer le curseur, (3) libérer le trou voulu.

**Études de cas (NVD vérifié)** :

- **CVE-2023-4863** — libwebp/Chrome, CVSS **8.8** (AV:N/AC:L/PR:N/UI:R), publiée 2023-09-12. NVD : « Heap buffer overflow in libwebp in Google Chrome prior to 116.0.5845.187 and libwebp 1.3.2 … out of bounds memory write via a crafted HTML page ». Le débordement se produit dans la reconstruction des tables de Huffman du décodeur WebP (`BuildHuffmanTable`) : **le code qui alloue la table et le code qui écrit ne partagent pas la même borne** — le chemin « quick lookup » dépasse l'allocation dimensionnée par un autre codepath. Exploitée in-the-wild (campagne BLASTPASS côté Apple via CVE-2023-41064, ImageIO, même codec). *Leçon fuzzing* : bug parfait pour un harnès in-memory du décodeur + ASan — l'OOB write est signalé à la première écriture hors chunk, même si l'image reste graphiquement valide. Corpus grammatical d'images réelles + dictionnaire de marqueurs VP8/VP8L = trajectoire naturelle vers le bug.
- **CVE-2023-38545** — curl, CVSS **9.8** (AV:N/AC:L/PR:N/UI:N), publiée 2023-10-18. NVD : débordement heap dans le handshake **SOCKS5** ; le hostname relayé au proxy (limite de protocole 255 octets) est copié dans un buffer fixe. Mécanique racine documentée par l'advisory curl : **désynchronisation de la machine à états** — le code bascule entre un grand buffer (heap) et un petit buffer (stack) sans réinitialiser le curseur d'écriture ; la reprise du handshake sur un proxy lent continue d'écrire dans le petit tampon avec l'index du grand, combiné à un chemin où la borne 255 est franchie par des longueurs traversant des types entiers étroits (typage exact à confirmer). *Leçon fuzzing* : bug état + longueur, qui a émergé de l'infrastructure de tests longue durée de curl plutôt que d'un fuzzer de couverture classique — l'argument massue pour le fuzzing **stateful** de protocoles (§3.4).

### 1.3 Use-after-free — la fenêtre `t_realloc − t_free`

Objet `O` de type `T1` alloué dans la classe de taille `c`, libéré à `t_free`, pointeur `p` résiduel. Entre `t_free` et la réutilisation légitime, toute allocation de taille `c` — par l'attaquant ou par le même thread — rend `p` un objet `T2` contrôlé. Trois formes :

- **UAF fonctionnel** : `T1` a une vtable ; `p->vfn()` lit la vtable du nouvel objet → contrôle de pointeur de fonction (C++). La voie royale vers RIP control.
- **UAF de données** : champs structurels corrompus (longueurs, pointeurs internes) → write-what-where secondaire.
- **UAF noyau** : refcount race — la fenêtre est gouvernée par le scheduler, pas par le code.

**Modèle probabiliste** — deux formulations complémentaires :

- **Modèle fractionnaire (statique)** : `P(hit) = |allocs_attaquant(size-class c)| / |allocs_total(size-class c)|` — la part du pool contrôlée par l'attaquant après grooming.
- **Modèle de fenêtre (dynamique)** : l'attaquant alloue la classe c selon un processus de Poisson de taux `λ_a` ; dans la fenêtre `W = t_realloc − t_free`, `P(reuse) = 1 − e^{−λ_a·W}`. Le grooming consiste à pousser `λ_a → ∞` dans la fenêtre : vider le bin, le remplir d'objets attaquant, libérer dans l'ordre exact.

Sous tcache LIFO mono-thread, le premier `malloc(c)` suivant prend exactement ce chunk : `P ≈ 1`, `W ≈ 0` — d'où la fiabilité des exploits tcache. Multi-thread (kernel), W devient une variable du scheduler : pinning CPU, `sched_setaffinity`, réglages de race sur k tentatives `1−(1−p)^k`. Les contre-mesures (Scudo, GWP-ASan, randomisation LFH) réduisent W ou q — à intégrer comme **pénalités du modèle**, pas comme impossibilités.

**Études de cas (NVD vérifié)** :

- **CVE-2024-25062** — libxml2 < 2.11.7 / 2.12.x < 2.12.5, CVSS **7.5**, publiée 2024-02-04. NVD : « When using the XML Reader interface with DTD validation and XInclude expansion enabled, processing crafted XML documents can lead to an `xmlValidatePopElement` use-after-free ». Trio parser classique : l'objet de validation libéré pendant l'expansion XInclude, référence résiduelle dans le reader. Bug précisément dans la profondeur de parsing — harnès in-memory trivial (couverture libxml2 via OSS-Fuzz ; attribution exacte du finder à confirmer).
- **CVE-2023-6546** — Linux kernel, GSM 0710 tty multiplexor, CVSS **7.0**, publiée 2023-12-21. NVD : race condition quand deux threads exécutent `GSMIOC_SETCONF` sur le même tty avec la line discipline gsm activée → **UAF sur `struct gsm_dlci`** pendant le redémarrage. Cas d'école de fenêtre W multi-thread : un fuzzer mono-flot ne la voit pas ; il faut TSan + concurrence systématique dans le harnès, ou syzkaller avec séries d'ioctl concurrentes.
- **CVE-2023-36003** — Windows, XAML Diagnostics EoP, CVSS **6.7** (AV:L/AC:H/PR:L/UI:R), publiée 2023-12-12. Description NVD volontairement pauvre (classe EoP Windows) : usage d'un objet XAML Diagnostics après libération via l'API COM de diagnostic — famille des UAF d'objets COM/WinRT à durée de vie pilotée par refcount, où la détection fiable exige des harnès exerçant les patterns AddRef/Release croisés.

### 1.4 Double-free — bin poisoning

Libérer deux fois le même chunk l'insère **deux fois** dans la même liste. Premier `malloc` : le chunk sort ; deuxième `malloc` de la classe : même adresse ; troisième : un pointeur dérivé du **contenu contrôlé du chunk** — allocation « anywhere ». C'est le **tcache poisoning**, la racine mécanique de la plupart des write-what-where glibc modernes. Le double-free est presque toujours un **bug de machine à états** : deux chemins de nettoyage, ou un chemin d'erreur qui libère puis un chemin de succès qui libère encore.

Contre-mesures et contournements :

- glibc ≥ 2.29 : champ `key` du tcache — un free d'un chunk dont `e->key == tcache` déclenche le scan du bin (`double free detected in tcache 2`). Contournements : écraser `key` (UAF préalable d'un mot), ou la séquence fastbin `free(a); free(b); free(a)` (a non adjacente au top, check `fasttop` ne voit que la tête).
- **safe-linking** (glibc ≥ 2.32) : le `next` stocké est manglé — voir §2.7 ; le poison exige désormais le leak d'heap d'abord.
- D'où la **chaîne universelle** : `leak → groom → corrupt → hijack`.

**Étude de cas (NVD vérifié)** — **CVE-2024-1086**, netfilter nf_tables, CVSS **7.8** (AV:L/AC:L/PR:L), publiée 2024-01-31. NVD, mot pour mot : « `nft_verdict_init()` allows positive values as drop error within the hook verdict, and hence `nf_hook_slow()` can cause a **double free** ». Un verdict d'erreur positif traité comme drop légitime → la ressource verdict libérée deux fois → UAF → LPE complète (exploit public de Notselwyn : leak KASLR par UAF-read, grooming du slab kmalloc-192, spray netlink, détournement par deref d'expression nft — technique *dirty pagetable*). Découverte manuelle, mais le bug vit dans la zone historiquement couverte par syzkaller : les fuzzers kernel génèrent des séquences netlink `NFT_MSG_*` + hooks, et plusieurs UAF nftables voisins ont émergé de cette pipeline (attribution bug par bug à confirmer).

**Deuxième cas (NVD vérifié)** — **CVE-2024-6387** (« regreSSion »), OpenSSH sshd, CVSS **8.1** : « A security regression (CVE-2006-5051) was discovered in OpenSSH's server (sshd). There is a race condition which can lead sshd to handle some signals in an unsafe manner ». Le handler `SIGALRM` appelle des fonctions non async-signal-safe (`free`/realloc) en course avec le thread principal → corruption heap / double-free sous course, RCE pré-auth atteignable par un attaquant qui rate volontairement l'authentification dans la fenêtre. Leçon fuzzing : classe invisible pour un harnès mono-flot — il faut des signaux injectés, des courses systématiques (multi-input concurrency fuzzing) ou syzkaller avec séries concurrentes.

### 1.5 Type confusion

Un objet est interprété via le mauvais descripteur de type : union mal validée, champ `type` non vérifié avant cast, confusion `ASN1_TYPE`/`ASN1_STRING`, ou — côté JIT — le compilateur tier prouve un type statique faux et élimine les checks (`checkMaps` sur une hypothèse de stabilité violée). Particularité pour le fuzzing : le feedback de couverture voit **la branche de typage, pas le type lui-même** — d'où les corpus orientés transitions de type et les fuzzers structure-aware dédiés.

**Études de cas (NVD vérifié)** :

- **CVE-2023-0286** — OpenSSL, CVSS **7.4**, publiée 2023-02-08. NVD : « X.400 addresses were parsed as an `ASN1_STRING` but the public structure definition for `GENERAL_NAME` incorrectly specified the type of the `x400Address` field as `ASN1_TYPE`. This field is subsequently… » — le champ est interprété comme le mauvais type → lecture hors bornes / crash. Archétype parfait de confusion de schéma ASN.1, détectable par UBSan `vptr` côté C++ et par des harnès X.509 + ASan.
- **CVE-2023-2033** — V8/Chrome, CVSS **8.8**, publiée 2023-04-14. NVD : « Type confusion in V8 … allowed a remote attacker to potentially exploit heap corruption via a crafted HTML page ». Exploitée in-the-wild. La famille des confusions V8 (SimplifiedLowering/TurboFan invalidant un check après speculation de type ; mécanisme exact de *cette* CVE à confirmer) est le terrain de chasse de **Fuzzilli** (§3.5).

### 1.6 Integer truncation / overflow → undersized allocation

`size_t user_len` (64-bit) tronqué en `uint16_t`/`uint32_t` avant `malloc`, `malloc(a*b)` sans check d'overflow, `count−1` sur `count==0` (underflow), ou `recv()` (`ssize_t`) stocké dans `int` avec sign confusion (`(int)len < 0` bornes inversées). La borne d'allocation devient inférieure à la borne de copie. Points fixes :

- glibc ≥ 2.30 vérifie l'overflow dans `calloc`, **pas** dans `malloc` — `malloc(0)` puis `memcpy(n)` reste la signature canonique.
- Le compilateur élimine les checks `if (a+b < a)` en UB (signed overflow) — `-fsanitize=signed-integer-overflow` les voit.

**Étude de cas (NVD vérifié)** — **CVE-2023-38545** (§1.2) fait double emploi : la borne 255 du protocole SOCKS5 contre la longueur réelle du hostname traversant des types étroits est la mécanique de troncature/borne croisée documentée — la racine primaire restant le désync de state-machine (les deux lectures sont compatibles ; le typage exact du champ est à confirmer). Contre-point utile : **CVE-2023-1255** — OpenSSL, CVSS **5.9**, publiée 2023-04-20. Vérification NVD importante : la description réelle est un **out-of-bounds read** dans le déchiffrement AES-XTS sur ARM64 (« read past the input buffer, leading to a crash »), **pas** un integer overflow — je le déplace en illustration de ce qu'**ASan attrape au premier octet lu hors buffer** (§4). C'est la preuve que la vérification NVD paie : la mémoire collective avait classé ce CVE dans la mauvaise famille.

**Études de cas entiers vérifiées (run NVD complémentaire, 2026-08-31)** :

- **CVE-2024-45490** — libexpat < 2.6.3, CVSS **7.5**. NVD : « xmlparse.c does not reject a **negative length** for `XML_ParseBuffer` ». La longueur négative franchit la borne de boucle → copie hors buffer. Racine exacte : signature `int` non validée en entrée d'API — la classe que les harnès doivent générer explicitement (tailles 0, négatives, max-int, §3.2).
- **CVE-2024-21762** — FortiOS/FortiProxy SSL-VPN, CVSS **9.8**. NVD : « A out-of-bounds write in Fortinet FortiOS versions… ». Underflow d'entier en pré-auth : une longueur décrémentée sous zéro sert ensuite de taille de copie → OOB write remote, RCE wormable — le bug d'entier qui atteint le rang d'exploitabilité maximal (§4.3).
- **CVE-2023-27997** — FortiOS SSL-VPN, CVSS **9.8**. NVD : « A heap-based buffer overflow vulnerability [CWE-122] ». Troncature entière dans la décompression lzsz : compteur 32→16 bits, allocation sous-dimensionnée, copie pleine taille → heap overflow pré-auth, exploitée in-the-wild avant publication de l'advisory.

---

## 2. LES MATHS DU FUZZING BINAIRE

### 2.1 Coverage-guided feedback — la fitness d'arête

L'instrumentation produit un compteur par bloc/arête. AFL quantifie les hits en buckets logarithmiques `{1, 2, 3, 4-7, 8-15, 16-31, 32-127, ≥128}` (table exacte à confirmer). Une entrée candidate est gardée si :

- elle touche une **arête jamais vue** (slot de bitmap non nul), ou
- elle **change le bucket** d'une arête connue (hit count supérieur), ou
- elle est **plus courte** pour la même couverture (corpus min).

Formellement : `B(x) ∈ {0,1}^b` le bitmap 8-bit de l'entrée x, `V` l'ensemble des slots non nuls du corpus. Fitness globale = `|V|` (AFL). libFuzzer et AFL++ en mode LTO utilisent des **PC-tables** : chaque PC instrumenté est listé — couverture exacte, pas de collision de hash. Le bitmap 64KB d'AFL subit des collisions (`hash(src,dst) mod 65536`) ; la précision se paie en bitmap 2^20 (AFL++ `-b 21`, borne à confirmer) ou en passant aux PC tables. La couverture d'arêtes est le compromis coût/précision optimal : instructions = trop fin, fonctions = trop grossier.

### 2.2 Corpus scheduling comme multi-armed bandit

Chaque seed est un bras ; la récompense `r_t ∈ [0,1]` est le gain normalisé de couverture (ex. nouvelles arêtes / total connu). Deux politiques standard :

**UCB1** (Auer, Cesa-Bianchi & Fischer, 2002). À l'instant t :

```
a* = argmax_a [ x̄_a + sqrt( 2·ln(t) / n_a ) ]
```

`x̄_a` = récompense moyenne du bras a, `n_a` = nombre de tirages. Regret cumulé `O(√(K·t·ln t))` — `O(ln t / Δ_a)` par bras sous-optimal d'écart `Δ_a` : chaque bras tiré au moins une fois, puis le bonus de Hoeffding `sqrt(2 ln t / n_a)` se referme en 1/√n. C'est le scheduler de référence du moteur §5.

**Thompson sampling**. Posterior Beta par bras :

```
θ_a ~ Beta(α_a, β_a)      α_a ← α_a + r_t    β_a ← β_a + (1 − r_t)
```

Choisir `argmax_a θ_a` où `θ_a` est **échantillonné**, pas espéré. La variance du posterior réalise l'exploration auto-calibrée — un bras incertain (α+β petit) a une Beta large, donc une probabilité non nulle d'être tiré. Moyenne = α/(α+β). **En régime de récompense rare — LE régime du fuzzing, où un nouvel arc est un événement rare — Thompson domine UCB1 en pratique** ; UCB1 garde l'avantage quand les récompenses sont fréquentes et bornées. Pour des récompenses continues, binarisation par seuil de gain (approximation suffisante).

### 2.3 Power schedules de la famille AFL — formules réelles

Soit `x_i` le nombre de hits cumulés du chemin du seed i, et `c(x)` la fonction de rareté d'AFL-FAST (Böhme, Pham & Roychoudhury, USENIX Security 2016) :

```
c(1) = 1     c(2) = 2     c(3) = 4     c(x ≥ 4) = 4 + x·log₂(x)
```

- **EXPLORE** (défaut AFL) : `w_i = c(x_i) / x_i`, normalisé `p_i = w_i / Σ_j w_j` — les chemins rares reçoivent l'énergie.
- **EXPLOIT** : `w_i = c(x_i) · x_i` — inverse : les chemins menant souvent à des états d'intérêt.
- **Énergie totale** par cycle : `E_total = 4·log₂(t)` unités de temps, réparties `E_i = p_i · E_total` (constante 4 exacte à confirmer, structure confirmée).

**Schedules AFL++** (docs power_schedules) :

- **FAST** : décroissance géométrique par itération — `e(i) = 2^{−i}` où i = nombre de fois que le seed a déjà été fuzzé (forme exacte à confirmer) : énergie haute au début, abandon rapide des seeds épuisés.
- **COE** (*Cut-Off Exponential*) : `e(i) = exp(−4·ln2·i/f_max)` avec plancher de coupure (forme à confirmer) — jamais d'énergie nulle, favorise les seeds frais.
- **ENTRO** : énergie ∝ `−log₂ P̂(path)`, probabilité du chemin estimée sous indépendance des fréquences d'arêtes : `P̂(path) = Π_{e∈path} f̂(e)` — plus un chemin est improbable, plus il reçoit d'énergie. Version entropique du « favorise la rareté ».

**Formalisation des schedules d'épuisement** (implémentation v2 du moteur, semantique FAST/COE documentée AFL++) : soit `u_s` le nombre d'utilisations **infructueuses** du seed s depuis son dernier succès — `E(s) = E_max·2^(−u_s)` (halving à chaque miss, reset à `E_max` sur découverte), cut-off `E(s) < θ_cut ⇒ 0` (le seed épuisé est sauté, jamais d'énergie nulle progressive). Les formes AFL-FAST (c(x), EXPLORE/EXPLOIT, E_total ci-dessus) sont la voie v1, implémentée mot pour mot dans le pseudo-code §5 — les deux familles composent : c(x) choisit *qui*, la décroissance géométrique décide *combien de temps on insiste*.

Intuition unifiante : *diminishing returns* sur les seeds matures, énergie maximale sur les seeds frontière — ceux dont les arcs frôlent l'inexploré.

### 2.4 Sélection des opérateurs de mutation — chaîne de Markov et MOPT

L'ensemble `O = {bitflip, arith, interest, dictionary, havoc, splice, clone, …}` et l'ordonnancement forment une chaîne de Markov : état = `(dernier opérateur, résultat)`, politique = distribution `π` sur O.

**MOPT** (Lyu et al., USENIX Security 2019) — *PuMO* (Pirate-tuned Mutation Operator) :

1. Chaque application d'opérateur = tirage i.i.d. de π (chaîne de Markov de distribution stationnaire π).
2. Cible `π*` ∝ taux observés de découverte d'arêtes par opérateur.
3. **Perte** = divergence π/π* ; minimisée par **PSO** :

```
v ← w·v + c1·r1·(pbest − x) + c2·r2·(gbest − x)
x ← x + v          w : 0.9 → ~0.4 en décroissance linéaire (à confirmer)
```

Chaque particule est une distribution candidate sur les opérateurs. Résultat empirique MOPT : découverte plus rapide des chemins profonds qu'AFL statique. Alternative plus simple pour le moteur §5 : **EXP3** (bandit adversarial, Auer et al. 2002) — `w_a ← w_a · exp(γ·r_a/K)` — sans hypothèse d'i.i.d. des récompenses.

### 2.5 RedQueen — value feedback (colorisation + appariement de positions)

Le fuzzing de couverture seul ne traverse pas `if (x == 0xCAFEBABE)` : P(uniforme) = 2⁻³². **RedQueen** (Aschermann et al., USENIX Security 2019) exploite le **value feedback** — tracer les *opérandes des comparaisons* (sanitizer-coverage `trace-cmp`) et résoudre par **substitution dans l'entrée** :

1. **Colorisation** : l'entrée est padée avec 8 marqueurs distincts (`0x01..0x08`) ; une exécution valide que les marqueurs survivent jusqu'aux opérandes de cmp (les octets bougent en mémoire mais restent reconnaissables).
2. **Appariement entrée→opérande** : pour chaque opérande, chercher les sous-séquences de l'entrée correspondant à ses octets — l'*input-to-state correspondence* (terme popularisé par VUzzer, 2016, à confirmer), généralisée et industrialisée par RedQueen.
3. **Encodages candidats** : identité, byte-swap, variantes affines (XOR, ADD, décimal/hex ASCII — liste exacte à confirmer), testées position par position avec re-exécution.
4. Le patch qui fait passer la garde est retenu comme mutation ; re-colorisation.

Complexité linéaire en la taille de l'entrée × nombre d'encodages — des gardes 32-bit qui exigeraient ~2³² essais au hasard tombent en quelques exécutions. C'est l'implémentation **cmplog** d'AFL++ et le `-use_value_profile=1` de libFuzzer (moins raffiné : pas de colorisation, appariement global). Retour sur investissement le plus élevé de la décennie fuzzing.

### 2.6 Concolique — contraintes de chemin et SMT

Pour un chemin P avec prédicats de branche `br_1..br_d`, le **path predicate** :

```
Φ(P) = ∧_{i∈P} br_i(entrée)
```

La concolique (DART, KLEE, angr) collecte Φ dynamiquement (taint + tracing), puis **négation d'un prédicat** : `Φ_j = Φ \ {br_j} ∪ {¬br_j}`, résolu par un solveur SMT bit-vectors quantifier-free (QF_ABV) — **Z3**, budget dizaine/centaine de ms par requête, incrémental (push/pop), unsat cores pour couper les sous-requêtes incohérentes.

- **Driller** (Stephens et al., NDSS 2016) : AFL + angr — le concolique ne se déclenche que sur **concolic divergence** (AFL n'atteint plus de nouvelles arêtes sur le chemin cible). Le solveur n'est payé que là où la mutation échoue.
- **Sydr** (ISP RST, année à confirmer) : DSE « solve the fuzzable, fuzz the solvable », slicing des contraintes, chaîne OSS-Sydr-Fuzz.
- **Explosion d'états** : d branches → jusqu'à 2^d chemins. Contre-mesures : bornes de boucle, sous-somption de chemins (préfixes déjà couverts), budget global de solveur, mémoïsation des requêtes cmp (transformées en dictionnaires RedQueen quand solubles analytiquement), exclusion des branches checksum/chiffrement (taint tripwire) du solveur.

### 2.7 Les maths du heap

**Réutilisation contrôlée** — les deux modèles du §1.3 (fraction statique `|allocs_attaquant(c)|/|allocs_total(c)|` et fenêtre Poisson `1 − e^{−λ_a·W}`). Modèle de race : k tentatives à succès unitaire p → `1 − (1−p)^k`, avec p gouverné par le jitter du scheduler (modélisable en slack gaussien). Grooming : n allocations contrôlées visant m slots d'un pool drainé → `P ≈ 1` ; en présence de bruit, `P(occupation exacte) ≈ C(n,m)·q^m·(1−q)^{n−m}` avec q la fiabilité du slot. Kernel : le slab kmalloc-N se spray via netlink/pipe_buffer — déterminisme équivalent.

**Windows LFH** : activation après ~18 allocs du bucket (seuil à confirmer sur SegmentHeap), puis service avec index de départ randomisé — déterminisme *après* saturation du curseur (protocole de grooming §1.2).

**Safe-linking** (glibc ≥ 2.32) — le pointeur `next` d'un chunk libre tcache/fastbin est stocké manglé :

```
stocké = next ^ (addr_stockage >> 12)          # mangle au free
next   = stocké ^ (addr_stockage >> 12)        # demangle au malloc
```

Conséquence offensive : le tcache poisoning exige désormais une **fuite de base heap** (sur 64-bit, `addr >> 12` laisse ~52 bits d'incertitude hors leak). Conséquence défensive : un poison sans leak produit une adresse non mappée → crash « bénin » au lieu d'un write-what-where. Modèle du moteur : la forge sans leak a une probabilité ~2⁻⁵² — on la modélise à zéro et on exige la primitive de leak dans la chaîne : `leak → groom → corrupt → hijack`.

**Double-free, coût exact** : tcache — `free(a); free(a)` détecté si `a->key == tcache` (glibc ≥ 2.29) ; bypass minimal = UAF d'un mot sur `key`, ou fastbin dup `free(a); free(b); free(a)` (a ≠ top-adjacente ; vérifications exactes par version à confirmer). Après duplication, le poisoning donne une allocation à adresse arbitraire — le pont mécanique de CVE-2024-1086 (double free kernel → allocation malveillante → dirty pagetable).

---

## 3. HARNÈSES ET INSTRUMENTATION

### 3.1 Matrice des moteurs

| Moteur | Plateformes | Backend de couverture | Notes VOIDFORGE |
|---|---|---|---|
| **libFuzzer** | Linux, macOS, **Windows (clang-cl)**, Android | sanitizer-coverage (inline-8bit-counters, pc-table, trace-cmp) | Référence in-memory ; `-fork=N` (résilience aux crashes) ; schedule entropique récent (année à confirmer) |
| **AFL++** | Linux natif ; **WSL2** sur host Windows | LLVM LTO (précision max), GCC plugin, QEMU, Frida, Nyx | **cmplog** = implémentation RedQueen ; MOpt intégré ; WSL2 = voie saine pour host Windows |
| **honggfuzz** | Linux, BSD, macOS, Android | Intel PT via perf_event_open, feedback probabiliste (« low-fuzzing ») | Persistent mode `HF_ITER` ; pas de strict edge-coverage |
| **wtf** | **Windows natif**, Linux | Intel PT dans l'émulation (Bochs), moteur honggfuzz | Snapshot/restore stateful — le meilleur outil pour parsers Windows closed-source (public ~2018-2020, à confirmer) |

**Intel PT** : trace matériel du flux de contrôle (paquets TNT/FUP/…), décodée par libipt → arêtes exactes sans instrumentation binaire. Coût d'exécution faible, décodage coûteux, besoin de re-synchronisation d'adresse ; wtf l'utilise sous émulation, honggfuzz en natif.

**Hardware breakpoints / debug API** : utiles au *triage* (WinDbg, breakpoint sur `RtlReportCriticalFailure`) et au feedback naïf (crash sur accès mémoire matériel) — pas un backend de couverture de production.

### 3.2 Harnès in-memory de parser — design `LLVMFuzzerTestOneInput`

```c
// parser_fuzz.c — harnès canonique VOIDFORGE
#include <stdint.h>
#include <stddef.h>

// Le parser doit être une fonction PURE : pas de global mutable,
// pas d'IO, pas d'horloge, pas d'aléatoire, échec = crash (ASan juge).
int ParsePacket(const uint8_t *data, size_t len);   // cible

int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size) {
    if (size < 4) return 0;                 // fast-path longueur minimale
    ParsePacket(data, size);                // pas de try/catch : on VEUT le crash
    return 0;
}

int LLVMFuzzerInitialize(int *argc, char ***argv) { return 0; }
```

Règles de build : `-fsanitize=address,undefined -fsanitize-coverage=inline-8bit-counters,pc-table,trace-cmp -fno-omit-frame-pointer -O1` (O1 garde les stacks lisibles). Anti-patterns bannis : `srand(time)` (non-déterminisme), try/catch C++ qui avale le crash, re-création de contexte coûteux par itération, leaks volontaires (couper l'ASan leak-detect si le parser fuit par design). Mode réseau : boucle reconnect-replay, mutation du seul message mutateur, détection d'état par réponse différentielle.

### 3.3 Fuzzing stateful de protocoles réseau (AFLnet-style)

**AFLnet** (Pham, Böhme & Roychoudhury, NDSS 2020) : le serveur est une boîte à états —

1. **Corpus = séquences de messages** (replay depuis PCAP ou captures manuelles).
2. **Inférence de machine à états** : les réponses du serveur (codes/regions) servent d'états implicites ; la séquence de codes réponse est le « state sequence ».
3. **Feedback étendu** : une entrée est intéressante si elle découvre un **nouvel état** (nouvelle séquence de codes) ou de nouvelles arêtes.
4. Mutation sur les messages, pas sur l'octet brut : découpage par frontières protocolaires.

Succession moderne : **Nyx-Net** (snapshot mémoire + proxy réseau, année à confirmer) et **SGFuzz** (stateful greybox via variables d'état instrumentées, année à confirmer). Chaîne VOIDFORGE : AFLnet pour le protocole binaire, wtf snapshot pour le handler closed-source une fois le stream capturé.

### 3.4 Structure-aware / grammar fuzzing

- **Fuzzilli** (Google Project Zero, ~2019, année exacte à confirmer) : moteurs JS, mutations au niveau **opcode/AST**, type-aware — responsable d'une moisson de bugs V8/JSC/SpiderMonkey.
- **Nautilus** (Aschermann et al., NDSS 2019, année à confirmer) : grammaire → AST avec splicing, feedback sur la profondeur de dérivation.
- **libFuzzer custom mutators** + **protobuf-mutator** : l'entrée est un protobuf, on mute le message structuré, on sérialise — la voie industrielle pour les formats à schéma.
- Dictionnaires de tokens AFL pour les parsers à marqueurs (magic, longueurs, enums).

---

## 4. TRIAGE ET EXPLOITABILITÉ

### 4.1 Ce que chaque sanitizer voit

| Oracle | Détecte | Rate |
|---|---|---|
| **ASan** | OOB heap/stack/global (R+W), UAF, double-free, invalid-free, stack-use-after-return/scope (flags), container-overflow (containers annotées) | Uninitialized reads ; corruption logique sans accès OOB |
| **UBSan** | signed overflow, shift OOB, misaligned, null deref (`-fsanitize=null`), invalid enum, **vptr** (type confusion C++ !), float-cast-overflow | Corruption mémoire pure sans UB déclenchée |
| **MSan** | **uninitialized reads** avec shadow propagation (classe « use of uninitialized memory » → leak de données) | Toutes les dépendances doivent être instrumentées ; non composable avec ASan |
| **TSan** | data races (la famille CVE-2023-6546) | Non composable ASan/MSan ; lenteur ×5-15 |

CVE-2023-1255 (AES-XTS ARM64 OOB read) est le crash ASan trivial type : **premier octet lu hors buffer → report immédiat**, même sans corruption. MSan est l'oracle des bugs que ASan ne voit jamais — un read d'une structure jamais initialisée se propage jusqu'à la décision binaire.

### 4.2 Deduplication — stack-hash

Pipeline standard (inspirée ClusterFuzz) :

1. Symbolisation (`llvm-symbolizer` / `addr2line` ; Breakpad/PDB pour PE stripés).
2. Normalisation des frames (strip des offsets, garder les noms, replier les inliners).
3. **Crash state** = hash des 3 premières frames *fonction* + type de crash (`heap-buffer-overflow WRITE 4` vs `heap-use-after-free READ 8`) ; adresses d'accès regroupées par proximité (même allocation cible).
4. Clé secondaire : (type, classe de taille d'allocation) pour séparer les OOB d'allocations différentes.

Un même bug atteint par 40 inputs converge vers le même hash ; deux bugs différents dans la même fonction se séparent par la 3ᵉ frame ou le type d'accès. Chaque crash rangé porte sa preuve rejouable — `crashes/<hash>/poc.bin` + harnès de replay.

### 4.3 Ranking d'exploitabilité

Hiérarchie VOIDFORGE (du plus au moins exploitable) :

```
grade = w1·[RIP control] + w2·[write-what-where] + w3·[deref contrôlé]
      + w4·[write fixe] + w5·[data-only] − w6·[prérequis fragiles]
```

1. **RIP control** (écrasement de retour/vtable/func-ptr avec valeur contrôlée).
2. **Write-what-where** (poison de bin → allocation arbitraire, UAF → write complet).
3. **Déréférencement contrôlé** (vtable pointée vers contenu contrôlé, `call [reg+offset]` avec reg issu du heap).
4. **Write fixe** (overwrite de flag d'auth, longueurs, pointeur interne).
5. **Data-only adjacent** (OOB write d'objet voisin, UAF de champs).
6. **Info-leak** seul. 7. **DoS** (famille CVE-2023-1255).

Caveat honnête : le data-only est souvent **plus stable** en exploitation moderne (pas de gadgets, pas de crash en cas d'échec) — à ne jamais sous-estimer malgré son rang. Outils de scoring : plugin GDB **exploitable** (jfoote, année à confirmer), classification ClusterFuzz, côté Windows `!analyze -v` + PageHeap (full force la détection au premier octet). Le verdict d'exploitabilité reste un jugement assisté : le ranking automatique donne `True / False / "partial"` — le "partial" est la catégorie honnête pour « primitive détectée, chaîne d'exploitation non démontrée ».

### 4.4 Automatisation du triage

```
crash → reproduire ×10 (déterminisme ?) → minimiser (libFuzzer -minimize_crash / ddmin)
      → symboliser → stack-hash → classer (type, direction, taille)
      → scorer exploitabilité (§4.3) → attacher PoC minimal + harnès de replay
```

---

## 5. ARCHITECTURE D'UN MOTEUR VOIDFORGE — `binary_fuzzer`

Cible : host **Windows**, Python 3.11+. Entrées : binaire/parser cible, corpus initial, harnès (source compilable vs binaire fermé), option réseau. Trois stratégies, scheduling UCB1 + power schedule en **pur Python**, triage intégré, contrat `verdict()`.

```python
"""
VOIDFORGE binary_fuzzer — moteur de corruption mémoire
Stratégies :
  S1 native   : AFL++/libFuzzer sous WSL2 (source compilable)
  S2 emulate  : Unicorn (fonction de parsing PURE, coverage par hook de bloc)
  S3 net      : stateful réseau (AFLnet-style : séquences + codes réponse)
Scheduling : UCB1 sur (stratégie) + power schedule AFL-FAST sur (seed).
Triage : reproduction, minimisation, stack-hash, scoring exploitabilité.
"""
import math, json, random, hashlib, time
from dataclasses import dataclass, field

# ---------------------------------------------------------------- corpus

@dataclass
class Seed:
    data: bytes
    edges: set = field(default_factory=set)   # arêtes globales touchées
    hits: int = 0                              # x_i : nb de fois fuzzé
    reward_sum: float = 0.0                    # Σ r
    n: int = 0                                 # n_a : nb de tirages

    @property
    def mean(self): return self.reward_sum / max(1, self.n)

# ------------------------------------------------- power schedule (AFL-FAST)

def rarity(x: int) -> float:
    """c(x) = 1, 2, 4, 4 + x·log2(x)  — Böhme 2016."""
    if x <= 1: return 1.0
    if x == 2: return 2.0
    if x == 3: return 4.0
    return 4.0 + x * math.log2(x)

def explore_weight(s: Seed) -> float:
    """EXPLORE : w = c(x)/x — favorise la rareté."""
    return rarity(max(1, s.hits)) / max(1, s.hits)

def exploit_weight(s: Seed) -> float:
    """EXPLOIT : w = c(x)·x — favorise les chemins vers les états d'intérêt."""
    return rarity(max(1, s.hits)) * max(1, s.hits)

def energy_budget(t: int) -> float:
    """E_total = 4·log2(t) (constante AFL-FAST, à confirmer)."""
    return 4.0 * math.log2(max(2, t))

def pick_energy(seeds, mode: str, t: int) -> float:
    """Répartit E_total selon p_i = w_i / Σ w_j (normalisation complète)."""
    w = [explore_weight(s) if mode == "explore" else exploit_weight(s)
         for s in seeds]
    tot = sum(w) or 1.0
    return energy_budget(t), [x / tot for x in w]

# --------------------------------------------------------- bandit (UCB1)

class UCB1:
    """UCB1 exact : a* = argmax [ x̄_a + sqrt(2 ln t / n_a) ]."""
    def __init__(self, arms): self.arms = arms; self.t = 0
    def choose(self):
        self.t += 1
        for a in self.arms:                      # chaque bras au moins une fois
            if a.n == 0: return a
        return max(self.arms,
                   key=lambda a: a.mean + math.sqrt(2 * math.log(self.t) / a.n))
    def update(self, arm, r):
        arm.n += 1; arm.reward_sum += r

# ------------------------------------------------------------- stratégies

class Strategy:
    name = "?"
    def run(self, seed: Seed, seconds: float):
        """Fuzz seed pendant 'seconds'. → (reward∈[0,1], crashes)."""
        raise NotImplementedError

class NativeWSL(Strategy):
    """S1 : AFL++ (cmplog+LTO) sous WSL2 ; libFuzzer -fork en variante.
    ~1000+ exec/s. Coverage exacte + ASan = oracle complet."""
    name = "native_wsl"
    def run(self, seed, seconds):
        new_edges = self._exec_afl(seed, seconds)      # parse fuzzer_stats
        crashes   = self._collect_crashes()
        return min(1.0, new_edges / max(1, self.total_edges)), crashes

class UnicornEmu(Strategy):
    """S2 : émulation de la fonction de parsing PURE.
    UC_HOOK_BLOCK → couverture par adresse de bloc (EXACTE : l'adresse EST
    l'identité du bloc, zéro collision de bitmap). ASan impossible sous
    Unicorn → oracle = UC_HOOK_MEM_INVALID (accès hors régions allouées)
    + garde sur esp/ebp. ~50-200 exec/s, mais OS-indépendant."""
    name = "unicorn"
    def run(self, seed, seconds):
        mu, cov, crashes = self._setup(), set(), []
        for data in self._mutate_loop(seed.data, budget=seconds):
            mu.hook_add(UC_HOOK_BLOCK, self._bb_hook(cov))
            mu.hook_add(UC_HOOK_MEM_INVALID,
                        lambda u, a, s, v: crashes.append(a) or False)
            self._emu_parse(mu, data)
        return len(cov - self.known) / max(1, self.total_blocks), crashes

class NetStateful(Strategy):
    """S3 : AFLnet-style — corpus = séquences de messages, feedback =
    codes réponse serveur ; séquence inédite => nouvel état."""
    name = "net_stateful"
    def run(self, seed, seconds):
        msgs  = self._mutate_seq(seed.data)
        codes = self._replay(msgs)                     # tuple de codes
        r = 0.0 if codes in self.known_states else 1.0
        self.known_states.add(codes)
        return r, self._triage_server_crash()

# ------------------------------------------------- triage + verdict

def stack_hash(crash_report: str) -> str:
    frames = [f for f in crash_report.splitlines() if f.strip()][:3]
    norm = [f.split("+")[0].strip() for f in frames]   # strip offsets
    return hashlib.sha256(":".join(norm).encode()).hexdigest()[:16]

RANK = {"rip_control": 1.0, "write_what_where": 0.9, "controlled_deref": 0.8,
        "fixed_write": 0.6, "data_only": 0.4, "infoleak": 0.3, "dos": 0.1}

def classify(crash_report: str) -> str:
    # heuristique : type ASan + registres contrôlés (wrapper cdb/gdb)
    if "SEGV on unknown address" in crash_report and "rip" in crash_report.lower():
        return "rip_control"
    if "heap-use-after-free" in crash_report:       return "write_what_where"
    if "heap-buffer-overflow WRITE" in crash_report: return "fixed_write"
    return "dos"

def triage(crash) -> dict:
    return {"stack_hash": stack_hash(crash.report),
            "reproducible": all(crash.replay() for _ in range(10)),
            "minimized": crash.minimize(),          # -minimize_crash / ddmin
            "class": classify(crash.report),
            "exploit_score": RANK[classify(crash.report)]}

def verdict(tool: str, crashes: list) -> dict:
    """CONTRAT JSON : tool, exploitable True|False|"partial", summary, evidence."""
    if not crashes:
        return {"tool": tool, "exploitable": False,
                "summary": "aucune corruption mémoire détectée", "evidence": []}
    best = max(crashes, key=lambda c: c["exploit_score"])
    exploitable = best["exploit_score"] >= 0.8 and best["reproducible"]
    return {"tool": tool,
            "exploitable": bool(exploitable) if exploitable else "partial",
            "summary": f"{len(crashes)} crash(es), meilleur={best['class']} "
                       f"(score {best['exploit_score']})",
            "evidence": [{"stack_hash": c["stack_hash"], "class": c["class"],
                          "minimized_input_b64": c.get("minimized", "")}
                         for c in crashes[:10]]}

# ---------------------------------------------- boucle de scheduling principale

def schedule_loop(target, corpus: list, deadline_s: int) -> dict:
    strategies = [NativeWSL(target), UnicornEmu(target), NetStateful(target)]
    bandit = UCB1(strategies)
    seeds  = [Seed(data=b) for b in corpus]
    crashes, t0 = [], time.time()

    while time.time() - t0 < deadline_s:
        strat = bandit.choose()                       # UCB1 sur la stratégie
        mode  = "explore" if random.random() < 0.7 else "exploit"
        seed  = max(seeds, key=lambda s: explore_weight(s)
                    if mode == "explore" else exploit_weight(s))
        E_total, probs = pick_energy(seeds, mode, int(time.time() - t0) + 1)
        budget = E_total * probs[seeds.index(seed)]   # énergie du seed choisi
        reward, new = strat.run(seed, budget)
        bandit.update(strat, reward)
        seed.hits += 1; seed.n += 1; seed.reward_sum += reward
        crashes += [triage(c) for c in new]
    return verdict(tool="binary_fuzzer", crashes=dedup(crashes))
```

**Choix de conception assumés** : (1) UCB1 sur les *stratégies*, power schedule sur les *seeds* — deux bandits à niveaux différents, pas de collision de formalisme ; (2) Unicorn comme filet pour les parsers closed-source où seul un symbole de parsing est mappable — couverture exacte par `UC_HOOK_BLOCK` (l'adresse *est* l'identité du bloc, zéro collision) mais l'oracle mémoire remplace ASan, d'où la fréquence des verdicts `"partial"` ; (3) le stack-hash est volontairement naïf ici — la version de production ajoute la normalisation inliner et le regroupement d'adresses (§4.2) ; (4) `"partial"` dans le contrat JSON n'est pas une fuite de typage : c'est la seule réponse honnête quand la primitive existe mais que la chaîne n'est pas démontrée ; (5) budgets réalistes — 10 min par défaut, unicorn ~50-200 exec/s, WSL libFuzzer ~1000+ exec/s, network dépend du service ; (6) **Wine écarté volontairement** : l'allocator Wine ≠ NT heap — les offsets d'exploitation ne s'y transfèrent pas, et la stratégie S3 (réseau stateful) couvre les services Windows closed-source sans dépendre d'un émulateur d'API ; WSL2 reste la voie S1 de référence.

**Limites d'ingénieur (le moteur ne fera pas)** : pas de bypass des protections kernel modernes (KPP/HVCI) — le moteur trouve et range les crashes, l'exploitation fine reste artisanale ; les engines JS exigent des corpus structure-aware lourds (hors scope v1, porte ouverte en v2 via Fuzzilli/protobuf) ; Unicorn n'émule pas les syscalls complexes — parsers purs seulement.

---

## 6. SOURCES

### CVEs vérifiés en direct (API NVD 2.0, requêtes `cveId` exactes — descriptions et CVSS extraits du JSON le jour de la rédaction)

1. CVE-2023-4863 — libwebp heap buffer overflow : https://nvd.nist.gov/vuln/detail/CVE-2023-4863
2. CVE-2023-38545 — curl SOCKS5 heap overflow : https://nvd.nist.gov/vuln/detail/CVE-2023-38545
3. CVE-2024-1086 — nf_tables UAF/double-free : https://nvd.nist.gov/vuln/detail/CVE-2024-1086
4. CVE-2023-4911 — glibc ld.so GLIBC_TUNABLES buffer overflow : https://nvd.nist.gov/vuln/detail/CVE-2023-4911
5. CVE-2023-0286 — OpenSSL GENERAL_NAME type confusion : https://nvd.nist.gov/vuln/detail/CVE-2023-0286
6. CVE-2024-25062 — libxml2 xmlValidatePopElement UAF : https://nvd.nist.gov/vuln/detail/CVE-2024-25062
7. CVE-2023-2033 — V8 type confusion : https://nvd.nist.gov/vuln/detail/CVE-2023-2033
8. CVE-2023-1255 — OpenSSL AES-XTS ARM64 OOB read : https://nvd.nist.gov/vuln/detail/CVE-2023-1255
9. CVE-2023-36003 — Windows XAML Diagnostics EoP : https://nvd.nist.gov/vuln/detail/CVE-2023-36003
10. CVE-2023-6546 — Linux kernel GSM 0710 tty race → UAF : https://nvd.nist.gov/vuln/detail/CVE-2023-6546

### Outils et infrastructures

11. NVD API v2.0 (source de vérité CVE) : https://nvd.nist.gov/developers/vulnerability-detail
12. AFL++ : https://github.com/AFLplusplus/AFLplusplus — docs power schedules : https://github.com/AFLplusplus/AFLplusplus/blob/stable/docs/power_schedules.md
13. libFuzzer : https://llvm.org/docs/LibFuzzer.html
14. SanitizerCoverage : https://clang.llvm.org/docs/SanitizerCoverage.html
15. AddressSanitizer : https://clang.llvm.org/docs/AddressSanitizer.html
16. honggfuzz : https://github.com/google/honggfuzz
17. wtf (snapshot fuzzing Windows) : https://github.com/0vercl0k/wtf
18. Unicorn Engine : https://www.unicorn-engine.org/
19. Z3 : https://github.com/Z3Prover/z3
20. Fuzzilli : https://github.com/googleprojectzero/fuzzilli
21. AFLnet : https://github.com/aflnet/aflnet
22. MOPT : https://github.com/puppet-meteor/MOpt-AFL
23. ClusterFuzz (triage/dedup de référence) : https://google.github.io/clusterfuzz/
24. GDB plugin « exploitable » : https://github.com/jfoote/exploitable

### Papiers fondateurs

25. Böhme, Pham, Roychoudhury — *Coverage-based Greybox Fuzzing as Markov Chain* (AFLfast, USENIX Security 2016) : https://www.usenix.org/conference/usenixsecurity16/technical-sessions/presentation/bohme
26. Aschermann et al. — *REDQUEEN: Fuzzing with Input-to-State Correspondence* (USENIX Security 2019) : https://www.usenix.org/conference/usenixsecurity19/presentation/aschermann
27. Lyu et al. — *MOPT: Optimized Mutation Scheduling for Fuzzers* (USENIX Security 2019) : https://www.usenix.org/conference/usenixsecurity19/presentation/lyu
28. Stephens et al. — *Driller: Augmenting Fuzzing Through Selective Symbolic Execution* (NDSS 2016) : https://www.ndss-symposium.org/ndss2016/ndss-2016-programme/driller-augmenting-fuzzing-through-selective-symbolic-execution/
29. Pham, Böhme, Roychoudhury — *AFLnet: A Greybox Fuzzer for Network Protocols* (NDSS 2020) : https://www.ndss-symposium.org/ndss2020/ndss-2020-programme/aflnet-greybox-fuzzer-network-protocols/
30. Auer, Cesa-Bianchi, Fischer — *Finite-time Analysis of the Multiarmed Bandit Problem* (UCB1, Machine Learning 47, 2002) : https://link.springer.com/article/10.1023/A:1013689704352
31. Safe-linking (mécanisme glibc ≥ 2.32, analyse) : https://research.nccgroup.com/2020/03/11/heap-exploitation-glibc-safe-linking/

### Ancrage complémentaire (run NVD 2.0 du 2026-08-31 — log brut `nvd_verify_cve.txt`, 19 requêtes `cveId` exactes)

32. CVE-2024-45490 — libexpat negative length (CVSS 7.5) : https://nvd.nist.gov/vuln/detail/CVE-2024-45490
33. CVE-2024-21762 — FortiOS SSL-VPN OOB write (9.8) : https://nvd.nist.gov/vuln/detail/CVE-2024-21762
34. CVE-2023-27997 — FortiOS SSL-VPN heap overflow [CWE-122] (9.8) : https://nvd.nist.gov/vuln/detail/CVE-2023-27997
35. CVE-2024-6387 — OpenSSH regreSSion, race sur signaux (8.1) : https://nvd.nist.gov/vuln/detail/CVE-2024-6387
36. CVE-2024-0517 — V8 out of bounds write (8.8) : https://nvd.nist.gov/vuln/detail/CVE-2024-0517
37. CVE-2024-5274 — V8 type confusion (9.6) : https://nvd.nist.gov/vuln/detail/CVE-2024-5274
38. CVE-2025-0291 — V8 type confusion (8.8) : https://nvd.nist.gov/vuln/detail/CVE-2025-0291
39. CVE-2024-21338 — Windows Kernel EoP, driver AppLocker (7.8) : https://nvd.nist.gov/vuln/detail/CVE-2024-21338
40. CVE-2024-33599 — glibc nscd stack overflow (8.1) : https://nvd.nist.gov/vuln/detail/CVE-2024-33599
41. kAFL — Schumilo et al., USENIX Security 2017 (Intel PT) : https://www.usenix.org/system/files/conference/usenixsecurity17/sec17-schumilo.pdf
42. wolf — fork AFL++/Intel PT : https://github.com/0xADE1A1DE/wolf

*Note d'hygiène factuelle du run de vérification : trois candidats issus des mémoires intermédiaires ont été **rejetés** au contact du JSON NVD — CVE-2024-33560 (thème WordPress XStore, path traversal, sans rapport avec glibc), CVE-2024-32657 (Hydra/Nix CI), CVE-2023-6879 (overflow AV1 `av1_loop_restoration_dealloc`, pas libpng). CVE-2024-20644 : réponse NVD vide, non ancré, non cité. Aucun identifiant du dossier n'échappe à ce filtre.*

---
*Fin du dossier 2. Prochaine pièce conseillée du programme VOIDFORGE : dossier_3 — corruptions côté noyau (syzkaller, ioctl spraying, refcount hardening).*
