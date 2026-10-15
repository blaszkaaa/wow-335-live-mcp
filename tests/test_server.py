"""Protocol and decoder tests using synthetic data only."""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from PIL import Image, ImageDraw

import server


def make_panel(payload, *, checksum=None):
    """Draw one 32x16 wire page at a nonzero screen offset."""
    if len(payload) > 498:
        raise ValueError("Test payload exceeds one page")
    checksum = sum(payload) % 65536 if checksum is None else checksum
    header = bytes((87, 77, 67, 80, 1, 7, 1, 1,
                    len(payload) % 256, len(payload) // 256,
                    len(payload) % 256, len(payload) // 256,
                    checksum % 256, checksum // 256))
    data = header + payload
    image = Image.new("RGB", (240, 180), (0, 0, 0))
    draw = ImageDraw.Draw(image)
    for index in range(512):
        byte = data[index] if index < len(data) else 0
        x = 8 + (index % 32) * 3
        y = 7 + (index // 32) * 3
        draw.rectangle((x, y, x + 2, y + 2),
                       fill=((byte // 16) * 17, (byte % 16) * 17, 255))
    return image


class PanelTests(unittest.TestCase):
    def test_decodes_valid_panel(self):
        payload = b'{"wire_version":3,"quests":[]}'
        packet = server.decode_panel_packet(make_panel(payload))
        self.assertIsNotNone(packet)
        self.assertEqual(packet["fragment"], payload)
        self.assertEqual(packet["page"], 1)
        self.assertEqual(packet["pages"], 1)

    def test_rejects_bad_checksum(self):
        self.assertIsNone(server.decode_panel_packet(make_panel(b"data", checksum=0)))

    def test_expands_wire_keys_and_rows(self):
        self.assertEqual(len(server.WIRE_FIELDS), len(set(server.WIRE_FIELDS)))
        self.assertLessEqual(len(server.WIRE_FIELDS), len(server.WIRE_TOKENS))
        key = next(key for key, value in server.WIRE_REVERSE.items()
                   if value == "wire_version") if "wire_version" in server.WIRE_FIELDS else None
        # wire_version is intentionally uncompressed; unknown keys pass through.
        self.assertIsNone(key)
        encoded = {"~A": 123, "wire_version": 3,
                   "bags": [[42, "Test item", 2, 0, 1]],
                   "actions": [[1, "spell", 0, "", True, 0]]}
        expanded = server.expand_compact_rows(server.expand_wire_data(encoded))
        self.assertEqual(expanded["captured_at"], 123)
        self.assertEqual(expanded["bags"][0]["id"], 42)
        self.assertEqual(expanded["bags"][0]["bag"], 0)
        self.assertNotIn("id", expanded["actions"][0])


class McpTests(unittest.TestCase):
    def test_initialize_and_tool_discovery(self):
        initialized = server.reply({"jsonrpc": "2.0", "id": 1,
                                    "method": "initialize", "params": {}})
        self.assertEqual(initialized["result"]["serverInfo"]["name"],
                         "wow-335-live-mcp")
        listed = server.reply({"jsonrpc": "2.0", "id": 2,
                               "method": "tools/list"})
        names = {tool["name"] for tool in listed["result"]["tools"]}
        self.assertIn("read_wow_live_data", names)
        self.assertIn("capture_wow", names)

    def test_notification_and_unknown_method(self):
        self.assertIsNone(server.reply({"jsonrpc": "2.0",
                                        "method": "notifications/initialized"}))
        self.assertEqual(server.reply({"jsonrpc": "2.0", "id": 4,
                                       "method": "ping"})["result"], {})
        response = server.reply({"jsonrpc": "2.0", "id": 3,
                                 "method": "unknown"})
        self.assertEqual(response["error"]["code"], -32601)

    def test_configuration_is_required(self):
        with mock.patch.object(server, "GAME", None):
            with self.assertRaisesRegex(RuntimeError, "WOW_GAME_DIR"):
                server.require_game_dir()

    def test_uses_desktop_game_directory_when_env_is_missing(self):
        with tempfile.TemporaryDirectory() as temporary:
            game = Path(temporary)
            (game / "Wow.exe").touch()
            hub = mock.Mock()
            hub.settings.return_value = {"game_dir": str(game)}
            with mock.patch.object(server, "GAME", None), mock.patch.object(
                    server.NativeHubClient, "discover", return_value=hub):
                self.assertEqual(server.require_game_dir(), game.resolve())

    def test_live_data_prefers_visual_and_does_not_read_dll(self):
        visual = {"available": True, "source": "WoW addon visual data strip",
                  "data": {"character": {"name": "Hunter"}}}
        with mock.patch.object(server, "live_game_data", return_value=visual) as capture, \
             mock.patch.object(server, "read_wow_native_data") as native:
            result = server.read_best_wow_live_data()
            self.assertEqual(result, visual)
            self.assertFalse(server.wow_native_status()["available"])
            capture.assert_called_once_with()
            native.assert_not_called()

    def test_mcp_live_tool_returns_visual_data(self):
        visual = {"available": True, "source": "WoW addon visual data strip",
                  "data": {"character": {"name": "Kovaienko"}, "quests": []}}
        with mock.patch.object(server, "live_game_data", return_value=visual):
            response = server.reply({"jsonrpc": "2.0", "id": 11,
                                     "method": "tools/call",
                                     "params": {"name": "read_wow_live_data"}})
        self.assertEqual(__import__("json").loads(
            response["result"]["content"][0]["text"])["data"]["character"]["name"],
            "Kovaienko")

    def test_status_uses_configured_game_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            game = Path(temporary)
            (game / "Wow.exe").touch()
            with mock.patch.object(server, "GAME", game), mock.patch.object(
                    server, "wow_window", return_value=None):
                result = server.status()
        self.assertTrue(result["game_installed"])
        self.assertFalse(result["game_running"])


if __name__ == "__main__":
    unittest.main()
