"""The safe launch path must never use the previously installed DLL loader."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import Mock
from game_launcher import launch_wow


class VanillaLaunchTests(TestCase):
    def test_launch_ignores_old_loader_files(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "Wow.exe").write_bytes(b"test")
            (root / "LichLoader.exe").write_bytes(b"old native loader")
            (root / "LichCore.dll").write_bytes(b"old loader core")
            (root / "lichloader.txt").write_text("dll/Old.dll", encoding="utf-8")
            run = Mock()
            launch_wow(root, process_factory=run)
            args, kwargs = run.call_args
            self.assertEqual(args[0], [str((root / "Wow.exe").resolve())])
            self.assertEqual(kwargs["cwd"], str(root.resolve()))

    def test_launcher_has_no_native_argument(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "Wow.exe").write_bytes(b"test")
            run = Mock()
            with self.assertRaises(TypeError):
                launch_wow(root, process_factory=run, mode="native")
            run.assert_not_called()
