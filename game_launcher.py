"""Safe one-click WoW 3.3.5a launch and bundled addon installer.

Never injects a DLL, patches Wow.exe, or bypasses game integrity checks.
"""
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import os
import shutil
import subprocess
import sys
from uuid import uuid4

ADDON_FILES = ("WoWMCPData.toc", "WoWMCPData.lua")


def bundled_addon_path():
    """Resolve the addon both in the source checkout and PyInstaller onefile."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / "WoWMCPData"


def validate_game_directory(directory):
    if not isinstance(directory, str) or not directory.strip():
        raise ValueError("Najpierw wybierz folder z plikiem Wow.exe.")
    if len(directory) > 1024:
        raise ValueError("Ścieżka do gry jest za długa.")
    game = Path(directory).expanduser().resolve(strict=False)
    if not game.is_dir() or not (game / "Wow.exe").is_file():
        raise ValueError("Wybrany katalog nie zawiera Wow.exe.")
    return game


@dataclass
class AddonInstallResult:
    installed: bool
    changed: bool
    backup: str | None = None


def addon_installed(game):
    root = Path(game) / "Interface" / "AddOns" / "WoWMCPData"
    return all((root / name).is_file() for name in ADDON_FILES)


def install_addon(game, source=None):
    """Idempotent install with backup of any previous different addon folder.

    Only writes the two known addon files; never modifies Wow.exe or other mods.
    """
    game = validate_game_directory(str(game))
    source = Path(source) if source is not None else bundled_addon_path()
    for name in ADDON_FILES:
        if not (source / name).is_file():
            raise FileNotFoundError("Brak pliku addonu w aplikacji: " + name)
    addons = game / "Interface" / "AddOns"
    target = addons / "WoWMCPData"
    if target.is_symlink() or addons.is_symlink() or (game / "Interface").is_symlink():
        raise ValueError("Instalacja do dowiązania symbolicznego nie jest dozwolona.")
    identical = target.is_dir() and all(
        (target / name).is_file() and
        (target / name).read_bytes() == (source / name).read_bytes()
        for name in ADDON_FILES
    )
    if identical:
        return AddonInstallResult(installed=True, changed=False)
    backup = None
    if target.exists():
        if not target.is_dir():
            raise ValueError("Ścieżka addonu jest zajęta przez plik.")
        backup_root = game / "Interface" / "AddOns-backups"
        if backup_root.is_symlink():
            raise ValueError("Katalog kopii zapasowych jest dowiązaniem symbolicznym.")
        backup_root.mkdir(parents=True, exist_ok=True)
        backup = backup_root / ("WoWMCPData-" + datetime.now().strftime("%Y%m%d-%H%M%S")
                                + "-" + uuid4().hex[:8])
        shutil.copytree(target, backup)
    target.mkdir(parents=True, exist_ok=True)
    for name in ADDON_FILES:
        # Write to temp path then replace, preventing partially overwritten files.
        dest = target / name
        if dest.is_symlink():
            raise ValueError("Nie można nadpisać pliku addonu będącego dowiązaniem.")
        tmp = target / (name + ".wowmcp-tmp")
        try:
            shutil.copyfile(source / name, tmp)
            os.replace(tmp, dest)
        finally:
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass
    return AddonInstallResult(installed=True, changed=True,
                              backup=str(backup) if backup else None)


def launch_wow(game, process_factory=subprocess.Popen):
    """Start the selected game's own Wow.exe, without any DLL loader."""
    directory = validate_game_directory(str(game))
    executable = directory / "Wow.exe"
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return process_factory([str(executable)], cwd=str(directory),
                           close_fds=True, creationflags=flags)
