"""Read-only verification of a manually installed 3.3.5a native runtime."""
from pathlib import Path

EXPECTED_DLL = Path("dll") / "WoWMCPNativeLua.dll"
EXPECTED_ENTRY = r"dll\WoWMCPNativeLua.dll"


def is_win32_pe(path):
    """Check PE32 x86 without loading or modifying any executable."""
    try:
        with Path(path).open("rb") as stream:
            header = stream.read(4096)
        if len(header) < 64 or header[:2] != b"MZ":
            return False
        offset = int.from_bytes(header[60:64], "little")
        return (offset + 26 <= len(header)
                and header[offset:offset + 4] == bytes((80, 69, 0, 0))
                and int.from_bytes(header[offset + 4:offset + 6], "little") == 0x14c
                and int.from_bytes(header[offset + 24:offset + 26], "little") == 0x10b)
    except OSError:
        return False


def inspect_native_runtime(game_dir):
    """No installation or process access; returns actionable prerequisites."""
    if not game_dir:
        return {"ready": False, "reason": "Najpierw wybierz katalog gry."}
    root = Path(game_dir)
    game = root / "Wow.exe"
    if not game.is_file():
        return {"ready": False, "reason": "Nie znaleziono Wow.exe."}
    if not is_win32_pe(game):
        return {"ready": False, "reason": "Wow.exe nie jest plikiem PE32 x86 (WoW 3.3.5a)."}
    required = [
        ("LichLoader.exe", root / "LichLoader.exe"),
        ("LichCore.dll", root / "LichCore.dll"),
        ("WoWMCPNativeLua.dll", root / EXPECTED_DLL),
    ]
    for label, path in required:
        if not path.is_file():
            return {"ready": False, "reason": "Brak pliku " + label + " w katalogu gry."}
        if not is_win32_pe(path):
            return {"ready": False, "reason": label + " musi być biblioteką lub programem PE32 x86."}
    config = root / "lichloader.txt"
    try:
        lines = config.read_text(encoding="utf-8-sig").splitlines()
    except (OSError, UnicodeError):
        return {"ready": False, "reason": "Nie znaleziono czytelnego lichloader.txt."}
    enabled = [line.split("#", 1)[0].strip().replace("/", "\\").casefold() for line in lines]
    if EXPECTED_ENTRY.casefold() not in enabled:
        return {"ready": False, "reason": "Dopisz dll\\WoWMCPNativeLua.dll do lichloader.txt."}
    return {"ready": True, "reason": "Pliki są obecne; działanie potwierdzą dopiero pakiety z gry."}
