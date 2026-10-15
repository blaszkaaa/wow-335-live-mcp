"""Native-only MCP stdio bridge protocol and loopback transport tests."""
import json
import unittest
from unittest import mock

import native_mcp_stdio as mcp


class NativeMcpStdioTests(unittest.TestCase):
    def test_initialize_and_tool_catalog(self):
        hub = mock.Mock()
        with mock.patch.object(mcp.NativeHubClient, "discover", return_value=hub):
            hello = mcp.reply({"jsonrpc": "2.0", "id": 1,
                               "method": "initialize", "params": {}})
            self.assertEqual(hello["result"]["protocolVersion"], "2025-06-18")
            self.assertEqual(hello["result"]["serverInfo"]["name"], "wow-335-native-mcp")
            listed = mcp.reply({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
            names = [tool["name"] for tool in listed["result"]["tools"]]
            self.assertIn("read_wow_live_data", names)
            self.assertIn("wow_native_status", names)
            self.assertNotIn("capture_wow", names)
            self.assertEqual(hub.announce_mcp.call_count, 2)

    def test_notification_and_unknown_method(self):
        self.assertIsNone(mcp.reply({"jsonrpc": "2.0",
                                     "method": "notifications/initialized"}))
        self.assertEqual(mcp.reply({"jsonrpc": "2.0", "id": 7, "method": "ping"})["result"], {})
        self.assertEqual(mcp.reply({"jsonrpc": "2.0", "id": 8,
                                    "method": "method/unknown"})["error"]["code"], -32601)

    def test_native_live_tool_returns_real_character(self):
        hub = mock.Mock()
        hub.snapshot.return_value = {
            "available": True, "session": "char-01", "age_seconds": 1.1,
            "source": "experimental native DLL named pipe",
            "data": {"character": {"name": "Kovaienko", "level": 25},
                     "quests": [{"title": "Quest A"}]},
        }
        with mock.patch.object(mcp.NativeHubClient, "discover", return_value=hub):
            answer = mcp.reply({"jsonrpc": "2.0", "id": 5, "method": "tools/call",
                                "params": {"name": "read_wow_live_data", "arguments": {}}})
        content = json.loads(answer["result"]["content"][0]["text"])
        self.assertTrue(content["available"])
        self.assertEqual(content["data"]["character"]["name"], "Kovaienko")
        self.assertEqual(content["transport"], "desktop_gui_hub")

    def test_disconnected_client_returns_clean_error_not_demo(self):
        with mock.patch.object(mcp.NativeHubClient, "discover", return_value=None):
            answer = mcp.reply({"jsonrpc": "2.0", "id": 5, "method": "tools/call",
                                "params": {"name": "read_wow_live_data"}})
        content = json.loads(answer["result"]["content"][0]["text"])
        self.assertFalse(content["available"])
        self.assertIsNone(content["data"])

    def test_demo_packet_rejected(self):
        hub = mock.Mock()
        hub.snapshot.return_value = {"available": True, "session": "native-demo",
                                     "data": {"character": {"name": "Demo"}}}
        with mock.patch.object(mcp.NativeHubClient, "discover", return_value=hub):
            answer = mcp.native_snapshot()
            self.assertFalse(answer["available"])
