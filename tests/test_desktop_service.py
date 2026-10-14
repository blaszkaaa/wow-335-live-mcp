"""Native service and desktop dashboard integration tests (no game required)."""
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from native_bridge.pipe import NativePipeReceiver
from native_bridge.hub import NativeHubClient, NativeHubServer
from desktop_service import DesktopState


class DesktopServiceTests(unittest.TestCase):
    def test_unconfigured_state_is_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = DesktopState(NativePipeReceiver(), Path(tmp) / "settings.json")
            data = state.dashboard()
            self.assertFalse(data["available"])
            self.assertFalse(data["game"]["installed"])
            self.assertEqual(data["metrics"]["quest_count"], 0)
            self.assertEqual(state.request_refresh()["reason"], "game_dir_missing")

    def test_synthetic_preview_is_labeled_demo(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = DesktopState(NativePipeReceiver(), Path(tmp) / "settings.json")
            state.show_demo()
            data = state.dashboard()
            self.assertTrue(data["available"])
            self.assertTrue(data["demo"])
            self.assertIn("DEMO", data["source_label"])
            self.assertEqual(data["metrics"]["quest_count"], 2)

    def test_settings_folder_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = DesktopState(NativePipeReceiver(), Path(tmp) / "settings.json")
            with self.assertRaises(ValueError):
                state.set_settings({"game_dir": "non-existent-folder"})
            folder = Path(tmp) / "WoW"
            folder.mkdir()
            (folder / "Wow.exe").touch()
            state.set_settings({"game_dir": str(folder)})
            self.assertEqual(state.get_settings()["game_dir"], str(folder))

    def test_authenticated_api_endpoints(self):
        with tempfile.TemporaryDirectory() as tmp:
            receiver = NativePipeReceiver()
            state = DesktopState(receiver, Path(tmp) / "settings.json")
            server = NativeHubServer(receiver, Path(tmp) / "control.json", dashboard=state)
            server.start()
            try:
                client = NativeHubClient.discover(Path(tmp) / "control.json")
                self.assertFalse(client._get("/v2/dashboard")["available"])
                response = client._post("/v2/demo", {})
                self.assertTrue(response["demo"])
                self.assertTrue(client._get("/v2/dashboard")["demo"])
                self.assertEqual(client._get("/v2/settings")["game_dir"], "")
                self.assertIsNone(NativeHubClient(client.port, "x" * 64)._post("/v2/demo", {}))
            finally:
                server.stop()


if __name__ == "__main__":
    unittest.main()
