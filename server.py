"""Read-only, on-demand WoW 3.3.5a MCP server for Windows."""

import base64
import ctypes
import io
import json
import os
import re
import sys
import time
from pathlib import Path

import numpy as np
from PIL import ImageGrab

from native_bridge.pipe import NativePipeReceiver
from native_bridge.hub import NativeHubClient


GAME_DIR = os.environ.get("WOW_GAME_DIR")
GAME = Path(GAME_DIR).expanduser().resolve() if GAME_DIR else None
WIRE_TOKENS = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
WIRE_SOURCE = (Path(__file__).parent / "WoWMCPData" / "WoWMCPData.lua").read_text(encoding="utf-8")
WIRE_MATCH = re.search(r'local WIRE_FIELDS = "([^"]+)"', WIRE_SOURCE)
WIRE_FIELDS = WIRE_MATCH.group(1).split(",") if WIRE_MATCH else []
if len(WIRE_FIELDS) > len(WIRE_TOKENS):
    raise RuntimeError("Too many WoW MCP wire fields")
WIRE_REVERSE = {"~" + token: field for token, field in zip(WIRE_TOKENS, WIRE_FIELDS)}
USER32 = ctypes.windll.user32
KERNEL32 = ctypes.windll.kernel32
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
KERNEL32.OpenProcess.restype = ctypes.c_void_p
KERNEL32.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_bool, ctypes.c_ulong]
KERNEL32.CloseHandle.argtypes = [ctypes.c_void_p]
KERNEL32.QueryFullProcessImageNameW.argtypes = [ctypes.c_void_p, ctypes.c_ulong,
                                                 ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_ulong)]
USER32.GetWindowThreadProcessId.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong)]
USER32.GetWindowThreadProcessId.restype = ctypes.c_ulong
USER32.GetForegroundWindow.restype = ctypes.c_void_p
USER32.SetForegroundWindow.argtypes = [ctypes.c_void_p]
USER32.IsWindow.argtypes = [ctypes.c_void_p]
USER32.AttachThreadInput.argtypes = [ctypes.c_ulong, ctypes.c_ulong, ctypes.c_bool]
USER32.SetWindowPos.argtypes = [ctypes.c_void_p, ctypes.c_void_p,
                                ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                ctypes.c_uint]
USER32.SetWindowPos.restype = ctypes.c_bool
USER32.GetWindowLongW.argtypes = [ctypes.c_void_p, ctypes.c_int]
USER32.GetWindowLongW.restype = ctypes.c_long
KERNEL32.GetCurrentThreadId.restype = ctypes.c_ulong
SWP_KEEP_SIZE_AND_POSITION = 0x0001 | 0x0002 | 0x0010
WS_EX_TOPMOST = 0x00000008


class RECT(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                ("right", ctypes.c_long), ("bottom", ctypes.c_long)]


def require_game_dir():
    if GAME is not None:
        return GAME
    # MCP often runs separately from the desktop UI. Reuse its authenticated
    # saved configuration rather than require a second game path setting.
    hub = NativeHubClient.discover()
    if hub is not None:
        settings = hub.settings()
        directory = settings.get("game_dir") if isinstance(settings, dict) else None
        if isinstance(directory, str) and directory:
            game = Path(directory).expanduser().resolve()
            if (game / "Wow.exe").is_file():
                return game
    raise RuntimeError("Wybierz folder WoW w aplikacji lub ustaw WOW_GAME_DIR.")


def process_path(hwnd):
    pid = ctypes.c_ulong()
    USER32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    handle = KERNEL32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
    if not handle:
        return ""
    try:
        size = ctypes.c_ulong(32768)
        buf = ctypes.create_unicode_buffer(size.value)
        if KERNEL32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
            return buf.value
        return ""
    finally:
        KERNEL32.CloseHandle(handle)


def wow_window():
    game = require_game_dir()
    found = []
    callback_type = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

    @callback_type
    def visit(hwnd, _):
        if USER32.IsWindowVisible(hwnd):
            path = process_path(hwnd)
            if (path and Path(path).name.lower() == "wow.exe" and
                    os.path.normcase(str(Path(path).parent.resolve())) ==
                    os.path.normcase(str(game))):
                title = ctypes.create_unicode_buffer(512)
                USER32.GetWindowTextW(hwnd, title, len(title))
                rect = RECT()
                USER32.GetWindowRect(hwnd, ctypes.byref(rect))
                found.append((hwnd, title.value, rect))
        return True

    USER32.EnumWindows(visit, 0)
    return found[0] if found else None


def focus_window(hwnd):
    """Bring a requested window forward despite Win32 foreground restrictions."""
    if USER32.GetForegroundWindow() == hwnd:
        return True
    USER32.SetForegroundWindow(hwnd)
    time.sleep(0.08)
    if USER32.GetForegroundWindow() == hwnd:
        return True
    foreground = USER32.GetForegroundWindow()
    if not foreground:
        return False
    own_thread = KERNEL32.GetCurrentThreadId()
    foreground_thread = USER32.GetWindowThreadProcessId(foreground, None)
    if not foreground_thread or foreground_thread == own_thread:
        return False
    if not USER32.AttachThreadInput(own_thread, foreground_thread, True):
        return False
    try:
        USER32.BringWindowToTop(hwnd)
        USER32.SetForegroundWindow(hwnd)
    finally:
        USER32.AttachThreadInput(own_thread, foreground_thread, False)
    time.sleep(0.08)
    return USER32.GetForegroundWindow() == hwnd


def prepare_capture(hwnd):
    """Make WoW visible for screen capture when foreground activation is denied.

    Returns True only when this call temporarily changed WoW to topmost.
    """
    if focus_window(hwnd):
        return False
    was_topmost = bool(USER32.GetWindowLongW(hwnd, -20) & WS_EX_TOPMOST)
    if was_topmost:
        return False
    if not USER32.SetWindowPos(hwnd, ctypes.c_void_p(-1), 0, 0, 0, 0,
                               SWP_KEEP_SIZE_AND_POSITION):
        raise RuntimeError("Nie udało się pokazać okna WoW.")
    time.sleep(0.12)
    return True


def restore_capture(hwnd, previous, raised_topmost):
    if raised_topmost:
        USER32.SetWindowPos(hwnd, ctypes.c_void_p(-2), 0, 0, 0, 0,
                            SWP_KEEP_SIZE_AND_POSITION)
    if (previous != hwnd and USER32.IsWindow(previous) and
            USER32.GetForegroundWindow() == hwnd):
        focus_window(previous)


def status():
    game = require_game_dir()
    window = wow_window()
    if not window:
        return {"game_installed": (game / "Wow.exe").is_file(),
                "game_running": False, "capture_ready": False}
    hwnd, title, rect = window
    minimized = bool(USER32.IsIconic(hwnd))
    return {"game_installed": True, "game_running": True,
            "window_title": title, "foreground": USER32.GetForegroundWindow() == hwnd,
            "minimized": minimized, "capture_ready": not minimized,
            "window_size": [rect.right - rect.left, rect.bottom - rect.top]}


def capture():
    window = wow_window()
    if not window:
        raise RuntimeError("WoW nie jest uruchomiony.")
    hwnd, _, rect = window
    if USER32.IsIconic(hwnd):
        raise RuntimeError("Przywróć zminimalizowane okno WoW i spróbuj ponownie.")
    if rect.right <= rect.left or rect.bottom <= rect.top:
        raise RuntimeError("Okno WoW ma nieprawidłowy rozmiar.")
    previous = USER32.GetForegroundWindow()
    raised_topmost = False
    try:
        raised_topmost = prepare_capture(hwnd)
        image = ImageGrab.grab(bbox=(rect.left, rect.top, rect.right, rect.bottom), all_screens=True)
    finally:
        restore_capture(hwnd, previous, raised_topmost)
    image.thumbnail((1280, 900))
    output = io.BytesIO()
    image.save(output, format="JPEG", quality=78, optimize=True)
    return {"type": "image", "data": base64.b64encode(output.getvalue()).decode("ascii"),
            "mimeType": "image/jpeg"}


def addons():
    root = require_game_dir() / "Interface" / "AddOns"
    result = []
    if root.is_dir():
        for folder in sorted(root.iterdir()):
            if folder.is_dir():
                toc = list(folder.glob("*.toc"))
                if toc:
                    result.append({"name": folder.name, "toc": [p.name for p in toc]})
    return {"addon_count": len(result), "addons": result}


def lua_string_after_assignment(source, variable):
    match = re.search(r"(?:^|\n)\s*" + re.escape(variable) + r'\s*=\s*"', source)
    if not match:
        raise ValueError("Nie znaleziono zapisanego eksportu WoW MCP.")
    result = []
    index = match.end()
    while index < len(source):
        char = source[index]
        index += 1
        if char == '"':
            return "".join(result)
        if char != "\\":
            result.append(char)
            continue
        if index >= len(source):
            break
        escaped = source[index]
        index += 1
        if escaped.isdigit():
            digits = escaped
            while index < len(source) and len(digits) < 3 and source[index].isdigit():
                digits += source[index]
                index += 1
            result.append(chr(int(digits, 10)))
        else:
            result.append({"n": "\n", "r": "\r", "t": "\t", "\\": "\\", '"': '"',
                           "a": "\a", "b": "\b", "f": "\f", "v": "\v"}.get(escaped, escaped))
    raise ValueError("Niepełny zapis WoW MCP w SavedVariables.")


def game_data():
    root = require_game_dir() / "WTF" / "Account"
    candidates = list(root.glob("*/SavedVariables/WoWMCPData.lua")) if root.is_dir() else []
    if not candidates:
        return {"available": False, "reason": "Brak zapisu dodatku WoWMCPData. Włącz go i użyj /reload lub wyloguj postać."}
    saved = max(candidates, key=lambda path: path.stat().st_mtime)
    if saved.stat().st_size > 2_000_000:
        raise ValueError("Zapis dodatku jest nieoczekiwanie duży; odczyt wstrzymany.")
    source = saved.read_text(encoding="utf-8-sig", errors="replace")
    data = json.loads(lua_string_after_assignment(source, "WoWMCPExport"))
    captured_at = data.get("captured_at")
    return {"available": True, "source": "WoW 3.3.5a addon SavedVariables",
            "live": False, "saved_at_unix": int(saved.stat().st_mtime),
            "captured_at_unix": captured_at,
            "age_seconds": max(0, int(time.time() - captured_at)) if isinstance(captured_at, (int, float)) else None,
            "refresh_instruction": "Wpisz /reload w grze, aby zapisać nowy stan bez zamykania WoW.",
            "data": data}


def combat_log(max_lines=40):
    path = require_game_dir() / "Logs" / "WoWCombatLog.txt"
    if not path.is_file():
        return {"available": False, "reason": "Dziennik walki nie jest włączony. W grze wpisz /combatlog, aby zacząć zapis."}
    max_lines = max(1, min(int(max_lines), 100))
    with path.open("rb") as stream:
        stream.seek(0, 2)
        size = stream.tell()
        stream.seek(max(0, size - 128_000))
        tail = stream.read().decode("utf-8", errors="replace")
    lines = tail.splitlines()
    if size > 128_000 and lines:
        lines = lines[1:]
    return {"available": True, "source": "WoWCombatLog.txt", "file_age_seconds": max(0, int(time.time() - path.stat().st_mtime)),
            "lines": lines[-max_lines:]}


def decode_panel_packet(image):
    pixels = np.asarray(image.convert("RGB"))
    area = pixels[:min(550, pixels.shape[0]), :min(450, pixels.shape[1]), :]
    magic = (87, 77, 67, 80)

    def near(pixel, byte):
        red = (byte // 16) * 17
        green = (byte % 16) * 17
        return (abs(int(pixel[0]) - red) <= 10 and
                abs(int(pixel[1]) - green) <= 10 and int(pixel[2]) >= 240)

    mask = ((np.abs(area[:, :, 0].astype(np.int16) - 85) <= 10) &
            (np.abs(area[:, :, 1].astype(np.int16) - 119) <= 10) &
            (area[:, :, 2] >= 240))
    ys, xs = np.where(mask)
    for y, x in zip(ys[:10000], xs[:10000]):
        for step in range(3, 9):
            if x + step * 3 >= area.shape[1]:
                continue
            if not all(near(area[y, x + step * offset], magic[offset]) for offset in range(1, 4)):
                continue
            left = int(x)
            while left > 0 and near(area[y, left - 1], magic[0]):
                left -= 1
            top = int(y)
            while top > 0 and near(area[top - 1, left + step // 2], magic[0]):
                top -= 1
            # The entire strip has a blue channel of 255. Measure its actual
            # width and height because WoW UI scale can stretch cells by a
            # fractional number of physical pixels, differently on each axis.
            edge_x = left
            while edge_x < area.shape[1] and area[top, edge_x, 2] >= 230:
                edge_x += 1
            edge_y = top
            while edge_y < area.shape[0] and area[edge_y, left, 2] >= 230:
                edge_y += 1
            candidates = [(float(edge_x - left) / 32, float(edge_y - top) / 16)]
            candidates.extend((step + tenth * 0.05, step + tenth * 0.05)
                              for tenth in range(-15, 16))
            for cell_x, cell_y in candidates:
                if not (2.5 <= cell_x <= 9 and 2.5 <= cell_y <= 9):
                    continue
                right = left + int((31.5) * cell_x)
                bottom = top + int((15.5) * cell_y)
                if right >= pixels.shape[1] or bottom >= pixels.shape[0]:
                    continue
                data = []
                valid = True
                for row in range(16):
                    yy = top + int((row + 0.5) * cell_y)
                    for col in range(32):
                        xx = left + int((col + 0.5) * cell_x)
                        r, g, b = pixels[yy, xx]
                        if b < 230:
                            valid = False
                            break
                        data.append(min(15, int(round(int(r) / 17))) * 16 +
                                    min(15, int(round(int(g) / 17))))
                    if not valid:
                        break
                if not valid or tuple(data[:4]) != magic or data[4] != 1:
                    continue
                generation, page, pages = data[5:8]
                fragment_length = data[8] + 256 * data[9]
                total_length = data[10] + 256 * data[11]
                checksum = data[12] + 256 * data[13]
                if not (1 <= page <= pages <= 255 and
                        0 < total_length <= 24000 and
                        pages == (total_length + 497) // 498 and
                        fragment_length == min(498, total_length - (page - 1) * 498)):
                    continue
                fragment = bytes(data[14:14 + fragment_length])
                if pages == 1 and sum(fragment) % 65536 != checksum:
                    continue
                return {"generation": generation, "page": page, "pages": pages,
                        "total_length": total_length, "checksum": checksum,
                        "fragment": fragment}
    return None


def expand_wire_data(value):
    if isinstance(value, list):
        return [expand_wire_data(item) for item in value]
    if isinstance(value, dict):
        return {WIRE_REVERSE.get(key, key): expand_wire_data(item) for key, item in value.items()}
    return value


def expand_compact_rows(data):
    if not isinstance(data, dict) or data.get("wire_version", 0) < 3:
        return data
    layouts = {
        "bags": ("id", "name", "count", "bag", "slot"),
        "equipment": ("id", "name", "count", "bag", "slot"),
        "spells": ("name", "rank", "tab"),
        "actions": ("slot", "kind", "id", "name", "usable", "cooldown"),
        "skills": ("name", "rank", "maximum"),
    }
    for section, columns in layouts.items():
        items = data.get(section)
        if not isinstance(items, list):
            continue
        expanded = []
        for item in items:
            if not isinstance(item, list):
                expanded.append(item)
                continue
            row = dict(zip(columns, item))
            if section in ("bags", "equipment"):
                if row.get("count") == 0:
                    row.pop("count", None)
                if row.get("bag") == -1:
                    row.pop("bag", None)
            elif section == "actions":
                if row.get("id") == 0:
                    row.pop("id", None)
                if not row.get("name"):
                    row.pop("name", None)
            expanded.append(row)
        data[section] = expanded
    return data


def live_game_data(timeout_seconds=20):
    window = wow_window()
    if not window:
        return {"available": False, "reason": "WoW nie jest uruchomiony."}
    hwnd, _, rect = window
    if USER32.IsIconic(hwnd):
        return {"available": False, "reason": "Okno WoW jest zminimalizowane."}
    previous = USER32.GetForegroundWindow()
    raised_topmost = False
    packets = {}
    active = None
    deadline = time.monotonic() + timeout_seconds
    try:
        raised_topmost = prepare_capture(hwnd)
        while time.monotonic() < deadline:
            image = ImageGrab.grab(
                bbox=(rect.left, max(rect.top, rect.bottom - 180),
                      min(rect.right, rect.left + 240),
                      rect.bottom),
                all_screens=True,
            )
            packet = decode_panel_packet(image)
            if packet:
                identity = (packet["generation"], packet["pages"], packet["total_length"], packet["checksum"])
                if identity != active:
                    active = identity
                    packets = {}
                packets[packet["page"]] = packet["fragment"]
                if len(packets) == packet["pages"]:
                    raw = b"".join(packets[index] for index in range(1, packet["pages"] + 1))
                    if len(raw) == packet["total_length"] and sum(raw) % 65536 == packet["checksum"]:
                        data = expand_compact_rows(expand_wire_data(json.loads(raw.decode("utf-8"))))
                        captured_at = data.get("captured_at")
                        return {"available": True, "source": "WoW addon visual data strip",
                                "age_seconds": max(0, int(time.time() - captured_at)) if isinstance(captured_at, (int, float)) else None,
                                "data": data}
            time.sleep(0.03)
    finally:
        restore_capture(hwnd, previous, raised_topmost)
    return {"available": False, "reason": "Nie udało się odczytać paska danych. Sprawdź, czy WoWMCPData jest włączony i użyj /reload w grze."}


_NATIVE_RECEIVER = None


def wow_native_status():
    return {"available": False, "enabled": False,
            "reason": "Tryb DLL jest wyłączony. Odczyt działa przez addon RGB."}


def read_wow_native_data():
    return {"available": False, "enabled": False, "data": None,
            "reason": "Tryb DLL jest wyłączony. Użyj read_wow_live_data."}


def read_best_wow_live_data():
    """Decode the lower-left WoWMCPData visual panel, without using any DLL."""
    return live_game_data()


TOOLS = [
    {"name": "wow_status", "description": "Check whether the local WoW 3.3.5a window is ready for an on-demand screenshot. Read-only.",
     "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
     "annotations": {"readOnlyHint": True, "destructiveHint": False}},
    {"name": "wow_native_status", "description": "Legacy status: DLL transport disabled. WoWMCPData visual strip is the active source.",
     "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
     "annotations": {"readOnlyHint": True, "destructiveHint": False}},
    {"name": "read_wow_native_data", "description": "Read the most recent validated snapshot from an experimental local DLL pipe. Unavailable if the receiver is disabled or the frame is stale (>30s). Optional native Lua adapter requires explicit separate game-side installation and testing.",
     "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
     "annotations": {"readOnlyHint": True, "destructiveHint": False}},
    {"name": "capture_wow", "description": "Capture one screenshot of the WoW window rectangle on user request. Briefly brings WoW forward and restores the previous window. Does not control the character. Other windows overlapping the rectangle can appear in the image.",
     "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
     "annotations": {"readOnlyHint": True, "destructiveHint": False}},
    {"name": "list_wow_addons", "description": "List installed WoW addon folders and TOC filenames, without reading accounts or settings.",
     "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
     "annotations": {"readOnlyHint": True, "destructiveHint": False}},
    {"name": "read_wow_game_data", "description": "Read a structured snapshot collected by the WoWMCPData addon: character stats, location, target, quests/objectives, bags, equipment and spellbook. The file updates only on /reload or logout; always report its age and never describe it as live data.",
     "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
     "annotations": {"readOnlyHint": True, "destructiveHint": False}},
    {"name": "read_wow_combat_log", "description": "Read the latest raw WoW combat-log lines if /combatlog is enabled in game. Report file age; a missing or old file is not live combat data.",
     "inputSchema": {"type": "object", "properties": {"max_lines": {"type": "integer", "minimum": 1, "maximum": 100}}, "additionalProperties": False},
     "annotations": {"readOnlyHint": True, "destructiveHint": False}},
    {"name": "read_wow_live_data", "description": "Read current WoW 3.3.5a data by decoding the WoWMCPData 32x16 colored rectangle in the bottom-left of the game screen. On-demand screenshot only, no DLL or game injection. Reports age, character, quests, bags, equipment, abilities and talents.",
     "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
     "annotations": {"readOnlyHint": True, "destructiveHint": False}},
]


def reply(req):
    method = req.get("method")
    request_id = req.get("id")
    if request_id is None:
        return None
    if method in ("initialize", "tools/list", "tools/call"):
        hub = NativeHubClient.discover()
        if hub is not None:
            hub.announce_mcp()
    try:
        if method == "initialize":
            result = {"protocolVersion": "2025-06-18", "capabilities": {"tools": {}},
                      "serverInfo": {"name": "wow-335-live-mcp", "version": "0.7.0"}}
        elif method == "ping":
            result = {}
        elif method == "tools/list":
            result = {"tools": TOOLS}
        elif method == "tools/call":
            name = req.get("params", {}).get("name")
            if name == "wow_status":
                result = {"content": [{"type": "text", "text": json.dumps(status(), ensure_ascii=False)}]}
            elif name == "list_wow_addons":
                result = {"content": [{"type": "text", "text": json.dumps(addons(), ensure_ascii=False)}]}
            elif name == "read_wow_game_data":
                result = {"content": [{"type": "text", "text": json.dumps(game_data(), ensure_ascii=False)}]}
            elif name == "read_wow_combat_log":
                result = {"content": [{"type": "text", "text": json.dumps(combat_log(req.get("params", {}).get("arguments", {}).get("max_lines", 40)), ensure_ascii=False)}]}
            elif name == "wow_native_status":
                result = {"content": [{"type": "text", "text": json.dumps(wow_native_status(), ensure_ascii=False)}]}
            elif name == "read_wow_native_data":
                result = {"content": [{"type": "text", "text": json.dumps(read_wow_native_data(), ensure_ascii=False)}]}
            elif name == "read_wow_live_data":
                result = {"content": [{"type": "text", "text": json.dumps(read_best_wow_live_data(), ensure_ascii=False)}]}
            elif name == "capture_wow":
                result = {"content": [capture()]}
            else:
                raise ValueError("Unknown tool")
        else:
            return {"jsonrpc": "2.0", "id": request_id,
                    "error": {"code": -32601, "message": "Method not found"}}
        return {"jsonrpc": "2.0", "id": request_id, "result": result}
    except Exception as exc:
        return {"jsonrpc": "2.0", "id": request_id,
                "result": {"content": [{"type": "text", "text": str(exc)}], "isError": True}}


def main():
    # Pure stdio MCP: don't open a DLL pipe or inject a game module.
    for line in sys.stdin:
        try:
            response = reply(json.loads(line))
            if response is not None:
                # MCP stdio is UTF-8. ASCII JSON escapes keep the wire format
                # valid even when Windows gives redirected stdout a legacy codepage.
                sys.stdout.write(json.dumps(response, ensure_ascii=True, separators=(",", ":")) + "\n")
                sys.stdout.flush()
        except Exception as exc:
            print(f"Malformed MCP request: {exc}", file=sys.stderr)


if __name__ == "__main__":
    main()
