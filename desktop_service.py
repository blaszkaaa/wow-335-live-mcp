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

from game_launcher import addon_installed, install_addon, launch_wow
from native_bridge.hub import NativeHubServer, DISCOVERY_FILE
from native_bridge.pipe import NativePipeReceiver
from native_bridge.diagnostics import inspect_native_runtime
from native_bridge.setup import native_bundle_ready, setup_native_runtime
from ui_models import metrics, select_snapshot, source_label

SETTINGS_FILE = DISCOVERY_FILE.parent / "settings.json"


def find_game_running(game_dir):
    if os.name != "nt":
        return False
    try:
        result = subprocess.run(
            ["tasklist", "/fi", "IMAGENAME eq Wow.exe", "/fo", "csv", "/nh"],
            capture_output=True, text=True, timeout=3,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000))
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
        # Cache process discovery. Never block an HTTP dashboard request on tasklist.
        self._game_checked_at = 0.0
        self._game_checked_dir = None
        self._game_checking = False
        self._game_running = False
        self._launch_busy = False
        self._launch_state = "idle"
        self._launch_message = "Wybierz folder gry, aby rozpocząć."
        self._addon_backup = None
        self._game_dir = os.environ.get("WOW_GAME_DIR") or ""
        self._launch_mode = "addon"
        try:
            settings = json.loads(self.settings_file.read_text(encoding="utf-8"))
            if not self._game_dir:
                self._game_dir = settings.get("game_dir") or ""
            if settings.get("launch_mode") in ("addon", "native"):
                self._launch_mode = settings["launch_mode"]
        except (ValueError, OSError):
            pass

    def get_settings(self):
        with self._lock:
            return {"game_dir": self._game_dir, "auto_read": False,
                    "launch_mode": self._launch_mode}

    def set_settings(self, body):
        """Update only named settings; changing modes never erases the game path."""
        if not isinstance(body, dict) or not body or not set(body) <= {"game_dir", "launch_mode"}:
            raise ValueError("Expected game_dir or launch_mode")
        location = body.get("game_dir", self._game_dir)
        mode = body.get("launch_mode", self._launch_mode)
        if not isinstance(location, str) or len(location) > 1024:
            raise ValueError("Invalid game_dir")
        if location and not (Path(location) / "Wow.exe").is_file():
            raise ValueError("Folder must contain Wow.exe")
        if mode not in ("addon", "native"):
            raise ValueError("Invalid launch_mode")
        with self._lock:
            if self._launch_busy:
                raise ValueError("Wait until game launch completes")
            changed = location != self._game_dir
            self._game_dir = location
            self._launch_mode = mode
            if changed:
                self._game_checked_at = 0.0
                self._game_checked_dir = None
                self._game_running = False
            self._launch_state = "idle"
            self._launch_message = "Gotowe do uruchomienia gry."
            self._addon_backup = None
            self.settings_file.parent.mkdir(parents=True, exist_ok=True)
            temp = self.settings_file.with_suffix(".tmp")
            temp.write_text(json.dumps({"game_dir": location, "launch_mode": mode},
                                       ensure_ascii=False), encoding="utf-8")
            os.replace(temp, self.settings_file)
        return self.get_settings()

    def request_launch(self):
        """Queue addon setup and launch without blocking HTTP or the app window."""
        with self._lock:
            if self._launch_busy:
                return {"started": False, "reason": "already_starting"}
            game_dir = self._game_dir
            mode = self._launch_mode
            if not game_dir or not (Path(game_dir) / "Wow.exe").is_file():
                return {"started": False, "reason": "game_dir_missing"}
            self._launch_busy = True
            self._launch_state = "installing"
            self._launch_message = "Przygotowywanie addonu WoWMCPData..."
            self._addon_backup = None
        threading.Thread(target=self._launch_worker, args=(game_dir, mode),
                         daemon=True, name="wow-one-click-launch").start()
        return {"started": True}

    def _launch_worker(self, game_dir, mode="addon"):
        try:
            result = install_addon(game_dir)
            with self._lock:
                self._addon_backup = result.backup
            if find_game_running(game_dir):
                with self._lock:
                    self._launch_state = "already_running"
                    self._launch_message = (
                        "Zamknij działającą grę i uruchom WoW ponownie w trybie DLL. "
                        "LichLoader musi wystartować przed grą."
                        if mode == "native" else
                        "WoW już działa. " +
                        ("Wpisz /reload, aby wczytać zaktualizowany addon."
                         if result.changed else "Addon jest gotowy.")
                    )
                    self._game_checked_dir = game_dir
                    self._game_checked_at = time.monotonic()
                    self._game_running = True
                return
            if mode == "native":
                with self._lock:
                    self._launch_state = "installing"
                    self._launch_message = "Instalowanie składników DLL z pakietu aplikacji..."
                setup_native_runtime(game_dir)
            with self._lock:
                self._launch_state = "starting"
                self._launch_message = ("Uruchamianie przez LichLoader..." if mode == "native"
                                        else "Uruchamianie Wow.exe...")
            if mode == "native":
                launch_wow(game_dir, mode="native")
            else:
                launch_wow(game_dir)
            with self._lock:
                self._launch_state = "started"
                self._launch_message = (
                    "Uruchomiono WoW z przygotowaną DLL. Oczekiwanie na dane z gry."
                    if mode == "native" else
                    "Uruchomiono WoW z addonem. Jeśli to pierwsze uruchomienie, "
                    "włącz WoW MCP Data na ekranie wyboru postaci.")
                self._game_checked_at = 0.0
                self._game_checked_dir = None
        except (OSError, ValueError, RuntimeError) as exc:
            with self._lock:
                self._launch_state = "error"
                self._launch_message = str(exc)[:400]
        finally:
            with self._lock:
                self._launch_busy = False

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

    def _cached_game_running(self, game_dir):
        """Return cached state instantly and refresh the process check in the background."""
        with self._lock:
            now = time.monotonic()
            valid = self._game_checked_dir == game_dir
            running = self._game_running if valid else False
            should_check = (
                bool(game_dir) and
                not self._game_checking and
                (not valid or now - self._game_checked_at >= 8.0)
            )
            if should_check:
                self._game_checking = True
        if should_check:
            threading.Thread(
                target=self._refresh_game_status,
                args=(game_dir,),
                daemon=True,
                name="wow-process-discovery",
            ).start()
        return running

    def _refresh_game_status(self, game_dir):
        try:
            running = find_game_running(game_dir)
            with self._lock:
                if self._game_dir == game_dir:
                    self._game_running = running
                    self._game_checked_dir = game_dir
                    self._game_checked_at = time.monotonic()
        finally:
            with self._lock:
                self._game_checking = False

    def dashboard(self):
        with self._lock:
            visual = self._visual
            demo = self._demo
            busy = self._busy
            error = self._error
            game_dir = self._game_dir
            last_read = self._updated_at
            launch = {"status": self._launch_state,
                      "busy": self._launch_busy,
                      "message": self._launch_message,
                      "backup": self._addon_backup}
        native = self.receiver.snapshot()
        active = select_snapshot(native, visual)
        if not active.get("available") and demo is not None:
            active = demo
        data = metrics(active) if active.get("available") else metrics({})
        source = source_label(active)
        if active.get("source") == "demo":
            source = "DEMO · dane demonstracyjne"
        transport = self.receiver.status()
        native_files = inspect_native_runtime(game_dir)
        native_files["bundled"] = native_bundle_ready()
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
            "game": {"installed": game_installed,
                     "running": self._cached_game_running(game_dir),
                     "directory": game_dir,
                     "addon_installed": bool(game_installed and addon_installed(game_dir))},
            "launch": launch,
            "launch_mode": self._launch_mode,
            "transport": transport,
            "native_setup": native_files,
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
