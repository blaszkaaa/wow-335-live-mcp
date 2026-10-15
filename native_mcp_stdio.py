"""Compatible MCP stdio entry point for the safe visual-only WoWMCPData add-on.

Preserve this executable filename so existing local MCP clients can reconnect
without pointing to a new binary. All tool calls use the screenshot decoder in
server.py. The old native DLL transport is never started.
"""
from server import TOOLS, reply, main, read_best_wow_live_data


if __name__ == "__main__":
    main()
