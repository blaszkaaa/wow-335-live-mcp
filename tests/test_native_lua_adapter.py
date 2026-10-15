"""Native WoW Lua snapshots should seamlessly power the default MCP live tool."""
import json
import time
import unittest
from unittest import mock

import server
from native_bridge.state import NativeState


class NativeLuaFrameTests(unittest.TestCase):
    def native_frame(self, seq=1, session="offline-client-1"):
        return json.dumps({
            "version": 1,
            "session": session,
            "sequence": seq,
            "kind": "snapshot",
            "captured_at": time.time(),
            "data": {
                "captured_at": time.time(),
                "character": {"name": "MCPMage", "level": 31, "health": 500},
                "location": {"zone": "Stranglethorn Vale", "map_x": 0.52},
                "quests": [{"title": "Find the Book", "ready_to_turn_in": True}],
                "bags": [{"name": "Blue Gem", "id": 11, "count": 2}],
            },
        }).encode("utf-8")

    def test_full_native_lua_snapshot_is_preserved(self):
        data = NativeState()
        self.assertTrue(data.ingest(self.native_frame()))
        value = data.snapshot()
        self.assertTrue(value["available"])
        self.assertEqual(value["data"]["character"]["name"], "MCPMage")
        self.assertEqual(value["data"]["quests"][0]["title"], "Find the Book")
        self.assertEqual(value["data"]["bags"][0]["name"], "Blue Gem")

    def test_native_is_default_when_enabled_and_fresh(self):
        native = {"available": True, "session": "offline-client-1",
                  "source": "experimental native DLL named pipe",
                  "data": {"character": {"name": "MCPMage"}}}
        with mock.patch.dict("os.environ", {"WOW_MCP_NATIVE_BRIDGE": "1"}), \
             mock.patch.object(server, "read_wow_native_data", return_value=native), \
             mock.patch.object(server, "live_game_data") as visual:
            self.assertEqual(server.read_best_wow_live_data(), native)
            visual.assert_not_called()

    def test_native_missing_returns_error_without_visual_fallback(self):
        with mock.patch.object(server, "read_wow_native_data", return_value={"available": False}), \
             mock.patch.object(server, "live_game_data") as visual:
            result = server.read_best_wow_live_data()
            self.assertFalse(result["available"])
            self.assertEqual(result["source"], "native_dll")
            visual.assert_not_called()

    def test_standalone_demo_not_considered_game_telemetry(self):
        with mock.patch.dict("os.environ", {"WOW_MCP_NATIVE_BRIDGE": "1"}), \
             mock.patch.object(server, "read_wow_native_data",
                               return_value={"available": True, "session": "native-demo",
                                             "data": {"character": {"name": "Demo"}}}), \
             mock.patch.object(server, "live_game_data", return_value={"available": False}) as visual:
            self.assertFalse(server.read_best_wow_live_data()["available"])
            visual.assert_not_called()

    def test_desktop_native_discovery_does_not_require_environment_flag(self):
        with mock.patch.dict("os.environ", {"WOW_MCP_NATIVE_BRIDGE": ""}), \
             mock.patch.object(server, "read_wow_native_data", return_value={"available": False}) as native, \
             mock.patch.object(server, "live_game_data", return_value={"available": False}):
            server.read_best_wow_live_data()
            native.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
