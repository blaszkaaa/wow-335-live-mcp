"""Local native package setup tests; only temporary, fake files are touched."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
import os

from native_bridge.setup import setup_native_runtime, native_bundle_ready
from native_bridge.diagnostics import inspect_native_runtime


def fake_pe(path, marker=b""):
    file = Path(path)
    file.parent.mkdir(parents=True, exist_ok=True)
    data = bytearray(256)
    data[0:2] = b"MZ"
    data[60:64] = (128).to_bytes(4, "little")
    data[128:132] = b"PE\x00\x00"
    data[132:134] = (0x14c).to_bytes(2, "little")
    data[152:154] = (0x10b).to_bytes(2, "little")
    file.write_bytes(bytes(data) + marker)


class NativeSetupTests(TestCase):
    def fixture(self, parent):
        base = Path(parent)
        game = base / "game"
        bundle = base / "bundle"
        fake_pe(game / "Wow.exe")
        for name in ("LichLoader.exe", "LichCore.dll", "WoWMCPNativeLua.dll"):
            fake_pe(bundle / name)
        return game, bundle

    def test_one_click_setup_is_idempotent(self):
        with TemporaryDirectory() as tmp:
            game, bundle = self.fixture(tmp)
            self.assertTrue(native_bundle_ready(bundle))
            self.assertFalse(inspect_native_runtime(game)["ready"])
            initial = setup_native_runtime(game, bundle)
            self.assertTrue(initial["ready"])
            self.assertEqual(initial["files_updated"], 3)
            self.assertTrue(inspect_native_runtime(game)["ready"])
            self.assertEqual(setup_native_runtime(game, bundle)["files_updated"], 0)
            self.assertEqual(
                (game / "lichloader.txt").read_text(encoding="utf-8").count(
                    r"dll\WoWMCPNativeLua.dll"), 1)

    def test_preserve_existing_loader_config(self):
        with TemporaryDirectory() as tmp:
            game, bundle = self.fixture(tmp)
            (game / "lichloader.txt").write_text("# custom\nmods/foo.dll\n", encoding="utf-8")
            setup_native_runtime(game, bundle)
            text = (game / "lichloader.txt").read_text(encoding="utf-8")
            self.assertIn("mods/foo.dll", text)
            self.assertIn(r"dll\WoWMCPNativeLua.dll", text)

    def test_existing_conflicting_loader_is_not_overwritten(self):
        with TemporaryDirectory() as tmp:
            game, bundle = self.fixture(tmp)
            fake_pe(game / "LichLoader.exe", b"custom-build")
            original = (game / "LichLoader.exe").read_bytes()
            with self.assertRaises(FileExistsError):
                setup_native_runtime(game, bundle)
            self.assertEqual((game / "LichLoader.exe").read_bytes(), original)
            self.assertFalse((game / "LichCore.dll").exists())

    def test_update_adapter_preserves_backup(self):
        with TemporaryDirectory() as tmp:
            game, bundle = self.fixture(tmp)
            setup_native_runtime(game, bundle)
            original = (game / "dll" / "WoWMCPNativeLua.dll").read_bytes()
            fake_pe(bundle / "WoWMCPNativeLua.dll", b"new-version")
            updated = setup_native_runtime(game, bundle)
            self.assertEqual(updated["files_updated"], 1)
            backups = list((game / "WoWMCPBackups").glob("WoWMCPNativeLua-*.dll"))
            self.assertEqual(len(backups), 1)
            self.assertEqual(backups[0].read_bytes(), original)

    def test_rejects_invalid_client_without_modification(self):
        with TemporaryDirectory() as tmp:
            game, bundle = self.fixture(tmp)
            (game / "Wow.exe").write_bytes(b"Not a Windows PE executable")
            with self.assertRaises(ValueError):
                setup_native_runtime(game, bundle)
            self.assertFalse((game / "LichLoader.exe").exists())
