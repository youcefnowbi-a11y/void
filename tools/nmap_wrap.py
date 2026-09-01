"""TOOL: nmap_wrap - Nmap integration wrapper with structured output and fallback."""
import json, re, subprocess, os, xml.etree.ElementTree as ET
from tools import register
from sandbox.runner import run

NMAP_CANDIDATES = [
    "nmap",
    r"C:\Program Files (x86)\Nmap\nmap.exe",
    r"C:\Program Files\Nmap\nmap.exe",
    "/usr/bin/nmap"
]

def _find_nmap():
    for c in NMAP_CANDIDATES:
        try:
            r = subprocess.run([c, "--version"], capture_output=True, timeout=10,
                               encoding="utf-8", errors="replace")
            if r.returncode == 0 or "Nmap" in (r.stdout or ""):
                return c
        except Exception:
            continue
    return None

def _parse_ports_arg(ports_str):
    if not ports_str:
        return None
    res = []
    for part in ports_str.split(","):
        part = part.strip()
        if "-" in part:
            try:
                start, end = part.split("-", 1)
                res.extend(range(int(start), min(int(end) + 1, 65536)))
            except Exception:
                pass
        else:
            try:
                res.append(int(part))
            except Exception:
                pass
    return res or None

def _parse_nmap_xml(xml_text):
    idx = xml_text.find("<nmaprun")
    if idx == -1:
        return []
    xml_clean = xml_text[idx:]
    end_idx = xml_clean.rfind("</nmaprun>")
    if end_idx != -1:
        xml_clean = xml_clean[:end_idx + len("</nmaprun>")]

    try:
        root = ET.fromstring(xml_clean)
    except Exception:
        return []

    hosts = []
    for host_el in root.findall("host"):
        addr_el = host_el.find("address")
        ip = addr_el.attrib.get("addr") if addr_el is not None else "unknown"
        status_el = host_el.find("status")
        status = status_el.attrib.get("state") if status_el is not None else "unknown"

        hostnames = []
        hostnames_el = host_el.find("hostnames")
        if hostnames_el is not None:
            for hn in hostnames_el.findall("hostname"):
                if "name" in hn.attrib:
                    hostnames.append(hn.attrib["name"])

        open_ports = []
        ports_el = host_el.find("ports")
        if ports_el is not None:
            for p in ports_el.findall("port"):
                portid = int(p.attrib.get("portid", 0))
                proto = p.attrib.get("protocol", "tcp")
                state_el = p.find("state")
                state = state_el.attrib.get("state") if state_el is not None else "unknown"
                svc_el = p.find("service")
                svc_name = svc_el.attrib.get("name", "") if svc_el is not None else ""
                product = svc_el.attrib.get("product", "") if svc_el is not None else ""
                version = svc_el.attrib.get("version", "") if svc_el is not None else ""
                extrainfo = svc_el.attrib.get("extrainfo", "") if svc_el is not None else ""

                if state == "open":
                    open_ports.append({
                        "port": portid,
                        "protocol": proto,
                        "state": state,
                        "service": svc_name,
                        "product": product,
                        "version": version,
                        "extrainfo": extrainfo
                    })

        hosts.append({
            "ip": ip,
            "status": status,
            "hostnames": hostnames,
            "open_ports": open_ports
        })
    return hosts

@register(
    name="nmap_scan",
    desc="Execute Nmap port and service scan with XML parsing, with automatic fallback to async socket scanner.",
    params={
        "type": "object",
        "properties": {
            "target": {"type": "string", "description": "Target hostname or IP address"},
            "scan_type": {
                "type": "string",
                "enum": ["quick", "service", "full"],
                "default": "quick",
                "description": "quick: fast port scan (-F), service: banner/version probe (-sV), full: version + default scripts (-sV -sC)"
            },
            "ports": {"type": "string", "description": "Optional port specification, e.g. '80,443,8080' or '1-1000'"},
            "timeout_min": {"type": "integer", "default": 10, "description": "Scan timeout in minutes"}
        },
        "required": ["target"]
    }
)
def nmap_scan(target, scan_type="quick", ports=None, timeout_min=10):
    nmap_bin = _find_nmap()

    # Fallback to internal port_scan if nmap binary is not available
    if not nmap_bin:
        try:
            from tools.port_scan import port_scan_sync
            parsed_ports = _parse_ports_arg(ports)
            fallback_res = port_scan_sync(host=target, mode="top" if not parsed_ports else None, ports=parsed_ports)
            fallback_data = json.loads(fallback_res) if isinstance(fallback_res, str) else fallback_res
            return json.dumps({
                "target": target,
                "scan_type": scan_type,
                "nmap_used": False,
                "note": "nmap binary not found, used internal socket scanner fallback",
                "hosts": [{
                    "ip": target,
                    "status": "up",
                    "hostnames": [],
                    "open_ports": fallback_data.get("open", [])
                }]
            }, ensure_ascii=False, indent=1)
        except Exception as ex:
            return json.dumps({
                "error": f"Nmap not found and fallback failed: {str(ex)}",
                "target": target
            })

    # Build Nmap command
    cmd = [nmap_bin]
    if scan_type == "quick":
        if ports:
            cmd.extend(["-T4", "--open", "-p", str(ports), "-oX", "-"])
        else:
            cmd.extend(["-T4", "-F", "--open", "-oX", "-"])
    elif scan_type == "service":
        cmd.extend(["-sV", "-T4", "--open", "-oX", "-"])
        if ports:
            cmd.extend(["-p", str(ports)])
    elif scan_type == "full":
        cmd.extend(["-sV", "-sC", "-T4", "--open", "-oX", "-"])
        if ports:
            cmd.extend(["-p", str(ports)])
    else:
        cmd.extend(["-T4", "--open", "-oX", "-"])
        if ports:
            cmd.extend(["-p", str(ports)])

    # R5-18: pas de leading-dash / chars hors hostname — l'argument-injection
    # via --datadir/-iL passe par une cible qui ressemble à un flag nmap
    if not re.match(r"^[A-Za-z0-9._-]+$", target) or target.startswith("-"):
        return "TOOL ERROR [ARGS]: cible invalide"
    cmd.append(target)

    code, output = run(cmd, timeout_minutes=int(timeout_min))
    hosts = _parse_nmap_xml(output)

    # Flatten open ports across all detected hosts
    all_open_ports = []
    for h in hosts:
        for p in h.get("open_ports", []):
            all_open_ports.append({
                "host": h.get("ip"),
                **p
            })

    return json.dumps({
        "target": target,
        "scan_type": scan_type,
        "nmap_used": True,
        "exit_code": code,
        "hosts_found": len(hosts),
        "hosts": hosts,
        "open_ports": all_open_ports,
        "raw_tail": output[-400:] if not hosts else ""
    }, ensure_ascii=False, indent=1)
