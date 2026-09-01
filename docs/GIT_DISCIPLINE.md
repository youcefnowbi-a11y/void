# Git — discipline pour les agents VOIDFORGE

**Repo** : `C:\Users\youcef cheriet\D\VOIDFORGE\.git` (branche `main`, baseline `ecc2464` = état vert 122/122).
⚠️ Le home a AUSSI un repo git parent qui ne sert à rien — toujours travailler DEPUIS le dossier VOIDFORGE (le repo interne gagne toujours).

## Pourquoi
Les fixes de vague ont édité des fichiers CONCURREMMENT (clusters parallèles) sans base de comparaison : « file changed since read », tests pollués, impossible de dire qui a touché quoi. Le repo rend chaque changement **visible, réversible, attribuable**.

## Les règles
1. **Avant de commencer** : `git status --short` — si le working tree est sale, tu travailles sur des changements non commités d'un autre agent : NE TOUCHE PAS, signale-le dans ton rapport.
2. **Ton périmètre** : ne modifie QUE les fichiers listés dans ta mission. `git diff --stat` à la fin doit montrer uniquement ces fichiers.
3. **En cas de collision** (`file changed since read`) : re-LIS le fichier, intègre la version actuelle, ré-applique ton fix à elle. Jamais d'écrasement à l'aveugle.
4. **Après chaque unité de travail cohérente** (fix, cluster, réconciliation) :
   ```powershell
   git add <tes fichiers>
   git commit -m "lane X: <résumé> (tests: N/N)"
   ```
5. **Jamais** de `git add -A` si d'autres agents tournent (tu commitrerais leurs demi-édits). `git add <fichiers précis>`.
6. **Jamais** de `git reset --hard` / `git checkout -- .` global sans accord de l'opérateur.
7. **Avant de supprimer du code** : `git log -p -- <fichier>` montre l'histoire — vérifie ce que tu supprimes n'est pas une dépendance vivante.
8. **Diff de revue** : pour qu'un relecteur voie TON travail : `git diff <baseline>..HEAD -- <fichiers>`.

## Fichiers hors historique (voir .gitignore)
missions/, uploads/, *.db, bandit.json, *.log — l'état runtime ne pollue pas le code.
