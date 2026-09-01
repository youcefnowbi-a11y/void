"""TOOL: cn_fingerprint — CN-battlefield stack fingerprints + default creds.

Dictionaries from the reverse-skill src-hunter corpus (WooYun-derived:
22k+ real cases), copied into tools/data/cn_fingerprints/. The tool gives
the agent a product-level lookup: fingerprint markers, high-risk default
paths, and default credentials for Chinese OA/CMS/middleware/network-gear
stacks that international dicts (SecLists, H1) do not cover.

op=list                -> every known product id + name
op=fingerprint <id>    -> markers (headers/URL patterns/page traits)
op=creds <id>          -> default credentials table (markdown rows)
op=search <keyword>    -> substring match over product names (zh+en)
"""
import json
import os
import re

from tools import register

_DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "data", "cn_fingerprints")
_FP_FILE = os.path.join(_DATA, "chinese-srcfingerprints.md")
_CREDS_FILE = os.path.join(_DATA, "default-credentials-cn.md")

_PROD = re.compile(r"(?m)^###\s+(\d+\.\d+)\s+(.+)$")
_ID = re.compile(r"^[a-z0-9_]{2,40}$")


def _slug(name, num, prefix, taken):
    """Stable id: the ASCII part of the product name (parens included —
    '致远 OA（Seeyon）' -> 'seeyon'), else a numbered fallback keyed by file.
    Renvoie (sid, renamed) — renamed=True si un suffixe de collision a été posé."""
    m = re.search(r"[A-Za-z][A-Za-z0-9 .\-/]{2,}", name)
    s = ""
    if m:
        s = re.sub(r"[^A-Za-z0-9]+", "_", m.group(0)).strip("_").lower()[:30]
    sid = s or f"{prefix}_{num.replace('.', '_')}"
    base, i = sid, 2
    while sid in taken:
        sid = f"{base}_{i}"
        i += 1
    taken.add(sid)
    return sid, sid != base


def _load(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""


def _sections(path, prefix, taken=None):
    """product_id -> ({id: {name, num, body}}, renamed_ids) from ### X.Y Name headers.
    R3-10: `taken` partagé entre fps et crs — un même slug 'seeyon' ne peut plus
    pointer vers des produits différents selon le fichier d'origine."""
    text = _load(path)
    if not text:
        return {}, set()
    if taken is None:
        taken = set()
    out, renamed = {}, set()
    matches = list(_PROD.finditer(text))
    for i, m in enumerate(matches):
        num, name = m.group(1), m.group(2).strip()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[m.end():end].strip()
        sid, was_renamed = _slug(name, num, prefix, taken)
        if was_renamed:
            renamed.add(sid)
        out[sid] = {"name": name, "num": num, "body": body}
    return out, renamed


@register(
    name="cn_fingerprint",
    desc="Chinese-battlefield stack intelligence: fingerprints, high-risk default "
         "paths and default credentials for CN OA/CMS/middleware/network gear "
         "(Seeyon, Tongda, Yonyou, Landray, Weaver, Hikvision, Ruijie, ... — "
         "WooYun 22k-case derived, absent from SecLists). Use when the target "
         "looks like a Chinese government/enterprise stack: op=list to browse, "
         "op=fingerprint <id> for markers, op=creds <id> for default accounts, "
         "op=search <keyword> (zh or en) to find the product id.",
    params={
        "type": "object",
        "properties": {
            "op": {"type": "string",
                   "description": "list | fingerprint | creds | search"},
            "product_id": {"type": "string",
                           "description": "product id from op=list (e.g. seeyon, tongda_oa)"},
            "keyword": {"type": "string",
                        "description": "search keyword for op=search (zh or en substring)"},
        },
        "required": ["op"],
    },
    danger="safe",
)
def cn_fingerprint(op: str, product_id: str = "", keyword: str = "") -> str:
    # R3-10: un seul `taken` pour les DEUX fichiers — slugs cross-file uniques;
    # R3-37: les ids artificiels (suffixes de collision posés au parse) sont
    # tracés dans renamed_fps/crs, op=list ne les cache plus par pattern.
    taken = set()
    fps, renamed_fps = _sections(_FP_FILE, "fp", taken)
    crs, renamed_crs = _sections(_CREDS_FILE, "cr", taken)
    product_id = (product_id or "").strip().lower()

    if op == "list":
        ids = sorted(set(fps) | set(crs))
        # R3-37: on ne cache que les artefacts de collision tracés au parse —
        # plus de filtre endswith qui tuait des ids légitimes finissant par
        # un chiffre (ex: tongda_oa_2017)
        hidden = renamed_fps | renamed_crs
        rows = [{"id": i, "name": (fps.get(i) or crs.get(i))["name"]}
                for i in ids if i not in hidden]
        return json.dumps({"count": len(rows), "products": rows},
                          ensure_ascii=False, indent=1)

    if op == "search":
        kw = (keyword or "").strip().lower()
        if not kw:
            return "TOOL ERROR [ARGS]: op=search requires keyword"
        hits = []
        for src in (fps, crs):
            for sid, v in src.items():
                if kw in v["name"].lower() or kw in v["body"].lower()[:4000]:
                    if sid not in [h["id"] for h in hits]:
                        hits.append({"id": sid, "name": v["name"]})
        return json.dumps({"query": kw, "matches": hits[:30]},
                          ensure_ascii=False, indent=1)

    if op in ("fingerprint", "creds"):
        if not product_id or not _ID.match(product_id):
            return "TOOL ERROR [ARGS]: provide product_id from op=list"
        src, label = ((fps, "fingerprint") if op == "fingerprint" else (crs, "default creds"))
        sec = src.get(product_id)
        if not sec:
            alt = [k for k in src if k.startswith(product_id)]
            if alt:
                sec = src[alt[0]]
            else:
                return json.dumps(
                    {"error": f"no {label} section for '{product_id}'",
                     "known": sorted(src)[:40]}, ensure_ascii=False)
        # cap the section to keep the tool output bounded
        return f"# {sec['name']} — {label}\n\n{sec['body'][:6000]}"

    return "TOOL ERROR [ARGS]: op must be list | fingerprint | creds | search"
