"""WoW MCP Control Center — zero-extra-dependency desktop GUI for Windows.

Run: py -3 desktop_app.py

The GUI hosts the experimental local native telemetry receiver and publishes its
read-only state to independently launched MCP servers via an authenticated
loopback endpoint. It does NOT inject code into WoW.
"""
import datetime
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import messagebox, ttk

from native_bridge.hub import NativeHubServer
from native_bridge.pipe import NativePipeReceiver

BG = "#0D1119"
SIDEBAR = "#111721"
PANEL = "#181F2B"
PANEL_ALT = "#202A39"
BORDER = "#2B3545"
FG = "#F3F4F6"
MUTED = "#96A3B6"
ACCENT = "#10A37F"
WARNING = "#F0B65D"
FONT = "Segoe UI"


def time_label(timestamp):
    if not isinstance(timestamp, (int, float)):
        return "—"
    try:
        return datetime.datetime.fromtimestamp(timestamp).strftime("%H:%M:%S")
    except (OSError, OverflowError, ValueError):
        return "—"


def source_label(snapshot):
    if not snapshot.get("available"):
        return "Brak świeżych danych"
    if snapshot.get("data", {}).get("character", {}).get("name") == "Demo":
        return "Dane demonstracyjne — NIE z WoW"
    return "Dane z eksperymentalnego kanału DLL"


class ControlCenter(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("WoW MCP Control Center")
        self.geometry("1130x760")
        self.minsize(890, 610)
        self.configure(bg=BG)

        self.receiver = NativePipeReceiver()
        self.hub = NativeHubServer(self.receiver)
        self.messages = []
        self.last_seq = None
        self.last_available = None
        self.section = "Przegląd"
        self._game_status = {"game_running": False, "game_installed": False}
        self._result_queue = queue.Queue()

        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("WoW.Horizontal.TProgressbar", troughcolor=PANEL_ALT,
                        background=ACCENT, borderwidth=0, lightcolor=ACCENT,
                        darkcolor=ACCENT)

        self._construct()
        try:
            self.hub.start()
            if not self.receiver.start():
                self._log("Odbiornik DLL nie wystartował (wymagany Windows).")
            else:
                self._log("Uruchomiono odbiornik DLL i lokalny serwer GUI.")
        except Exception as exc:
            self._log("Nie udało się uruchomić centrum: " + str(exc))
            messagebox.showerror("WoW MCP", str(exc), parent=self)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._refresh()
        self._check_game_async()

    def _text(self, parent, text, size=11, color=FG, bold=False, **kwargs):
        return tk.Label(parent, text=text, font=(FONT, size, "bold" if bold else "normal"),
                        bg=parent.cget("bg"), fg=color, anchor="w", **kwargs)

    def _card(self, parent, padding=18):
        outer = tk.Frame(parent, bg=PANEL, highlightthickness=1,
                         highlightbackground=BORDER)
        inner = tk.Frame(outer, bg=PANEL)
        inner.pack(fill="both", expand=True, padx=padding, pady=padding)
        return outer, inner

    def _button(self, parent, title, callback, primary=False):
        color = ACCENT if primary else PANEL_ALT
        btn = tk.Button(parent, text=title, command=callback, bg=color, fg=FG,
                        activebackground="#149B7E" if primary else BORDER,
                        activeforeground=FG, relief="flat", bd=0,
                        font=(FONT, 10, "bold"), cursor="hand2", padx=15, pady=10)
        return btn

    def _construct(self):
        shell = tk.Frame(self, bg=BG)
        shell.pack(fill="both", expand=True)
        nav = tk.Frame(shell, bg=SIDEBAR, width=220)
        nav.pack(side="left", fill="y")
        nav.pack_propagate(False)

        self._text(nav, "◈  WoW MCP", size=18, bold=True).pack(
            anchor="w", padx=21, pady=(28, 2))
        self._text(nav, "CONTROL CENTER", size=9, color=MUTED).pack(
            anchor="w", padx=23, pady=(0, 37))

        self.nav_buttons = {}
        for title, glyph in [
            ("Przegląd", "▦"), ("Postać", "♙"), ("Zadania", "☷"),
            ("Diagnostyka", "⌁"), ("Ustawienia", "⚙"),
        ]:
            btn = tk.Button(nav, text="  " + glyph + "   " + title,
                            font=(FONT, 11), anchor="w", padx=14, pady=13,
                            bg=SIDEBAR, fg=MUTED, relief="flat", bd=0,
                            activeforeground=FG, activebackground=PANEL_ALT,
                            cursor="hand2",
                            command=lambda name=title: self._show(name))
            btn.pack(fill="x", padx=11, pady=2)
            self.nav_buttons[title] = btn

        tk.Frame(nav, bg=SIDEBAR).pack(expand=True, fill="both")
        self._text(nav, "WoW 3.3.5a  •  Experimental", size=9,
                   color=MUTED).pack(anchor="w", padx=20, pady=20)

        self.main = tk.Frame(shell, bg=BG)
        self.main.pack(side="left", fill="both", expand=True)
        head = tk.Frame(self.main, bg=BG)
        head.pack(fill="x", padx=35, pady=(27, 15))
        self.heading = self._text(head, "Przegląd", size=23, bold=True)
        self.heading.pack(side="left")
        self.connection = self._text(head, "●  Oczekiwanie na dane", size=10, color=WARNING)
        self.connection.pack(side="right", pady=9)

        self.content = tk.Frame(self.main, bg=BG)
        self.content.pack(fill="both", expand=True, padx=35, pady=(2, 24))
        self._show("Przegląd")

    def _show(self, section):
        self.section = section
        self.heading.configure(text=section)
        for title, btn in self.nav_buttons.items():
            btn.configure(bg=PANEL_ALT if title == section else SIDEBAR,
                          fg=FG if title == section else MUTED)
        for child in self.content.winfo_children():
            child.destroy()

        if section == "Przegląd":
            self._overview()
        elif section == "Postać":
            self._character()
        elif section == "Zadania":
            self._quests()
        elif section == "Diagnostyka":
            self._diagnostics()
        elif section == "Ustawienia":
            self._settings()

    def _overview(self):
        self._text(self.content, "Stan połączenia i najważniejsze informacje o postaci.",
                   size=11, color=MUTED).pack(anchor="w", pady=(0, 23))
        grid = tk.Frame(self.content, bg=BG)
        grid.pack(fill="x")
        self.metric_labels = {}
        for index, (key, label) in enumerate([
            ("level", "POZIOM"), ("health", "ZDROWIE"),
            ("zone", "LOKALIZACJA"), ("quests", "AKTYWNE ZADANIA"),
        ]):
            grid.columnconfigure(index, weight=1)
            card, inner = self._card(grid, 16)
            card.grid(row=0, column=index, sticky="nsew", padx=(0, 11) if index < 3 else 0)
            self._text(inner, label, size=9, color=MUTED, bold=True).pack(anchor="w")
            value = self._text(inner, "—", size=19, bold=True)
            value.pack(anchor="w", pady=(13, 0))
            self.metric_labels[key] = value

        section, inside = self._card(self.content, 21)
        section.pack(fill="x", pady=(23, 0))
        self._text(inside, "Status transmisji", size=15, bold=True).pack(anchor="w")
        self.overview_status = self._text(inside, "Oczekiwanie na połączenie...", size=11,
                                          color=MUTED, wraplength=650)
        self.overview_status.pack(anchor="w", pady=(14, 10))
        buttons = tk.Frame(inside, bg=PANEL)
        buttons.pack(anchor="w", pady=(10, 0))
        self._button(buttons, "Wyślij dane testowe", self._run_demo, True).pack(side="left")
        self._button(buttons, "Sprawdź uruchomienie WoW", self._check_game_async).pack(
            side="left", padx=(10, 0))

        log_frame, log_inner = self._card(self.content, 18)
        log_frame.pack(fill="both", expand=True, pady=(20, 0))
        self._text(log_inner, "Ostatnie zdarzenia", size=14, bold=True).pack(anchor="w")
        self.preview_logs = self._text(log_inner, "Brak zdarzeń.", color=MUTED,
                                       size=10, justify="left", wraplength=600)
        self.preview_logs.pack(anchor="nw", pady=(12, 0))

    def _character(self):
        card, inside = self._card(self.content, 23)
        card.pack(fill="both", expand=True)
        self._text(inside, "Aktualna postać", size=17, bold=True).pack(anchor="w")
        self._text(inside, "Wartości pochodzą z ostatniego poprawnego snapshotu.",
                   color=MUTED).pack(anchor="w", pady=(5, 24))
        self.character_info = self._text(inside, "Brak danych postaci.",
                                         size=12, justify="left", wraplength=650)
        self.character_info.pack(anchor="nw")

    def _quests(self):
        card, inside = self._card(self.content, 20)
        card.pack(fill="both", expand=True)
        self._text(inside, "Dziennik zadań", size=17, bold=True).pack(anchor="w")
        self._text(inside, "Aktywne zadania i ich postęp ze stanu MCP.",
                   color=MUTED).pack(anchor="w", pady=(7, 15))
        self.quests_text = tk.Text(inside, bg=PANEL, fg=FG, relief="flat", borderwidth=0,
                                   font=(FONT, 11), wrap="word", selectbackground=PANEL_ALT,
                                   state="disabled", spacing2=7)
        self.quests_text.pack(fill="both", expand=True)
        self._set_text(self.quests_text, "Brak danych o zadaniach.")

    def _diagnostics(self):
        card, inside = self._card(self.content, 21)
        card.pack(fill="x")
        self._text(inside, "Diagnostyka transportu", size=17, bold=True).pack(anchor="w")
        self.diagnostics_text = self._text(inside, "", size=11, justify="left",
                                           wraplength=700)
        self.diagnostics_text.pack(anchor="w", pady=(19, 5))
        logcard, loginner = self._card(self.content, 20)
        logcard.pack(fill="both", expand=True, pady=(18, 0))
        self._text(loginner, "Dziennik zdarzeń", size=14, bold=True).pack(anchor="w")
        self.logs_text = tk.Text(loginner, bg=PANEL, fg=MUTED, borderwidth=0,
                                 relief="flat", font=(FONT, 10), wrap="word",
                                 selectbackground=PANEL_ALT, state="disabled")
        self.logs_text.pack(fill="both", expand=True, pady=(10, 0))

    def _settings(self):
        card, inside = self._card(self.content, 22)
        card.pack(fill="x")
        self._text(inside, "Konfiguracja MCP", size=17, bold=True).pack(anchor="w")
        self._text(inside, "GUI obsługuje DLL, a ChatGPT odczytuje stan przez lokalny hub.",
                   color=MUTED, wraplength=660).pack(anchor="w", pady=(12, 16))
        self._text(inside, "W konfiguracji serwera MCP ustaw:", color=FG).pack(anchor="w")
        self._text(inside, "WOW_MCP_NATIVE_BRIDGE=1", color=ACCENT, size=13,
                   bold=True).pack(anchor="w", pady=(10, 10))
        self._button(inside, "Kopiuj zmienną środowiskową",
                     self._copy_config, True).pack(anchor="w", pady=(7, 0))
        other, inner = self._card(self.content, 22)
        other.pack(fill="x", pady=(19, 0))
        self._text(inner, "Informacje", size=16, bold=True).pack(anchor="w")
        self.settings_info = self._text(inner, "", color=MUTED, size=10,
                                        justify="left", wraplength=650)
        self.settings_info.pack(anchor="w", pady=(12, 4))
        self._text(inner,
                   "Ten prototyp NIE ładuje DLL do WoW i nie dodaje funkcji Lua. "
                   "Funkcja testowa wysyła wyłącznie dane demonstracyjne.",
                   color=WARNING, wraplength=660).pack(anchor="w", pady=(12, 0))

    @staticmethod
    def _set_text(widget, value):
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("end", value)
        widget.configure(state="disabled")

    def _copy_config(self):
        self.clipboard_clear()
        self.clipboard_append("WOW_MCP_NATIVE_BRIDGE=1")
        self._log("Skopiowano konfigurację MCP.")

    def _log(self, text):
        time = datetime.datetime.now().strftime("%H:%M:%S")
        self.messages.insert(0, f"[{time}] {text}")
        del self.messages[100:]

    def _run_demo(self):
        directory = (Path(sys.executable).resolve().parent
                     if getattr(sys, "frozen", False) else Path(__file__).resolve().parent)
        demo = directory / "native_bridge_demo.exe"
        if not demo.is_file():
            demo = directory / "build" / "native-bridge" / "Release" / "native_bridge_demo.exe"
        if not demo.is_file():
            self._log("Brak native_bridge_demo.exe — skompiluj projekt CMake.")
            messagebox.showinfo("Dane testowe",
                "Najpierw skompiluj natywny transport:\n"
                "cmake -S native_bridge -B build/native-bridge -A Win32\n"
                "cmake --build build/native-bridge --config Release", parent=self)
            return
        def send():
            try:
                result = subprocess.run([str(demo)], capture_output=True,
                                        text=True, timeout=5)
                msg = ("Dane demonstracyjne zostały wysłane."
                       if result.returncode == 0
                       else "Nie udało się wysłać testu: " + result.stderr.strip())
            except (OSError, subprocess.TimeoutExpired) as exc:
                msg = "Błąd testu: " + str(exc)
            self._result_queue.put(("log", msg))
        threading.Thread(target=send, daemon=True).start()

    def _check_game_async(self):
        def check():
            base = os.environ.get("WOW_GAME_DIR")
            installed = bool(base and (Path(base) / "Wow.exe").is_file())
            running = False
            if os.name == "nt":
                try:
                    cmd = subprocess.run(["tasklist", "/fi", "IMAGENAME eq Wow.exe", "/fo", "csv", "/nh"],
                                         capture_output=True, text=True, timeout=5)
                    running = '"Wow.exe"' in cmd.stdout
                except (OSError, subprocess.TimeoutExpired):
                    pass
            self._result_queue.put(("game", {"game_installed": installed,
                                              "game_running": running}))
        threading.Thread(target=check, daemon=True).start()

    def _refresh(self):
        while True:
            try:
                kind, value = self._result_queue.get_nowait()
            except queue.Empty:
                break
            if kind == "game":
                self._game_status = value
                self._log("WoW uruchomiony: " + ("tak" if value["game_running"] else "nie"))
            elif kind == "log":
                self._log(value)
        status = self.receiver.status()
        snapshot = self.receiver.snapshot()
        available = bool(snapshot["available"])
        if available != self.last_available:
            self._log("Odebrano poprawne dane." if available else "Oczekiwanie na świeże dane.")
            self.last_available = available
        if available and snapshot.get("sequence") != self.last_seq:
            self.last_seq = snapshot.get("sequence")
            self._log("Pakiet #" + str(self.last_seq) + " odebrany.")
        self.connection.configure(text="●  Połączono" if available else "●  Oczekiwanie na dane",
                                  fg=ACCENT if available else WARNING)
        data = snapshot.get("data") or {}
        character = data.get("character") or {}
        location = data.get("location") or {}
        quests = data.get("quests") or []
        if not isinstance(character, dict):
            character = {}
        if not isinstance(location, dict):
            location = {}
        if not isinstance(quests, list):
            quests = []
        if self.section == "Przegląd":
            health = f'{character.get("health", "—")} / {character.get("health_max", "—")}'
            values = {"level": character.get("level", "—") if available else "—",
                      "health": health if available else "—",
                      "zone": location.get("zone", "—") if available else "—",
                      "quests": len(quests) if available else "—"}
            for key, label in self.metric_labels.items():
                label.configure(text=str(values[key]))
            self.overview_status.configure(
                text=source_label(snapshot) +
                     f'\nWoW działa: {"tak" if self._game_status["game_running"] else "nie"}'
                     f'  •  Odebrane pakiety: {status["accepted_frames"]}'
                     f'  •  Wiek danych: {status["age_seconds"] or "—"} s',
                fg=ACCENT if available else MUTED)
            self.preview_logs.configure(text="\n".join(self.messages[:5]))
        elif self.section == "Postać":
            if available:
                lines = [f'{title}: {character.get(key, "—")}' for title, key in [
                    ("Imię", "name"), ("Kraina", "realm"), ("Klasa", "class"),
                    ("Rasa", "race"), ("Poziom", "level"), ("Doświadczenie", "xp"),
                    ("Zdrowie", "health"), ("Maks. zdrowie", "health_max"),
                    ("Mana / energia", "power"), ("Złoto (miedziaki)", "money_copper")]]
                lines.append("Strefa: " + str(location.get("zone", "—")))
                lines.append("\n" + source_label(snapshot))
            else:
                lines = ["Brak świeżych danych. Włącz źródło DLL lub użyj testu."]
            self.character_info.configure(text="\n\n".join(lines))
        elif self.section == "Zadania":
            if available and quests:
                parts = []
                for q in quests[:50]:
                    if not isinstance(q, dict):
                        continue
                    done = " ✓" if q.get("ready_to_turn_in") or q.get("complete") else ""
                    parts.append(str(q.get("title", "Bez nazwy")) + done)
                    for objective in (q.get("objectives") or [])[:15]:
                        if isinstance(objective, dict):
                            parts.append("    • " + str(objective.get("text", "")))
                body = "\n\n".join(parts) or "Brak zadań."
            elif available:
                body = "Postać nie ma aktywnych zadań w ostatnim odczycie."
            else:
                body = "Brak świeżych danych o zadaniach."
            if self.quests_text.get("1.0", "end-1c") != body:
                self._set_text(self.quests_text, body)
        elif self.section == "Diagnostyka":
            lines = [
                "Kanał: Windows Named Pipe",
                "Stan: " + ("Połączono" if available else "Brak danych"),
                "Pipe: " + status["pipe"],
                "Odebrane: " + str(status["accepted_frames"]),
                "Odrzucone: " + str(status["rejected_frames"]),
                "Ostatnia sekwencja: " + str(status.get("sequence")),
                "Wiek: " + str(status["age_seconds"]) + " s",
                "Ostatni błąd: " + str(status.get("error") or "brak"),
                "Port API: " + (str(self.hub._httpd.server_address[1])
                                if self.hub._httpd else "wyłączony"),
                "Timestamp: " + time_label(snapshot.get("captured_at")),
            ]
            self.diagnostics_text.configure(text="\n\n".join(lines))
            self._set_text(self.logs_text, "\n".join(self.messages[:60]))
        elif self.section == "Ustawienia":
            self.settings_info.configure(text=
                "Windows: " + os.name +
                "\nGra: " + str(os.environ.get("WOW_GAME_DIR") or "nie skonfigurowano WOW_GAME_DIR") +
                "\nStatus WoW: " + ("uruchomiony" if self._game_status["game_running"] else "nie wykryto") +
                "\nLokalny hub: " + ("aktywny" if self.hub._httpd else "wyłączony") +
                "\nOdbiornik: " + status["pipe"] +
                "\nDokumentacja: native_bridge/README.md")
        self.after(750, self._refresh)

    def _on_close(self):
        try:
            self.hub.stop()
        finally:
            self.destroy()


def main():
    ControlCenter().mainloop()


if __name__ == "__main__":
    main()
