"""Background service for the Tauri desktop app.

Owns the Windows Named Pipe once, serves a local authenticated API shared with
the Tauri frontend and existing MCP client. Does not inject into WoW.
"""
import json
import os
from pathlib import Path
import subprocess
import threading
import time

from native_bridge.hub import NativeHubServer, DISCOVERY_FILE
from native_bridge.pipe import NativePipeReceiver
from ui_models import metrics, select_snapshot, source_label

SETTINGS_FILE = DISCOVERY_FILE.parent / "settings.json"


def find_game_running(game_dir):
    if os.name != "nt":
        return False
    try:
        result = subprocess.run(
            ["tasklist", "/fi", "IMAGENAME eq Wow.exe", "/fo", "csv", "/nh"],
            capture_output=True, text=True, timeout=3)
        return '"Wow.exe"' in result.stdout
    except (OSError, subprocess.TimeoutExpired):
        return False


class DesktopState:
    def __init__(self, receiver, settings_file=SETTINGS_FILE):
        self.receiver = receiver
        self.settings_file = Path(settings_file)
        self._lock = threading.RLock()
        self._visual = None
        self._demo = None
        self._busy = False
        self._error = None
        self._reading_since = None
        self._updated_at = 0
        self._game_dir = os.environ.get("WOW_GAME_DIR") or ""
        try:
            settings = json.loads(self.settings_file.read_text(encoding="utf-8"))
            if not self._game_dir:
                self._game_dir = settings.get("game_dir") or ""
        except (ValueError, OSError):
            pass

    def get_settings(self):
        with self._lock:
            return {"game_dir": self._game_dir, "auto_read": False}

    def set_settings(self, body):
        if not isinstance(body, dict) or set(body) != {"game_dir"}:
            raise ValueError("Expected game_dir")
        location = body["game_dir"]
        if not isinstance(location, str) or len(location) > 1024:
            raise ValueError("Invalid game_dir")
        if location and not (Path(location) / "Wow.exe").is_file():
            raise ValueError("Folder must contain Wow.exe")
        with self._lock:
            self._game_dir = location
            self.settings_file.parent.mkdir(parents=True, exist_ok=True)
            temp = self.settings_file.with_suffix(".tmp")
            temp.write_text(json.dumps({"game_dir": location}, ensure_ascii=False), encoding="utf-8")
            os.replace(temp, self.settings_file)
        return self.get_settings()

    def request_refresh(self):
        with self._lock:
            if self._busy:
                return {"started": False, "reason": "already_running"}
            game_dir = self._game_dir
            if not game_dir or not (Path(game_dir) / "Wow.exe").is_file():
                return {"started": False, "reason": "game_dir_missing"}
            self._busy = True
            self._reading_since = time.time()
            self._error = None
        thread = threading.Thread(target=self._read_visual, args=(game_dir,),
                                  daemon=True, name="wow-visual-refresh")
        thread.start()
        return {"started": True}

    def _read_visual(self, game_dir):
        try:
            import server
            server.GAME = Path(game_dir).expanduser().resolve()
            result = server.live_game_data()
            if not result.get("available"):
                raise RuntimeError(result.get("reason", "WoW visual read unavailable"))
            with self._lock:
                self._visual = result
                self._demo = None
                self._updated_at = time.time()
        except Exception as exc:
            with self._lock:
                self._error = str(exc)[:350]
        finally:
            with self._lock:
                self._busy = False

    def show_demo(self):
        """Explicitly labeled synthetic data for preview only."""
        now = time.time()
        demo = {
            "available": True, "source": "demo",
            "data": {
                "captured_at": now,
                "character": {
                    "name": "Postać demonstracyjna", "realm": "DEMO / Offline",
                    "class": "MAGE", "race": "HUMAN", "level": 32,
                    "health": 1450, "health_max": 1890, "power": 850,
                    "power_max": 1200, "xp": 33500, "xp_max": 47000,
                    "money_copper": 125460,
                },
                "location": {"zone": "Stranglethorn Vale", "subzone": "Booty Bay"},
                "quests": [
                    {"title": "Przykładowe zadanie — zbierz przedmioty",
                     "level": 31, "ready_to_turn_in": False,
                     "objectives": [{"text": "Zebrano 6 / 10 przedmiotów", "done": False}]},
                    {"title": "Przykładowe zadanie — wróć do NPC",
                     "level": 30, "ready_to_turn_in": True, "objectives": []},
                ],
                "bags": [{"id": 117, "name": "Tough Jerky", "count": 4}],
                "equipment": [{"id": 35, "name": "Przykładowy miecz", "count": 1}],
            },
        }
        with self._lock:
            self._demo = demo
        return {"demo": True}

    def dashboard(self):
        with self._lock:
            visual = self._visual
            demo = self._demo
            busy = self._busy
            error = self._error
            game_dir = self._game_dir
            last_read = self._updated_at
        native = self.receiver.snapshot()
        active = select_snapshot(native, visual)
        if not active.get("available") and demo is not None:
            active = demo
        data = metrics(active) if active.get("available") else metrics({})
        source = source_label(active)
        if active.get("source") == "demo":
            source = "DEMO · dane demonstracyjne"
        transport = self.receiver.status()
        game_installed = bool(game_dir and (Path(game_dir) / "Wow.exe").is_file())
        return {
            "available": bool(active.get("available")),
            "source": active.get("source"),
            "source_label": source,
            "demo": active.get("source") == "demo" or
                    (active.get("source") == "experimental native DLL named pipe" and
                     data["name"] == "Demo"),
            "data": active.get("data") if active.get("available") else None,
            "metrics": {key: value for key, value in data.items() if key not in
                        ("quests", "bags", "equipment")},
            "read_in_progress": busy,
            "last_visual_read": last_read,
            "error": error,
            "game": {"installed": game_installed, "running": find_game_running(game_dir),
                     "directory": game_dir},
            "transport": transport,
        }


def main():
    receiver = NativePipeReceiver()
    receiver.start()
    state = DesktopState(receiver)
    hub = NativeHubServer(receiver, dashboard=state)
    hub.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        hub.stop()


if __name__ == "__main__":
    main()
