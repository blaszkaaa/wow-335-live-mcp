"""Lightweight, DLL-only MCP stdio bridge for WoW Connect.

Runs as a separate process, started by an MCP client. Does not own the game
pipe or create a screenshot: it uses the authenticated, loopback desktop hub.
For ChatGPT remote connectors a separately configured secure MCP tunnel is
still required; this executable does not expose a public network service.
"""
import json
import sys
from native_bridge.hub import NativeHubClient

PROTOCOL = "2025-06-18"


def text_result(data):
    return {"content": [{"type": "text", "text": json.dumps(data, ensure_ascii=False)}]}


def native_snapshot():
    hub = NativeHubClient.discover()
    if hub is None:
        return {"available": False, "source": "native_dll", "data": None,
                "reason": "Nie znaleziono WoW Connect. Uruchom aplikację i WoW z DLL."}
    snapshot = hub.snapshot()
    if snapshot is None:
        return {"available": False, "source": "native_dll", "data": None,
                "reason": "Lokalny odbiornik DLL jest niedostępny. Uruchom ponownie WoW Connect."}
    data = snapshot.get("data")
    char = data.get("character") if isinstance(data, dict) else None
    if not (snapshot.get("available") is True and
            snapshot.get("session") != "native-demo" and
            isinstance(char, dict) and char.get("name") and char.get("name") != "Demo"):
        return {"available": False, "source": "native_dll", "data": None,
                "age_seconds": snapshot.get("age_seconds"),
                "reason": "Brak prawdziwych, świeżych danych DLL. W WoW wpisz /wowmcpnative."}
    return {**snapshot, "transport": "desktop_gui_hub"}


TOOLS = [
    {"name": "wow_status",
     "description": "DLL telemetry and native game connection status from WoW Connect. Read only.",
     "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False}},
    {"name": "read_wow_live_data",
     "description": "Current real WoW 3.3.5a character, quests, bags, talents, target, spells and NPC interactions from native DLL telemetry; no RGB strip.",
     "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False}},
    {"name": "wow_native_status",
     "description": "Raw local DLL pipe status including age and accepted frames.",
     "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False}},
]


def reply(request):
    if not isinstance(request, dict):
        return None
    method = request.get("method")
    request_id = request.get("id")
    # JSON-RPC notifications do not receive responses.
    if request_id is None:
        return None
    try:
        if method in ("initialize", "tools/list", "tools/call"):
            hub = NativeHubClient.discover()
            if hub is not None:
                hub.announce_mcp()
        if method == "initialize":
            result = {"protocolVersion": PROTOCOL, "capabilities": {"tools": {}},
                      "serverInfo": {"name": "wow-335-native-mcp", "version": "0.6.0"}}
        elif method == "ping":
            result = {}
        elif method == "tools/list":
            result = {"tools": TOOLS}
        elif method == "tools/call":
            params = request.get("params") or {}
            name = params.get("name")
            if name == "read_wow_live_data":
                result = text_result(native_snapshot())
            elif name in ("wow_status", "wow_native_status"):
                hub = NativeHubClient.discover()
                stat = hub.status() if hub is not None else None
                result = text_result(stat if stat is not None else {
                    "available": False, "reason": "WoW Connect jest niedostępny."})
            else:
                return {"jsonrpc": "2.0", "id": request_id,
                        "error": {"code": -32602, "message": "Unknown tool"}}
        else:
            return {"jsonrpc": "2.0", "id": request_id,
                    "error": {"code": -32601, "message": "Method not found"}}
        return {"jsonrpc": "2.0", "id": request_id, "result": result}
    except Exception as exc:
        return {"jsonrpc": "2.0", "id": request_id, "result": {
            "content": [{"type": "text", "text": "MCP bridge error: " + str(exc)[:300]}],
            "isError": True}}


def main():
    for line in sys.stdin:
        try:
            request = json.loads(line)
            response = reply(request)
            if response is not None:
                sys.stdout.write(json.dumps(response, ensure_ascii=True, separators=(",", ":")) + "\n")
                sys.stdout.flush()
        except (ValueError, UnicodeError, TypeError) as exc:
            print("Invalid MCP request: " + str(exc), file=sys.stderr)


if __name__ == "__main__":
    main()
