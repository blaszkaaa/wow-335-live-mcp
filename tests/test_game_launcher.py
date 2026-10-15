"""One-click game launch and bundled addon installation regression tests."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import Mock, patch
import time

from game_launcher import addon_installed, install_addon, launch_wow
from desktop_service import DesktopState
from native_bridge.pipe import NativePipeReceiver


class GameLauncherTests(TestCase):
    def make_fixture(self, base):
        game = Path(base) / "WoW"
        game.mkdir()
        (game / "Wow.exe").write_bytes(b"fake test game")
        src = Path(base) / "bundled"
        src.mkdir()
        (src / "WoWMCPData.toc").write_text("## Interface: 30300\n")
        (src / "WoWMCPData.lua").write_text("print('v1')\n")
        return game, src

    def test_install_idempotent_and_backups(self):
        with TemporaryDirectory() as temp:
            game, src = self.make_fixture(temp)
            first = install_addon(game, src)
            self.assertTrue(first.changed)
            self.assertIsNone(first.backup)
            self.assertTrue(addon_installed(game))
            second = install_addon(game, src)
            self.assertFalse(second.changed)
            self.assertIsNone(second.backup)
            (src / "WoWMCPData.lua").write_text("print('v2')\n")
            changed = install_addon(game, src)
            self.assertTrue(changed.changed)
            self.assertTrue(Path(changed.backup).is_dir())
            self.assertEqual((Path(changed.backup) / "WoWMCPData.lua").read_text(),
                             "print('v1')\n")
            self.assertEqual((game / "Interface" / "AddOns" / "WoWMCPData" /
                              "WoWMCPData.lua").read_text(), "print('v2')\n")

    def test_reject_missing_game_and_missing_bundled_files(self):
        with TemporaryDirectory() as temp:
            game, src = self.make_fixture(temp)
            with self.assertRaises(ValueError):
                install_addon(Path(temp) / "nothing", src)
            (src / "WoWMCPData.toc").unlink()
            with self.assertRaises(FileNotFoundError):
                install_addon(game, src)

    def test_safe_executable_launch_uses_cwd(self):
        with TemporaryDirectory() as temp:
            game, src = self.make_fixture(temp)
            fake = Mock()
            launch_wow(game, process_factory=fake)
            args, kwargs = fake.call_args
            self.assertEqual(args[0], [str((game / "Wow.exe").resolve())])
            self.assertEqual(kwargs["cwd"], str(game.resolve()))
            self.assertEqual(kwargs["creationflags"], 0 if __import__("os").name != "nt"
                             else __import__("subprocess").CREATE_NO_WINDOW)

    def test_service_launch_starts_in_background(self):
        with TemporaryDirectory() as temp:
            game, src = self.make_fixture(temp)
            state = DesktopState(NativePipeReceiver(), Path(temp) / "settings.json")
            state.set_settings({"game_dir": str(game)})
            captured = []
            def install(path):
                captured.append(("install", path))
                return install_addon(path, src)
            def start(path):
                captured.append(("launch", path))
            with patch("desktop_service.install_addon", side_effect=install), \
                 patch("desktop_service.find_game_running", return_value=False), \
                 patch("desktop_service.launch_wow", side_effect=start):
                response = state.request_launch()
                self.assertTrue(response["started"])
                limit = time.monotonic() + 4
                while state.dashboard()["launch"]["busy"] and time.monotonic() < limit:
                    time.sleep(0.015)
            self.assertEqual([name for name, _ in captured], ["install", "launch"])
            self.assertEqual(state.dashboard()["launch"]["status"], "started")
            self.assertTrue(state.dashboard()["game"]["addon_installed"])

    def test_launch_does_not_open_second_game(self):
        with TemporaryDirectory() as temp:
            game, src = self.make_fixture(temp)
            state = DesktopState(NativePipeReceiver(), Path(temp) / "settings.json")
            state.set_settings({"game_dir": str(game)})
            with patch("desktop_service.install_addon", side_effect=lambda p: install_addon(p, src)), \
                 patch("desktop_service.find_game_running", return_value=True), \
                 patch("desktop_service.launch_wow") as launch:
                self.assertTrue(state.request_launch()["started"])
                limit = time.monotonic() + 3
                while state.dashboard()["launch"]["busy"] and time.monotonic() < limit:
                    time.sleep(0.015)
                launch.assert_not_called()
            self.assertEqual(state.dashboard()["launch"]["status"], "already_running")

    def test_service_uses_selected_preinstalled_native_launcher(self):
        with TemporaryDirectory() as temp:
            game, src = self.make_fixture(temp)
            state = DesktopState(NativePipeReceiver(), Path(temp) / "settings.json")
            state.set_settings({"game_dir": str(game), "launch_mode": "native"})
            with patch("desktop_service.install_addon", side_effect=lambda p: install_addon(p, src)), \
                 patch("desktop_service.find_game_running", return_value=False), \
                 patch("desktop_service.setup_native_runtime") as setup, \
                 patch("desktop_service.launch_wow") as launch:
                self.assertTrue(state.request_launch()["started"])
                deadline = time.monotonic() + 3
                while state.dashboard()["launch"]["busy"] and time.monotonic() < deadline:
                    time.sleep(0.015)
            setup.assert_called_once_with(str(game))
            launch.assert_called_once_with(str(game), mode="native")
            self.assertEqual(state.dashboard()["launch"]["status"], "started")

    def test_launch_missing_game_returns_message(self):
        with TemporaryDirectory() as temp:
            state = DesktopState(NativePipeReceiver(), Path(temp) / "settings.json")
            self.assertEqual(state.request_launch()["reason"], "game_dir_missing")


if __name__ == "__main__":
    import unittest
    unittest.main()
