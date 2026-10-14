"""Platform-independent protocol tests for the optional native transport."""

import json
import time
import unittest

from native_bridge.state import NativeState


class NativeBridgeProtocolTests(unittest.TestCase):
    def setUp(self):
        self.state = NativeState()

    def packet(self, kind="snapshot", sequence=1, data=None, session="test"):
        return json.dumps({
            "version": 1, "session": session, "sequence": sequence,
            "kind": kind, "captured_at": time.time(),
            "data": data if data is not None else {"character": {"level": 9}},
        }).encode("utf-8")

    def test_snapshot(self):
        self.assertTrue(self.state.ingest(self.packet()))
        self.assertEqual(self.state.snapshot()["data"]["character"]["level"], 9)

    def test_delta_and_removal(self):
        self.assertTrue(self.state.ingest(self.packet()))
        self.assertTrue(self.state.ingest(self.packet(
            kind="delta", sequence=2, data={"location": {"zone": "Elwynn"}})))
        self.assertTrue(self.state.ingest(self.packet(
            kind="delta", sequence=3, data={"character": None})))
        self.assertNotIn("character", self.state.snapshot()["data"])
        self.assertEqual(self.state.snapshot()["data"]["location"]["zone"], "Elwynn")

    def test_rejects_out_of_order_or_missing_snapshot(self):
        self.assertFalse(self.state.ingest(self.packet(kind="delta")))
        self.assertTrue(self.state.ingest(self.packet()))
        self.assertFalse(self.state.ingest(self.packet(sequence=1)))
        self.assertFalse(self.state.ingest(self.packet(kind="delta", session="other", sequence=2)))
        self.assertEqual(self.state.status()["rejected_frames"], 3)

    def test_new_session_can_reset_sequence(self):
        self.assertTrue(self.state.ingest(self.packet(sequence=99)))
        self.assertTrue(self.state.ingest(self.packet(sequence=1, session="restart")))
        self.assertEqual(self.state.status()["session"], "restart")

    def test_rejects_oversized_and_malformed_json(self):
        self.assertFalse(self.state.ingest(b"{" * 100))
        self.assertFalse(self.state.ingest(b"x" * 65537))
        self.assertFalse(self.state.status()["available"])

    def test_stale_is_not_live(self):
        self.assertTrue(self.state.ingest(self.packet()))
        with self.state._lock:
            self.state._received_at -= 40
        self.assertFalse(self.state.snapshot()["available"])
        self.assertIsNone(self.state.snapshot()["data"])


if __name__ == "__main__":
    unittest.main()
