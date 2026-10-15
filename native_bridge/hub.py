"""Same-user-ish loopback discovery for the GUI-hosted native bridge.

The GUI owns the telemetry pipe. A separate MCP stdio process reads snapshots
via a randomly authenticated 127.0.0.1 HTTP endpoint (not a public server).
"""
import hmac
import json
import os
from pathlib import Path
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib import error, request

DISCOVERY_FILE = Path(os.environ.get("LOCALAPPDATA") or (Path.home() / ".local" / "share")) / "WoWMCP" / "control-center.json"


class NativeHubClient:
    def __init__(self, port, token):
        self.port = port
        self.token = token

    @classmethod
    def discover(cls, path=DISCOVERY_FILE):
        try:
            config = json.loads(Path(path).read_text(encoding="utf-8"))
            port, token = config["port"], config["token"]
            if not (type(port) is int and 0 < port < 65536 and
                    isinstance(token, str) and len(token) == 64):
                return None
            return cls(port, token)
        except (OSError, ValueError, KeyError, TypeError):
            return None

    def _get(self, endpoint):
        url = "http://127.0.0.1:%d%s" % (self.port, endpoint)
        headers = {"X-WoWMCP-Token": self.token}
        try:
            with request.urlopen(request.Request(url, headers=headers), timeout=0.4) as response:
                return json.loads(response.read(1024 * 1024).decode("utf-8"))
        except (OSError, ValueError, error.URLError):
            return None

    def _post(self, endpoint, payload):
        url = "http://127.0.0.1:%d%s" % (self.port, endpoint)
        headers = {"X-WoWMCP-Token": self.token,
                   "Content-Type": "application/json"}
        body = json.dumps(payload).encode("utf-8")
        try:
            req = request.Request(url, data=body, headers=headers, method="POST")
            with request.urlopen(req, timeout=1) as response:
                return json.loads(response.read(1024 * 1024).decode("utf-8"))
        except (OSError, ValueError, error.URLError):
            return None

    def status(self):
        return self._get("/v1/status")

    def snapshot(self):
        return self._get("/v1/snapshot")

    def settings(self):
        """Read the configured WoW path from the authenticated desktop service."""
        return self._get("/v2/settings")

    def announce_mcp(self):
        """Mark a real MCP protocol request as seen by the local desktop hub."""
        return self._post("/v2/mcp-activity", {})



class NativeHubServer:
    def __init__(self, receiver, discovery_file=DISCOVERY_FILE, dashboard=None):
        self.receiver = receiver
        self.dashboard = dashboard
        self.discovery_file = Path(discovery_file)
        self.token = secrets.token_hex(32)
        self._httpd = None
        self._thread = None

    def start(self):
        if self._httpd is not None:
            return True
        current = NativeHubClient.discover(self.discovery_file)
        if current is not None and current.status() is not None:
            raise RuntimeError("WoW MCP Control Center is already running.")
        self.discovery_file.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        hub = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                provided = self.headers.get("X-WoWMCP-Token", "")
                if not hmac.compare_digest(provided, hub.token):
                    self.send_error(403)
                    return
                if self.path == "/v1/status":
                    payload = hub.receiver.status()
                elif self.path == "/v1/snapshot":
                    payload = hub.receiver.snapshot()
                elif self.path == "/v2/dashboard" and hub.dashboard is not None:
                    payload = hub.dashboard.dashboard()
                elif self.path == "/v2/settings" and hub.dashboard is not None:
                    payload = hub.dashboard.get_settings()
                else:
                    self.send_error(404)
                    return
                encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(encoded)))
                self.end_headers()
                self.wfile.write(encoded)

            def do_POST(self):
                provided = self.headers.get("X-WoWMCP-Token", "")
                if not hmac.compare_digest(provided, hub.token):
                    self.send_error(403)
                    return
                if hub.dashboard is None:
                    self.send_error(404)
                    return
                size = self.headers.get("Content-Length")
                try:
                    if size is None or not 0 <= int(size) <= 4096:
                        raise ValueError("Request too large")
                    raw = self.rfile.read(int(size))
                    body = json.loads(raw or b"{}")
                    if not isinstance(body, dict):
                        raise ValueError("Expected JSON object")
                    if self.path == "/v2/refresh" and not body:
                        payload = hub.dashboard.request_refresh()
                    elif self.path == "/v2/launch" and not body:
                        payload = hub.dashboard.request_launch()
                    elif self.path == "/v2/demo" and not body:
                        payload = hub.dashboard.show_demo()
                    elif self.path == "/v2/settings":
                        payload = hub.dashboard.set_settings(body)
                    elif self.path == "/v2/mcp-activity" and not body:
                        payload = hub.dashboard.record_mcp_activity()
                    else:
                        self.send_error(404)
                        return
                except (ValueError, UnicodeError, KeyError) as exc:
                    self.send_error(400, str(exc)[:200])
                    return
                encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(encoded)))
                self.end_headers()
                self.wfile.write(encoded)

            def log_message(self, *_):
                pass

        self._httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._httpd.daemon_threads = True
        discovery = {
            "port": self._httpd.server_address[1],
            "token": self.token,
        }
        temp = self.discovery_file.with_suffix(".tmp")
        try:
            with open(temp, "w", encoding="utf-8") as fh:
                json.dump(discovery, fh)
            os.chmod(temp, 0o600)
            os.replace(temp, self.discovery_file)
            self._thread = threading.Thread(target=self._httpd.serve_forever,
                                            name="wow-hub-http", daemon=True)
            self._thread.start()
        except Exception:
            self._httpd.server_close()
            self._httpd = None
            try:
                temp.unlink(missing_ok=True)
            except OSError:
                pass
            raise
        return True

    def stop(self):
        if self._httpd is None:
            return
        self._httpd.shutdown()
        self._httpd.server_close()
        self._thread.join(timeout=3)
        self._httpd = None
        try:
            current = json.loads(self.discovery_file.read_text(encoding="utf-8"))
            if current.get("token") == self.token:
                self.discovery_file.unlink()
        except (OSError, ValueError):
            pass
