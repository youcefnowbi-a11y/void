"""TOOL: port_scan - fast async TCP port scanner."""
import asyncio, json
from tools import register

TOP_PORTS = [21,22,23,25,53,80,110,111,135,139,143,443,445,993,995,1723,3306,
             3389,5432,5900,6379,8080,8443,8888,9090,27017,5984,6443,9000,5985]

async def _scan(host, mode="top", ports=None, timeout=1.5):
    plist = {"top": TOP_PORTS,
             "web": [80,443,8080,8443],
             }.get(mode, ports or TOP_PORTS)
    open_ports = []
    sem = asyncio.Semaphore(500)
    async def check(p):
        async with sem:
            try:
                fut = asyncio.open_connection(host, p)
                reader, writer = await asyncio.wait_for(fut, timeout=timeout)
                open_ports.append({"port": p, "state": "open"})
                writer.close()
            except Exception:
                pass
    await asyncio.gather(*(check(p) for p in plist))
    return sorted(open_ports, key=lambda x: x["port"])

@register(name="port_scan_sync",
          desc="Sync wrapper: fast top-ports scan of a host (async internally, no nmap binary needed). Use for quick triage; prefer nmap_scan when full service/version detection matters.",
          params={"type":"object","properties":{
              "host":{"type":"string"},"mode":{"type":"string"},
              "ports":{"type":"array","items":{"type":"integer"}}},
              "required":["host"]})
def port_scan_sync(host, mode="top", ports=None):
    result = asyncio.run(_scan(host, mode, ports))
    return json.dumps({"host": host, "mode": mode, "open": result}, indent=1)
