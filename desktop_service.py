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
from ui_models import metrics, select_snapshot, source_label

SETTINGS_FILE = DISCOVERY_FILE.parent / "settings.json"


class DisabledNativeReceiver:
    """API-compatible null receiver: never opens a DLL named pipe."""
    def status(self):
        return {"available": False, "enabled": False, "reason": "Tryb DLL jest wyłączony."}

    def snapshot(self):
        return {"available": False, "enabled": False, "data": None,
                "reason": "Odczyt wyłącznie przez pasek addonu."}


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
        self._mcp_last_seen = 0.0
        self._mcp_calls = 0
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
        try:
            settings = json.loads(self.settings_file.read_text(encoding="utf-8"))
            if not self._game_dir:
                self._game_dir = settings.get("game_dir") or ""
        except (ValueError, OSError):
            pass

    def get_settings(self):
        with self._lock:
            return {"game_dir": self._game_dir, "auto_read": False, "launch_mode": "addon"}

    def set_settings(self, body):
        if not isinstance(body, dict) or not body or not set(body) <= {"game_dir", "launch_mode"}:
            raise ValueError("Expected game_dir or launch_mode")
        if body.get("launch_mode", "addon") != "addon":
            raise ValueError("Tryb DLL wyłączony. Używany jest tylko addon RGB.")
        location = body.get("game_dir", self._game_dir)
        if not isinstance(location, str) or len(location) > 1024:
            raise ValueError("Invalid game_dir")
        if location and not (Path(location) / "Wow.exe").is_file():
            raise ValueError("Folder must contain Wow.exe")
        with self._lock:
            self._game_dir = location
            self._game_checked_at = 0.0
            self._game_checked_dir = None
            self._game_running = False
            self._launch_state = "idle"
            self._launch_message = "Gotowe do uruchomienia gry."
            self._addon_backup = None
            self.settings_file.parent.mkdir(parents=True, exist_ok=True)
            temp = self.settings_file.with_suffix(".tmp")
            temp.write_text(json.dumps({"game_dir": location, "launch_mode": "addon"},
                                       ensure_ascii=False), encoding="utf-8")
            os.replace(temp, self.settings_file)
        return self.get_settings()

    def request_launch(self):
        """Queue addon setup and launch without blocking HTTP or the app window."""
        with self._lock:
            if self._launch_busy:
                return {"started": False, "reason": "already_starting"}
            game_dir = self._game_dir
            if not game_dir or not (Path(game_dir) / "Wow.exe").is_file():
                return {"started": False, "reason": "game_dir_missing"}
            self._launch_busy = True
            self._launch_state = "installing"
            self._launch_message = "Przygotowywanie addonu WoWMCPData..."
            self._addon_backup = None
        threading.Thread(target=self._launch_worker, args=(game_dir,),
                         daemon=True, name="wow-one-click-launch").start()
        return {"started": True}

    def _launch_worker(self, game_dir):
        try:
            result = install_addon(game_dir)
            with self._lock:
                self._addon_backup = result.backup
                self._launch_state = "starting"
                self._launch_message = "Uruchamianie Wow.exe..."
            if find_game_running(game_dir):
                with self._lock:
                    self._launch_state = "already_running"
                    self._launch_message = (
                        "WoW już działa. " +
                        ("Wpisz /reload, aby wczytać zaktualizowany addon."
                         if result.changed else "Addon jest gotowy.")
                    )
                    self._game_checked_dir = game_dir
                    self._game_checked_at = time.monotonic()
                    self._game_running = True
            else:
                launch_wow(game_dir)
                with self._lock:
                    self._launch_state = "started"
                    self._launch_message = (
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
                self._updated_at = time.time()
        except Exception as exc:
            with self._lock:
                self._error = str(exc)[:350]
        finally:
            with self._lock:
                self._busy = False

    def record_mcp_activity(self):
        """An authenticated local MCP request occurred; not proof of cloud access."""
        with self._lock:
            self._mcp_last_seen = time.time()
            self._mcp_calls += 1
        return {"recorded": True}

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
            busy = self._busy
            error = self._error
            game_dir = self._game_dir
            last_read = self._updated_at
            mcp_last_seen = self._mcp_last_seen
            mcp_calls = self._mcp_calls
            launch = {"status": self._launch_state,
                      "busy": self._launch_busy,
                      "message": self._launch_message,
                      "backup": self._addon_backup}
        # Only accept recent screenshot-decoded WoWMCPData packets. No DLL input.
        active = select_snapshot({}, visual)
        available = active.get("available") is True
        data = metrics(active) if available else metrics({})
        game_installed = bool(game_dir and (Path(game_dir) / "Wow.exe").is_file())
        last_seen_age = max(0, time.time() - mcp_last_seen) if mcp_last_seen else None
        return {
            "available": available,
            "source": active.get("source"),
            "source_label": source_label(active),
            "demo": False,
            "data": active.get("data") if available else None,
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
            "launch_mode": "addon",
            "transport": self.receiver.status(),
            "mcp_client": {"recent": last_seen_age is not None and last_seen_age < 90,
                           "last_seen_seconds": round(last_seen_age, 1) if last_seen_age is not None else None,
                           "requests": mcp_calls,
                           "note": "Aktywność lokalnego procesu MCP, nie potwierdzenie chmury ChatGPT."},
        }


def main():
    receiver = DisabledNativeReceiver()
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
