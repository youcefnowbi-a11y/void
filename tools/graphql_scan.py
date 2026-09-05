"""TOOL: graphql_scan - GraphQL introspection scanner."""
import json, re
from tools import register
from tools._transport import fetch as _fetch
from tools._exploit_lib import verdict

INTROSPECTION_QUERY = {
    "query": "{__schema{types{name fields{name type{name kind ofType{name}}}}}}"
}

GRAPHQL_PATHS = [
    "/graphql",
    "/_graphql",
    "/api/graphql",
    "/v1/graphql",
    "/graphql/v1",
    "/pg_graphql/v1"
]

SENSITIVE_KEYWORDS = ["admin", "user", "password", "secret", "token", "payment", "delete", "role"]

def _post_graphql(url, query_payload, anon_key=None, timeout=15):
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if anon_key:
        headers["apikey"] = anon_key
        headers["Authorization"] = f"Bearer {anon_key}"
    data = json.dumps(query_payload).encode("utf-8")
    r = _fetch(url, method="POST", headers=headers, body=data, timeout=timeout)
    return r.get("status", -1), r.get("body") or ""

@register(
    name="graphql_introspect",
    desc="Probe GraphQL endpoints for introspection, extract schema types, fields, mutations, and flag sensitive items.",
    params={
        "type": "object",
        "properties": {
            "base": {"type": "string", "description": "Base URL of the target or direct GraphQL endpoint (e.g. https://example.com or https://example.com/graphql)"},
            "anon_key": {"type": "string", "description": "Optional API / anon key (e.g. Supabase pg_graphql apikey header)"}
        },
        "required": ["base"]
    }
)
def graphql_introspect(base, anon_key=None):
    base_clean = base.strip().rstrip("/")
    if not base_clean.startswith("http://") and not base_clean.startswith("https://"):
        base_clean = "https://" + base_clean

    tested = []
    working_path = None
    schema_data = None

    # Ω1.3 (audit-6): If base already contains /graphql, test it directly first
    paths_to_try = list(GRAPHQL_PATHS)
    if any(base_clean.lower().endswith(p) for p in ("/graphql", "/_graphql", "/api/graphql", "/v1/graphql", "/graphql/v1", "/pg_graphql/v1")):
        paths_to_try = [""] + [p for p in GRAPHQL_PATHS if not base_clean.lower().endswith(p)]

    for path in paths_to_try:
        url = base_clean + path if path else base_clean
        status, body = _post_graphql(url, INTROSPECTION_QUERY, anon_key=anon_key)
        tested.append({"path": path or "/", "url": url, "status": status})

        if status == 200 and body:
            try:
                parsed = json.loads(body)
                if isinstance(parsed, dict) and "data" in parsed and "__schema" in (parsed.get("data") or {}):
                    schema_data = parsed["data"]["__schema"]
                    working_path = path or "/"
                    break
            except Exception:
                pass

    if not schema_data or not working_path:
        return verdict("graphql_introspect", False,
                       "GraphQL introspection is disabled or no GraphQL endpoints were detected.",
                       tested_paths=tested)

    raw_types = schema_data.get("types", []) or []
    type_names = []
    mutations = []
    sensitive_items = []
    type_field_map = {}

    for t in raw_types:
        if not isinstance(t, dict):
            continue
        t_name = t.get("name")
        if not t_name:
            continue
        type_names.append(t_name)

        fields = t.get("fields") or []
        field_names = []
        for f in fields:
            if isinstance(f, dict) and f.get("name"):
                fname = f["name"]
                field_names.append(fname)
                f_low = fname.lower()
                for kw in SENSITIVE_KEYWORDS:
                    if kw in f_low:
                        sensitive_items.append({
                            "type": t_name,
                            "field": fname,
                            "matched_keyword": kw
                        })
                        break

        if not t_name.startswith("__"):
            type_field_map[t_name] = field_names

        t_low = t_name.lower()
        if "mutation" in t_low:
            mutations.extend(field_names)
        for kw in SENSITIVE_KEYWORDS:
            if kw in t_low and not t_name.startswith("__"):
                sensitive_items.append({
                    "type": t_name,
                    "field": "*type_name*",
                    "matched_keyword": kw
                })
                break

    # Deduplicate sensitive items
    seen_sens = set()
    dedup_sens = []
    for item in sensitive_items:
        key = (item["type"], item["field"], item["matched_keyword"])
        if key not in seen_sens:
            seen_sens.add(key)
            dedup_sens.append(item)

    user_types = [tn for tn in type_names if not tn.startswith("__")]
    endpoint = (base_clean + working_path) if working_path != "/" else base_clean

    summary = (f"CONFIRMED: GraphQL introspection OPEN at {endpoint} — {len(user_types)} user types, "
               f"{len(mutations)} mutations, {len(dedup_sens)} sensitive field matches")
    return verdict("graphql_introspect", True, summary,
                   evidence=[f"{s['type']}.{s['field']} ({s['matched_keyword']})" for s in dedup_sens[:10]],
                   endpoint=endpoint,
                   working_path=working_path,
                   total_types=len(type_names),
                   user_defined_types_count=len(user_types),
                   types_found=user_types[:30],
                   mutations=mutations[:30],
                   sensitive_fields=dedup_sens[:40],
                   schema_sample={k: type_field_map[k] for k in list(type_field_map.keys())[:15]})
