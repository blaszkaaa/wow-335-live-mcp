"""Ensure the existing MCP stdio executable reads the RGB addon, not DLL."""
import json
import unittest
from unittest import mock
import native_mcp_stdio as mcp
import server


class VisualMcpStdioTests(unittest.TestCase):
    def test_initialize_and_catalog(self):
        with mock.patch.object(server.NativeHubClient, "discover", return_value=None):
            initialized = mcp.reply({"jsonrpc": "2.0", "id": 1, "method": "initialize"})
            self.assertEqual(initialized["result"]["serverInfo"]["name"], "wow-335-live-mcp")
            listed = mcp.reply({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        names = {item["name"] for item in listed["result"]["tools"]}
        self.assertIn("read_wow_live_data", names)
        self.assertIn("capture_wow", names)

    def test_stdio_visual_tool_is_correctly_routed(self):
        visual = {"available": True, "source": "WoW addon visual data strip",
                  "data": {"character": {"name": "Kovaienko"}}}
        with mock.patch.object(server.NativeHubClient, "discover", return_value=None), \
             mock.patch.object(server, "live_game_data", return_value=visual):
            message = mcp.reply({"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                                 "params": {"name": "read_wow_live_data", "arguments": {}}})
        body = json.loads(message["result"]["content"][0]["text"])
        self.assertEqual(body["data"]["character"]["name"], "Kovaienko")

    def test_notifications_do_not_reply(self):
        self.assertIsNone(mcp.reply({"jsonrpc": "2.0", "method": "notifications/initialized"}))
