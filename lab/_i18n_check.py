# Vérif i18n : chaque clé _t() référencée existe dans la table i18n.js
import os, re, sys

SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "web", "frontend", "src")

# 1. toutes les clés de la table
table_src = open(os.path.join(SRC, "i18n.js"), encoding="utf-8").read()
table_keys = set(re.findall(r"^\s{2}([a-z0-9_]+):\s*\{", table_src, re.M))

# 2. toutes les clés référencées dans les composants
refs = {}
for root, _, files in os.walk(SRC):
    for fn in files:
        if not fn.endswith((".jsx", ".js")) or fn == "i18n.js":
            continue
        p = os.path.join(root, fn)
        src = open(p, encoding="utf-8").read()
        for m in re.finditer(r"_t\(\s*['\"]([a-z0-9_]+)['\"]", src):
            refs.setdefault(m.group(1), set()).add(
                os.path.relpath(p, SRC))

missing = {k: v for k, v in refs.items() if k not in table_keys}
if missing:
    print(f"CLÉS MANQUANTES ({len(missing)}):")
    for k, files in sorted(missing.items()):
        print(f"  {k}  ← {', '.join(sorted(files))}")
    sys.exit(1)
print(f"i18n OK — {len(refs)} clés référencées, toutes présentes "
      f"(table: {len(table_keys)})")

# 3. chaînes FR codées en dur (hors commentaires) — heuristique
#    mots français courants hors table
fr_words = re.compile(
    r"['\"`“](?=[^'\"`]*\b)(?:[Aa]ctionnées?|[Bb]atterie|[Cc]ampagne|[Dd]émarrer"
    r"|[Ee]nvoyé|[Ff]ichier|[Gg]énéral|[Hh]istorique|[Ii]gnorer|[Ll]ancée"
    r"|[Mm]odèle|[Nn]on|[Oo]utils|[Pp]aramètres|[Rr]apport|[Ss]auvegardé"
    r"|[Tt]éléchargement|[Vv]érifié|[Éé]chec)\b[^'\"`]*['\"`“]")
hardcoded = []
for root, _, files in os.walk(SRC):
    for fn in files:
        if not fn.endswith((".jsx", ".js")) or fn == "i18n.js":
            continue
        p = os.path.join(root, fn)
        for i, line in enumerate(open(p, encoding="utf-8"), 1):
            if "//" in line or "/*" in line or "*" in line[:2]:
                continue
            if fr_words.search(line):
                hardcoded.append(f"{os.path.relpath(p, SRC)}:{i}: {line.strip()[:90]}")
if hardcoded:
    print(f"\nFR CODÉ EN DUR ({len(hardcoded)}):")
    for h in hardcoded[:15]:
        print(" ", h)
else:
    print("zéro chaîne FR codée en dur (hors commentaires)")
