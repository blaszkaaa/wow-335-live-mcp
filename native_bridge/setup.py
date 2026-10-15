"""Install the signed-off application runtime files from the local package.

No network access is performed during setup. Changes are limited to known files,
and existing unrelated loader configurations are preserved.
"""
from datetime import datetime
from pathlib import Path
import hashlib
import os
import shutil
import sys

from game_launcher import validate_game_directory
from native_bridge.diagnostics import inspect_native_runtime, is_win32_pe

FILES = {
    "LichLoader.exe": "LichLoader.exe",
    "LichCore.dll": "LichCore.dll",
    "dll/WoWMCPNativeLua.dll": "WoWMCPNativeLua.dll",
}
CONFIG_ENTRY = r"dll\WoWMCPNativeLua.dll"


def bundled_native_path():
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return root / "native_runtime"


def native_bundle_ready(source=None):
    root = Path(source) if source else bundled_native_path()
    return all((root / filename).is_file() for filename in FILES.values())


def file_hash(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(65536), b""):
            h.update(chunk)
    return h.digest()


def setup_native_runtime(game_dir, source=None):
    """Prepare a previously selected local game installation for native mode.

    A trusted bundle is shipped with the Windows application. Existing vendor
    loader binaries are never replaced; an older application adapter is backed
    up before upgrading. Unknown files and Wow.exe remain untouched.
    """
    root = validate_game_directory(str(game_dir))
    if not is_win32_pe(root / "Wow.exe"):
        raise ValueError("Tryb DLL wymaga WoW 3.3.5a Win32 (PE32).")
    bundle = Path(source) if source else bundled_native_path()
    if not native_bundle_ready(bundle):
        raise FileNotFoundError("Brak plików DLL w tej wersji aplikacji. Zainstaluj aktualną wersję.")
    for relative, file_name in FILES.items():
        source_file = bundle / file_name
        destination = root / relative
        if not is_win32_pe(source_file):
            raise ValueError("Niepoprawny plik Win32: " + file_name)
        if destination.is_symlink() or destination.parent.is_symlink():
            raise ValueError("Niedozwolone dowiązanie symboliczne: " + relative)
        if destination.exists():
            if not destination.is_file():
                raise ValueError("Ścieżka pliku jest zajęta: " + relative)
            if relative in ("LichLoader.exe", "LichCore.dll") and file_hash(source_file) != file_hash(destination):
                raise FileExistsError("Istnieje inna wersja " + relative +
                    ". Nie zastępuję pliku należącego do innej instalacji.")
    config = root / "lichloader.txt"
    if config.is_symlink():
        raise ValueError("Nie można nadpisać dowiązania lichloader.txt.")
    if config.exists() and not config.is_file():
        raise ValueError("Nieprawidłowy plik lichloader.txt.")
    original = config.read_bytes() if config.exists() else b""
    if len(original) > 1024 * 1024:
        raise ValueError("Plik lichloader.txt jest zbyt duży.")
    try:
        entries = original.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("lichloader.txt musi być plikiem UTF-8.") from exc
    lines = [line.split("#", 1)[0].strip().replace("/", "\\").casefold()
             for line in entries.splitlines()]
    if CONFIG_ENTRY.casefold() not in lines:
        entries += ("" if not entries or entries.endswith(("\r", "\n")) else "\n")
        entries += CONFIG_ENTRY + "\n"

    prepared = 0
    for relative, file_name in FILES.items():
        src = bundle / file_name
        dst = root / relative
        if dst.exists() and file_hash(dst) == file_hash(src):
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists():
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            backup_dir = root / "WoWMCPBackups"
            if backup_dir.is_symlink():
                raise ValueError("Niedozwolony katalog kopii zapasowych.")
            backup_dir.mkdir(parents=True, exist_ok=True)
            backup = backup_dir / ("WoWMCPNativeLua-" + stamp + ".dll")
            shutil.copy2(dst, backup)
        pending = dst.with_name(dst.name + ".wowmcp-pending")
        try:
            shutil.copy2(src, pending)
            os.replace(pending, dst)
        finally:
            pending.unlink(missing_ok=True)
        prepared += 1
    if entries != original.decode("utf-8-sig"):
        pending = config.with_name("lichloader.txt.wowmcp-pending")
        try:
            pending.write_text(entries, encoding="utf-8")
            os.replace(pending, config)
        finally:
            pending.unlink(missing_ok=True)
    check = inspect_native_runtime(root)
    if not check["ready"]:
        raise RuntimeError(check["reason"])
    return {"ready": True, "files_updated": prepared}
