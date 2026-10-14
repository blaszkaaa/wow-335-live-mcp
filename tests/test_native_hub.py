"""GUI-to-MCP IPC tests, independent of WoW and the Windows telemetry pipe."""
import json
import tempfile
import time
import unittest
from pathlib import Path

from native_bridge.hub import NativeHubClient, NativeHubServer
from native_bridge.pipe import NativePipeReceiver


class NativeHubTests(unittest.TestCase):
    def test_hub_discovery_authorization_and_cleanup(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "control.json"
            receiver = NativePipeReceiver()
            hub = NativeHubServer(receiver, discovery_file=path)
            try:
                self.assertTrue(hub.start())
                self.assertTrue(path.is_file())
                config = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(len(config["token"]), 64)
                client = NativeHubClient.discover(path)
                self.assertIsNotNone(client)
                self.assertEqual(client.status()["accepted_frames"], 0)
                invalid = NativeHubClient(client.port, "0" * 64)
                self.assertIsNone(invalid.status())

                frame = json.dumps({
                    "version": 1, "session": "gui-test", "sequence": 1,
                    "kind": "snapshot", "captured_at": time.time(),
                    "data": {"character": {"name": "TestUser", "level": 22}},
                }).encode("utf-8")
                self.assertTrue(receiver.state.ingest(frame))
                self.assertEqual(
                    client.snapshot()["data"]["character"]["level"], 22)
                with self.assertRaises(RuntimeError):
                    NativeHubServer(receiver, path).start()
            finally:
                hub.stop()
            self.assertFalse(path.exists())
            self.assertIsNone(client.status())

    def test_invalid_discovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.json"
            self.assertIsNone(NativeHubClient.discover(path))
            path.write_text('{"port": 42, "token": "test"}', encoding="utf-8")
            self.assertIsNone(NativeHubClient.discover(path))


class GuiPresentationTests(unittest.TestCase):
    def test_empty_and_demo_snapshots_are_labeled(self):
        from desktop_app import source_label, time_label
        self.assertEqual(source_label({"available": False}), "Brak świeżych danych")
        self.assertIn("demonstracyjne", source_label({
            "available": True, "data": {"character": {"name": "Demo"}}
        }))
        self.assertEqual(time_label(None), "—")


if __name__ == "__main__":
    unittest.main()
