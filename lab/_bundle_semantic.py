# Vérif sémantique bundle (les strings survivent au minify, pas les exprs)
import os

FE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                  "web", "frontend")
js = ""
for fn in os.listdir(os.path.join(FE, "dist", "assets")):
    if fn.startswith("index-") and fn.endswith(".js"):
        js = open(os.path.join(FE, "dist", "assets", fn), encoding="utf-8").read()

# strings/idiomes qui survivent
checks = {
    # C2: le join colonné laisse `:` + concat — cherche le pattern minifié :
    # soit `+":"+` soit le literal ':' dans le voisinage de .k
    "C2 colon join (minified +':'+)": '+":"+n.v' in js or "n.k+':'+n.v" in js.replace(" ", ""),
    # C4: la string critical du ternaire severity
    "C4 severity 'critical'": "critical" in js,
    # M1: la clé max_tool_rounds dans le POST
    "M1 max_tool_rounds POST": "max_tool_rounds" in js,
    # M2: d.elapsed lu
    "M2 d.elapsed": ".elapsed" in js,
    # M4: la string 'chat' du guard origin
    "M4 origin chat": "chat" in js,
}
for label, present in checks.items():
    print(f"  {'present' if present else 'ABSENT'}  {label}")

# diagnostic : montre le contexte minifié autour de max_tool_rounds
i = js.find("max_tool_rounds")
if i > 0:
    print("\ncontexte max_tool_rounds:")
    print("  ...", js[i-80:i+80].replace("\n", " "), "...")
i2 = js.find(".elapsed")
if i2 > 0:
    print("\ncontexte elapsed:")
    print("  ...", js[i2-80:i2+80].replace("\n", " "), "...")
