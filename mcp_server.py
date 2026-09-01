"""VOIDFORGE :: MCP server - exposes the entire tool registry over stdio JSON-RPC.
Any MCP-capable AI client (Claude Desktop, Copilot, etc.) can drive VOIDFORGE."""
import sys, json, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import tools as reg

reg.discover()

def rpc_result(id_, result=None, error=None):
    resp = {"jsonrpc": "2.0", "id": id_}
    if error: resp["error"] = error
    else: resp["result"] = result
    return json.dumps(resp)

def main():
    for line in sys.stdin:
        line = line.strip()
        if not line: continue
        try:
            msg = json.loads(line)
        except Exception:
            continue
        method = msg.get("method", "")
        id_ = msg.get("id")
        if method == "initialize":
            print(rpc_result(id_, {"protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "voidforge", "version": "0.2"}}), flush=True)
        elif method == "notifications/initialized":
            pass
        elif method == "tools/list":
            tools = [{"name": t["name"], "description": t["desc"],
                      "inputSchema": t["params"]} for t in reg.all_tools()]
            print(rpc_result(id_, {"tools": tools}), flush=True)
        elif method == "tools/call":
            params = msg.get("params", {})
            name = params.get("name")
            args = params.get("arguments") or {}
            try:
                out = reg.execute(name, args)
                print(rpc_result(id_, {"content": [{"type": "text", "text": out[:18000]}]}), flush=True)
            except KeyError as ex:
                print(rpc_result(id_, None, {"code": -32602, "message": str(ex)}), flush=True)
            except Exception as ex:
                print(rpc_result(id_, None, {"code": -32603, "message": str(ex)[:200]}), flush=True)
        elif method == "ping":
            print(rpc_result(id_, {}), flush=True)
        elif id_ is not None:
            print(rpc_result(id_, None, {"code": -32601, "message": f"unknown {method}"}), flush=True)

if __name__ == "__main__":
    main()
