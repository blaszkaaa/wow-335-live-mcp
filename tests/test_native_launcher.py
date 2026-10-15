"""Regression tests for the opt-in external-launcher route (no game needed)."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import Mock

from game_launcher import launch_wow
from native_bridge.diagnostics import inspect_native_runtime, is_win32_pe


def fake_pe(path, machine=0x14c):
    data = bytearray(256)
    data[0:2] = b"MZ"
    data[60:64] = (128).to_bytes(4, "little")
    data[128:132] = b"PE\x00\x00"
    data[132:134] = machine.to_bytes(2, "little")
    data[152:154] = (0x10b).to_bytes(2, "little")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


class NativeRouteTests(TestCase):
    def test_rejects_missing_and_wrong_architecture(self):
        with TemporaryDirectory() as folder:
            game = Path(folder)
            fake_pe(game / "Wow.exe")
            self.assertFalse(inspect_native_runtime(game)["ready"])
            self.assertIn("LichLoader.exe", inspect_native_runtime(game)["reason"])
            fake_pe(game / "LichLoader.exe", 0x8664)
            self.assertFalse(is_win32_pe(game / "LichLoader.exe"))
            self.assertIn("PE32", inspect_native_runtime(game)["reason"])

    def test_native_uses_separately_prepared_launcher(self):
        with TemporaryDirectory() as folder:
            game = Path(folder)
            for name in ("Wow.exe", "LichLoader.exe", "LichCore.dll", "dll/WoWMCPNativeLua.dll"):
                fake_pe(game / name)
            (game / "lichloader.txt").write_text("# my mods\ndll/WoWMCPNativeLua.dll\n", encoding="utf-8")
            self.assertTrue(inspect_native_runtime(game)["ready"])
            run = Mock()
            launch_wow(game, process_factory=run, mode="native")
            args, kwargs = run.call_args
            self.assertEqual(args[0], [str((game / "LichLoader.exe").resolve())])
            self.assertEqual(kwargs["cwd"], str(game.resolve()))

    def test_native_missing_configuration_never_starts_game(self):
        with TemporaryDirectory() as folder:
            game = Path(folder)
            fake_pe(game / "Wow.exe")
            run = Mock()
            with self.assertRaisesRegex(RuntimeError, "LichLoader"):
                launch_wow(game, process_factory=run, mode="native")
            run.assert_not_called()

    def test_invalid_mode_rejected(self):
        with TemporaryDirectory() as folder:
            game = Path(folder)
            fake_pe(game / "Wow.exe")
            with self.assertRaises(ValueError):
                launch_wow(game, mode="invalid")
