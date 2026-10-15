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

    def test_launch_mode_persists_and_keeps_game_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "WoW"
            folder.mkdir()
            (folder / "Wow.exe").touch()
            settings_file = Path(tmp) / "settings.json"
            state = DesktopState(NativePipeReceiver(), settings_file)
            state.set_settings({"game_dir": str(folder)})
            state.set_settings({"launch_mode": "native"})
            self.assertEqual(state.get_settings()["game_dir"], str(folder))
            self.assertEqual(state.dashboard()["launch_mode"], "native")
            reopened = DesktopState(NativePipeReceiver(), settings_file)
            self.assertEqual(reopened.get_settings()["launch_mode"], "native")
            with self.assertRaises(ValueError):
                reopened.set_settings({"launch_mode": "unknown"})
            reopened.set_settings({"launch_mode": "addon"})
            self.assertEqual(reopened.get_settings()["game_dir"], str(folder))

    def test_game_process_check_is_async_and_cached(self):
        from threading import Event
        gate = Event()
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "WoW"
            folder.mkdir()
            (folder / "Wow.exe").touch()
            state = DesktopState(NativePipeReceiver(), Path(tmp) / "settings.json")
            state.set_settings({"game_dir": str(folder)})
            with patch("desktop_service.find_game_running", side_effect=lambda _: (gate.wait(2), True)[1]) as detect:
                # The dashboard must not wait for a potentially slow tasklist call.
                started = time.monotonic()
                data = state.dashboard()
                self.assertLess(time.monotonic() - started, 0.5)
                self.assertFalse(data["game"]["running"])
                state.dashboard()
                self.assertEqual(detect.call_count, 1)
                gate.set()
                deadline = time.monotonic() + 3
                while time.monotonic() < deadline:
                    if state.dashboard()["game"]["running"]:
                        break
                    time.sleep(0.02)
                self.assertTrue(state.dashboard()["game"]["running"])
                state.dashboard()
                self.assertEqual(detect.call_count, 1)

    @unittest.skipUnless(__import__("os").name == "nt", "Windows-only console flag")
    def test_windows_process_detection_never_opens_console(self):
        from unittest.mock import Mock
        import subprocess
        from desktop_service import find_game_running
        with patch("desktop_service.subprocess.run", return_value=Mock(stdout='"Wow.exe","",123')) as run:
            self.assertTrue(find_game_running("C:/Fake"))
            self.assertTrue(run.call_args.kwargs["creationflags"] & subprocess.CREATE_NO_WINDOW)

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
