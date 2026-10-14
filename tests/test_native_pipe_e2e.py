"""Windows integration smoke test: real Win32 DLL -> pipe -> Python state."""

import os
import subprocess
import time
import unittest
from pathlib import Path

from native_bridge.pipe import NativePipeReceiver

DEMO_EXE = Path("build/native-bridge/Release/native_bridge_demo.exe")


@unittest.skipUnless(os.name == "nt" and DEMO_EXE.exists(),
                     "requires Win32 demo sender built by CI")
class NativePipeIntegrationTests(unittest.TestCase):
    def test_dll_delivers_json_over_real_named_pipe(self):
        receiver = NativePipeReceiver()
        self.assertTrue(receiver.start())
        deadline = time.monotonic() + 5
        result = None
        while time.monotonic() < deadline:
            result = subprocess.run([str(DEMO_EXE.resolve())],
                                    capture_output=True, text=True, timeout=3)
            if result.returncode == 0:
                break
            time.sleep(0.1)
        self.assertIsNotNone(result)
        self.assertEqual(result.returncode, 0,
                         (result.stderr or "") + (receiver.status().get("error") or ""))
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            snapshot = receiver.snapshot()
            if snapshot["available"]:
                break
            time.sleep(0.02)
        self.assertTrue(snapshot["available"], receiver.status())
        self.assertEqual(snapshot["data"]["character"]["name"], "Demo")
        self.assertEqual(snapshot["data"]["location"]["zone"], "Test zone")


if __name__ == "__main__":
    unittest.main()
