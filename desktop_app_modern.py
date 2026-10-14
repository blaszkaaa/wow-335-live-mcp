"""Modern Polish desktop interface for WoW MCP Control Center."""
import json
import os
import queue
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from tkinter import BooleanVar, filedialog, messagebox

import customtkinter as ctk

from native_bridge.hub import DISCOVERY_FILE, NativeHubServer
from native_bridge.pipe import NativePipeReceiver
from ui_models import (gold, is_demo, metrics, quest_view, ratio,
                       select_snapshot, source_label, time_label, as_mapping)

ctk.set_appearance_mode("dark")
BASE = "#0A0F16"
NAV = "#101720"
CARD = "#16202B"
RAISED = "#202D3B"
STROKE = "#2D3D4B"
WHITE = "#F3F8FA"
DIM = "#9CAEBB"
GREEN = "#16B38F"
GREEN_HOVER = "#0B8C70"
AMBER = "#F4B85F"
RED = "#ED7685"
BLUE = "#68A5EC"
MENU = [("Przegląd", "◈"), ("Postać", "♙"), ("Zadania", "☷"),
        ("Ekwipunek", "▤"), ("Diagnostyka", "⌁"), ("Ustawienia", "⚙")]


def label(parent, text, size=12, color=WHITE, bold=False, **kwargs):
    return ctk.CTkLabel(parent, text=str(text), text_color=color,
                        font=ctk.CTkFont(family="Segoe UI", size=size,
                                         weight="bold" if bold else "normal"),
                        anchor="w", justify="left", **kwargs)


def card(parent):
    return ctk.CTkFrame(parent, fg_color=CARD, border_color=STROKE,
                        border_width=1, corner_radius=16)


def button(parent, text, action, primary=False):
    return ctk.CTkButton(
        parent, text=text, height=41, corner_radius=10,
        font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
        command=action, fg_color=GREEN if primary else RAISED,
        hover_color=GREEN_HOVER if primary else STROKE, text_color=WHITE)


def chip(parent, text, color=GREEN):
    return ctk.CTkLabel(parent, text="  " + text + "  ",
                        fg_color=RAISED, text_color=color, height=28,
                        corner_radius=10, font=ctk.CTkFont(
                            family="Segoe UI", size=11, weight="bold"))


def section(parent, title, subtitle=None):
    group = ctk.CTkFrame(parent, fg_color="transparent")
    label(group, title, 16, bold=True).pack(anchor="w")
    if subtitle:
        label(group, subtitle, 11, DIM).pack(anchor="w", pady=(3, 0))
    return group


class ControlCenter(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("WoW MCP — Control Center")
        self.geometry("1300x820")
        self.minsize(1020, 670)
        self.configure(fg_color=BASE)
        self.receiver = NativePipeReceiver()
        self.hub = NativeHubServer(self.receiver)
        self.events = []
        self.pending = queue.Queue()
        self.section = "Przegląd"
        self._visual = None
        self._reading = False
        self._game = {"game_running": False, "game_installed": False}
        self._settings_file = DISCOVERY_FILE.parent / "settings.json"
        self.game_dir = os.environ.get("WOW_GAME_DIR", "")
        self._load_settings()
        self.auto_enabled = BooleanVar(value=False)
        self.next_read = 0
        self.next_game_check = time.monotonic() + 15
        self.last_native_sequence = None
        self._query = ""
        self._quest_filter = "Wszystkie"
        self.snapshot = {"available": False}
        self.status = {}
        self.view_key = None
        self._build_shell()
        try:
            self.hub.start()
            if self.receiver.start():
                self._log("Odbiornik DLL i lokalny hub są aktywne.")
            else:
                self._log("Native Bridge wymaga Windows.")
        except Exception as exc:
            self._log("Błąd połączenia: " + str(exc))
            messagebox.showerror("WoW MCP", str(exc), parent=self)
        self.protocol("WM_DELETE_WINDOW", self._close)
        self.bind("<Control-r>", lambda _event: self.read_game())
        self._check_game()
        self._tick()

    def _build_shell(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        sidebar = ctk.CTkFrame(self, fg_color=NAV, corner_radius=0, width=235)
        sidebar.grid(row=0, column=0, sticky="ns")
        sidebar.grid_propagate(False)
        sidebar.grid_rowconfigure(2, weight=1)
        brand = ctk.CTkFrame(sidebar, fg_color="transparent")
        brand.grid(row=0, column=0, sticky="w", padx=24, pady=(31, 32))
        label(brand, "◆", 27, GREEN, True).pack(side="left")
        box = ctk.CTkFrame(brand, fg_color="transparent")
        box.pack(side="left", padx=12)
        label(box, "WoW MCP", 20, bold=True).pack(anchor="w")
        label(box, "CONTROL CENTER", 10, DIM, True).pack(anchor="w")
        navigation = ctk.CTkFrame(sidebar, fg_color="transparent")
        navigation.grid(row=1, column=0, sticky="ew", padx=12)
        self.links = {}
        for name, glyph in MENU:
            widget = ctk.CTkButton(
                navigation, text=f" {glyph}     {name}", anchor="w",
                height=46, corner_radius=11, fg_color="transparent",
                hover_color=RAISED, text_color=DIM,
                font=ctk.CTkFont(family="Segoe UI", size=13),
                command=lambda page=name: self.show(page))
            widget.pack(fill="x", pady=3)
            self.links[name] = widget
        footer = ctk.CTkFrame(sidebar, fg_color=RAISED, corner_radius=12)
        footer.grid(row=3, column=0, sticky="sew", padx=13, pady=19)
        label(footer, "●  Lokalny asystent", 11, GREEN, True).pack(
            anchor="w", padx=13, pady=(13, 4))
        label(footer, "WoW 3.3.5a  ·  wersja testowa", 10, DIM).pack(
            anchor="w", padx=13, pady=(0, 13))
        self.main = ctk.CTkFrame(self, fg_color=BASE, corner_radius=0)
        self.main.grid(row=0, column=1, sticky="nsew")
        self.main.grid_columnconfigure(0, weight=1)
        self.main.grid_rowconfigure(1, weight=1)
        header = ctk.CTkFrame(self.main, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=30, pady=(23, 17))
        header.grid_columnconfigure(0, weight=1)
        stack = ctk.CTkFrame(header, fg_color="transparent")
        stack.grid(row=0, column=0, sticky="w")
        self.heading = label(stack, "Przegląd", 27, bold=True)
        self.heading.pack(anchor="w")
        label(stack, "Twój świat Warcraft w jednym miejscu", 11, DIM).pack(anchor="w")
        self.connection = chip(header, "Oczekiwanie", AMBER)
        self.connection.grid(row=0, column=1, sticky="e")
        self.view = None
        self.show("Przegląd")

    def show(self, name):
        self.section = name
        self.heading.configure(text=name)
        for title, link in self.links.items():
            selected = title == name
            link.configure(fg_color=RAISED if selected else "transparent",
                           text_color=WHITE if selected else DIM)
        self.view_key = None
        self.render()

    def render(self):
        if self.view is not None:
            self.view.destroy()
        self.view = ctk.CTkScrollableFrame(
            self.main, fg_color="transparent", corner_radius=0,
            scrollbar_button_color=STROKE)
        self.view.grid(row=1, column=0, sticky="nsew",
                       padx=(26, 15), pady=(0, 25))
        live = bool(self.snapshot.get("available"))
        data = metrics(self.snapshot if live else {})
        pages = {"Przegląd": self.overview, "Postać": self.character,
                 "Zadania": self.quests, "Ekwipunek": self.inventory,
                 "Diagnostyka": self.diagnostics, "Ustawienia": self.settings}
        pages[self.section](data, live)
        self.view_key = self._key()

    def _empty(self, parent, title, text):
        panel = card(parent)
        panel.pack(fill="x", pady=12)
        label(panel, title, 17, bold=True).pack(anchor="w", padx=23, pady=(24, 8))
        label(panel, text, 12, DIM, wraplength=690).pack(
            anchor="w", padx=23, pady=(0, 25))
        return panel

    def _detail(self, parent, heading, value):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=19, pady=8)
        label(row, heading, 11, DIM).pack(side="left")
        label(row, value, 11, WHITE, True).pack(side="right")

    def overview(self, data, live):
        hero = card(self.view)
        hero.pack(fill="x", pady=(2, 16))
        contents = ctk.CTkFrame(hero, fg_color="transparent")
        contents.pack(fill="x", padx=25, pady=24)
        chip(contents, source_label(self.snapshot),
             AMBER if not live or is_demo(self.snapshot) else GREEN).pack(anchor="w")
        label(contents, "Witaj w Azeroth", 26, bold=True).pack(
            anchor="w", pady=(15, 3))
        detail = (f'{data["name"]}  ·  Poziom {data["level"]}  ·  {data["zone"]}'
                  if live else "Połącz grę, aby zobaczyć statystyki postaci.")
        label(contents, detail, 12, DIM, wraplength=670).pack(anchor="w")
        actions = ctk.CTkFrame(contents, fg_color="transparent")
        actions.pack(anchor="w", pady=(22, 0))
        button(actions, "↻  Odczytaj WoW", self.read_game, True).pack(
            side="left", padx=(0, 9))
        button(actions, "◈  Test DLL", self.run_demo).pack(side="left")
        button(actions, "⚙  Wybierz folder", lambda: self.show("Ustawienia")).pack(
            side="left", padx=(9, 0))
        tiles = ctk.CTkFrame(self.view, fg_color="transparent")
        tiles.pack(fill="x", pady=(0, 17))
        items = [
            ("POZIOM", data["level"] if live else "—", GREEN),
            ("ZDROWIE", f'{data["health"]}/{data["health_max"]}' if live else "—", WHITE),
            ("ZADANIA", data["quest_count"] if live else "—", WHITE),
            ("GOTOWE DO ODDANIA", data["ready_count"] if live else "—", GREEN),
        ]
        for index, (name, val, tint) in enumerate(items):
            tiles.grid_columnconfigure(index, weight=1, uniform="stats")
            tile = card(tiles)
            tile.grid(row=0, column=index, sticky="nsew",
                      padx=(0, 10) if index < 3 else 0)
            label(tile, name, 10, DIM, True).pack(
                anchor="w", padx=16, pady=(17, 7))
            label(tile, val, 23, tint, True).pack(
                anchor="w", padx=16, pady=(0, 19))
        duo = ctk.CTkFrame(self.view, fg_color="transparent")
        duo.pack(fill="x")
        duo.grid_columnconfigure(0, weight=5)
        duo.grid_columnconfigure(1, weight=3)
        left = card(duo)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        right = card(duo)
        right.grid(row=0, column=1, sticky="nsew")
        section(left, "Aktywne zadania", "Najważniejsze cele").pack(
            anchor="w", padx=19, pady=(20, 13))
        if live and data["quests"]:
            for q in quest_view(data["quests"])[:4]:
                item = ctk.CTkFrame(left, fg_color=RAISED, corner_radius=10)
                item.pack(fill="x", padx=16, pady=4)
                label(item, q["title"], 11, WHITE, True).pack(
                    side="left", padx=11, pady=12)
                if q["ready"]:
                    chip(item, "Gotowe", GREEN).pack(side="right", padx=7)
        else:
            label(left, "Brak aktywnych danych o zadaniach.", 11, DIM).pack(
                anchor="w", padx=19, pady=16)
        button(left, "Otwórz dziennik zadań →",
               lambda: self.show("Zadania")).pack(anchor="w", padx=19, pady=19)
        section(right, "Status połączenia", "Kanały danych").pack(
            anchor="w", padx=19, pady=(20, 13))
        self._detail(right, "Proces WoW",
                     "Uruchomiony" if self._game["game_running"] else "Nie wykryto")
        self._detail(right, "Kanał DLL", "Aktywny" if self.receiver._thread else "Nieaktywny")
        self._detail(right, "Hub MCP", "Aktywny" if self.hub._httpd else "Wyłączony")
        self._detail(right, "Pakiety", str(self.status.get("accepted_frames", 0)))
        label(right, "DLL nie ma jeszcze podłączenia do Lua.",
              10, AMBER, wraplength=260).pack(
                  anchor="w", padx=19, pady=(12, 18))

    def _bar(self, parent, name, value, maximum, tint):
        head = ctk.CTkFrame(parent, fg_color="transparent")
        head.pack(fill="x", pady=(13, 6))
        label(head, name, 12, DIM).pack(side="left")
        label(head, f"{value} / {maximum}", 12, WHITE, True).pack(side="right")
        progress = ctk.CTkProgressBar(parent, height=10, corner_radius=5,
                                      fg_color=RAISED, progress_color=tint)
        progress.pack(fill="x")
        progress.set(ratio(value, maximum))

    def character(self, data, live):
        if not live:
            self._empty(self.view, "Brak danych postaci",
                        "Otwórz Przegląd i wykonaj odczyt z addonu.")
            return
        head = card(self.view)
        head.pack(fill="x", pady=(3, 17))
        left = ctk.CTkFrame(head, fg_color="transparent")
        left.pack(side="left", padx=24, pady=24)
        label(left, data["name"], 29, bold=True).pack(anchor="w")
        label(left, f'{data["race"]} · {data["class"]} · {data["realm"]}',
              12, DIM).pack(anchor="w", pady=(7, 0))
        chip(head, f'Poziom {data["level"]}', GREEN).pack(side="right", padx=24)
        panel = card(self.view)
        panel.pack(fill="x", pady=(0, 17))
        body = ctk.CTkFrame(panel, fg_color="transparent")
        body.pack(fill="x", padx=25, pady=21)
        section(body, "Zasoby postaci").pack(anchor="w", pady=(0, 4))
        self._bar(body, "Zdrowie", data["health"], data["health_max"], RED)
        self._bar(body, "Mana / energia", data["power"], data["power_max"], BLUE)
        self._bar(body, "Doświadczenie", data["xp"], data["xp_max"], GREEN)
        details = ctk.CTkFrame(self.view, fg_color="transparent")
        details.pack(fill="x")
        details.grid_columnconfigure(0, weight=1)
        details.grid_columnconfigure(1, weight=1)
        loc = card(details)
        loc.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        money = card(details)
        money.grid(row=0, column=1, sticky="nsew")
        section(loc, "Lokalizacja").pack(anchor="w", padx=21, pady=(19, 11))
        label(loc, data["zone"], 17, WHITE, True).pack(anchor="w", padx=21)
        label(loc, data["subzone"] or "Nieznana podstrefa", 11, DIM).pack(
            anchor="w", padx=21, pady=(6, 19))
        section(money, "Posiadane złoto").pack(anchor="w", padx=21, pady=(19, 11))
        label(money, gold(data["money_copper"]), 20, AMBER, True).pack(
            anchor="w", padx=21, pady=(0, 24))

    def quests(self, data, live):
        head = ctk.CTkFrame(self.view, fg_color="transparent")
        head.pack(fill="x", pady=(2, 16))
        self.quest_search = ctk.CTkEntry(
            head, width=340, height=42, corner_radius=11, fg_color=CARD,
            border_color=STROKE, placeholder_text="Szukaj questów i celów...")
        self.quest_search.pack(side="left", fill="x", expand=True, padx=(0, 12))
        self.quest_search.insert(0, self._query)
        self.quest_search.bind("<KeyRelease>", self._search_changed)
        self.filter = ctk.CTkSegmentedButton(
            head, values=["Wszystkie", "Gotowe", "W toku"],
            fg_color=RAISED, unselected_color=RAISED,
            selected_color=GREEN, selected_hover_color=GREEN_HOVER,
            unselected_hover_color=STROKE, height=40,
            command=self._filter_changed)
        self.filter.pack(side="right")
        self.filter.set(self._quest_filter)
        self.quest_total = label(self.view, "0 zadań", 12, DIM)
        self.quest_total.pack(anchor="w", pady=(0, 12))
        self.quest_items = ctk.CTkFrame(self.view, fg_color="transparent")
        self.quest_items.pack(fill="x")
        self._populate_quests(data, live)

    def _search_changed(self, _event):
        self._query = self.quest_search.get()
        self._populate_quests(metrics(self.snapshot), bool(self.snapshot.get("available")))

    def _filter_changed(self, value):
        self._quest_filter = value
        self._populate_quests(metrics(self.snapshot), bool(self.snapshot.get("available")))

    def _populate_quests(self, data, live):
        for child in self.quest_items.winfo_children():
            child.destroy()
        items = quest_view(data["quests"], self._query, self._quest_filter)
        self.quest_total.configure(text=f'{len(items)} zadań · {data["ready_count"]} do oddania')
        if not live or not items:
            self._empty(self.quest_items, "Brak zadań",
                        "Zmień filtr albo odczytaj stan gry.")
            return
        for q in items[:75]:
            item = card(self.quest_items)
            item.pack(fill="x", pady=(0, 9))
            header = ctk.CTkFrame(item, fg_color="transparent")
            header.pack(fill="x", padx=19, pady=(14, 8))
            level = f' · poziom {q["level"]}' if q["level"] is not None else ""
            label(header, q["title"] + level, 14, WHITE, True).pack(side="left")
            chip(header, "DO ODDANIA" if q["ready"] else "W TOKU",
                 GREEN if q["ready"] else DIM).pack(side="right")
            objectives = q["objectives"]
            if not objectives:
                label(item, "Brak celów w odczycie.", 11, DIM).pack(
                    anchor="w", padx=21, pady=(0, 15))
            else:
                for objective in objectives[:12]:
                    done = bool(objective.get("done"))
                    label(item, ("✓  " if done else "○  ") +
                          str(objective.get("text") or "Cel bez opisu"),
                          11, GREEN if done else DIM,
                          wraplength=750).pack(anchor="w", padx=21, pady=3)
                ctk.CTkFrame(item, height=13, fg_color="transparent").pack()

    def inventory(self, data, live):
        if not live:
            self._empty(self.view, "Brak ekwipunku",
                        "Odczytaj dane z addonu w zakładce Przegląd.")
            return
        for title, values in [("Założone przedmioty", data["equipment"]),
                              ("Zawartość toreb", data["bags"])]:
            panel = card(self.view)
            panel.pack(fill="x", pady=(0, 17))
            section(panel, title, f"{len(values)} pozycji").pack(
                anchor="w", padx=20, pady=(19, 12))
            if not values:
                label(panel, "Brak danych w tej sekcji.", 11, DIM).pack(
                    anchor="w", padx=20, pady=(0, 20))
            for item in values[:65]:
                if not isinstance(item, dict):
                    continue
                row = ctk.CTkFrame(panel, fg_color=RAISED, corner_radius=10)
                row.pack(fill="x", padx=16, pady=4)
                label(row, item.get("name") or f'Przedmiot #{item.get("id")}',
                      12).pack(side="left", padx=12, pady=11)
                label(row, f'x{item.get("count") or 1}', 11, DIM).pack(
                    side="right", padx=12)
            ctk.CTkFrame(panel, fg_color="transparent", height=13).pack()

    def diagnostics(self, _data, live):
        panel = card(self.view)
        panel.pack(fill="x", pady=(2, 16))
        section(panel, "Transmisja i status",
                "Monitoruje lokalny kanał DLL oraz dane z gry").pack(
                    anchor="w", padx=20, pady=(20, 12))
        fields = [
            ("Źródło danych", source_label(self.snapshot)),
            ("Named Pipe", self.status.get("pipe") or "—"),
            ("Pakiety odebrane", str(self.status.get("accepted_frames", 0))),
            ("Pakiety odrzucone", str(self.status.get("rejected_frames", 0))),
            ("Wiek danych", str(self.status.get("age_seconds") or "—") + " s"),
            ("Ostatnia aktualizacja", time_label(
                as_mapping(self.snapshot.get("data")).get("captured_at"))),
            ("Hub MCP", "Aktywny" if self.hub._httpd else "Nieaktywny"),
            ("Błąd", str(self.status.get("error") or "Brak")),
        ]
        for name, val in fields:
            self._detail(panel, name, val)
        ctk.CTkFrame(panel, height=16, fg_color="transparent").pack()
        events = card(self.view)
        events.pack(fill="x")
        section(events, "Dziennik zdarzeń").pack(
            anchor="w", padx=20, pady=(20, 11))
        for message in self.events[:35] or ["Brak zdarzeń."]:
            label(events, message, 11, DIM).pack(anchor="w", padx=20, pady=4)
        ctk.CTkFrame(events, height=17, fg_color="transparent").pack()

    def settings(self, _data, _live):
        path = card(self.view)
        path.pack(fill="x", pady=(2, 17))
        section(path, "Katalog gry", "Folder zawierający Wow.exe").pack(
            anchor="w", padx=21, pady=(20, 9))
        label(path, self.game_dir or "Nie wybrano folderu", 12, DIM,
              wraplength=760).pack(anchor="w", padx=21, pady=(5, 13))
        button(path, "Wybierz folder WoW", self.choose_game, True).pack(
            anchor="w", padx=21, pady=(0, 21))
        auto = card(self.view)
        auto.pack(fill="x", pady=(0, 17))
        section(auto, "Automatyczny odczyt",
                "Odczytuj dane addonu co 30 sekund (opcjonalne)").pack(
                    anchor="w", padx=21, pady=(20, 12))
        ctk.CTkSwitch(auto, text="Włącz odczyt w tle", variable=self.auto_enabled,
                      progress_color=GREEN, command=self._auto_changed).pack(
                          anchor="w", padx=23, pady=(0, 14))
        label(auto, "Odczyt może przełączać fokus na grę. Domyślnie wyłączony.",
              11, AMBER, wraplength=770).pack(
                  anchor="w", padx=23, pady=(0, 22))
        config = card(self.view)
        config.pack(fill="x", pady=(0, 17))
        section(config, "ChatGPT / MCP", "Lokalne połączenie przez hub").pack(
            anchor="w", padx=21, pady=(20, 13))
        label(config, "WOW_MCP_NATIVE_BRIDGE=1\nWOW_MCP_NATIVE_HUB=1",
              13, GREEN, True).pack(anchor="w", padx=21, pady=(0, 17))
        button(config, "Kopiuj konfigurację", self.copy_config).pack(
            anchor="w", padx=21, pady=(0, 22))
        warning = card(self.view)
        warning.pack(fill="x", pady=(0, 10))
        label(warning, "DLL nadal jest eksperymentalna", 15, AMBER, True).pack(
            anchor="w", padx=21, pady=(20, 7))
        label(warning,
              "Nie instaluj DLL wewnątrz procesu WoW. Łączność z silnikiem Lua "
              "nie została jeszcze wdrożona ani sprawdzona na Warmane.",
              12, DIM, wraplength=770).pack(
                  anchor="w", padx=21, pady=(0, 21))

    def _key(self):
        data = as_mapping(self.snapshot.get("data"))
        return (self.section, bool(self.snapshot.get("available")),
                self.snapshot.get("source"),
                json.dumps(data, sort_keys=True, default=str, ensure_ascii=False),
                str(self._game), self.status.get("accepted_frames"),
                self.status.get("rejected_frames"), len(self.events), self.game_dir)

    def _tick(self):
        while True:
            try:
                kind, item = self.pending.get_nowait()
            except queue.Empty:
                break
            if kind == "game" and item != self._game:
                self._game = item
                self._log("WoW uruchomiony" if item["game_running"] else "WoW nie jest uruchomiony")
            elif kind == "visual":
                self._reading = False
                self._visual = item if item.get("available") else None
                self._log("Odebrano dane WoW" if self._visual
                          else "Błąd odczytu: " + str(item.get("reason")))
            elif kind == "log":
                self._log(item)
        native = self.receiver.snapshot()
        self.status = self.receiver.status()
        sequence = native.get("sequence")
        if native.get("available") and sequence != self.last_native_sequence:
            self.last_native_sequence = sequence
            self._log(f"Odebrano pakiet DLL #{sequence}.")
        self.snapshot = select_snapshot(native, self._visual)
        live = bool(self.snapshot.get("available"))
        self.connection.configure(
            text="  ●  DEMO  " if is_demo(self.snapshot) else
                 ("  ●  AKTUALNE  " if live else "  ●  BRAK DANYCH  "),
            text_color=AMBER if not live or is_demo(self.snapshot) else GREEN)
        key = self._key()
        if key != self.view_key:
            if self.section == "Zadania" and self.view_key is not None:
                if self.view_key[0] == "Zadania" and self.view_key[3] == key[3]:
                    self.view_key = key
                else:
                    self._query = self.quest_search.get()
                    self.render()
            else:
                self.render()
        now = time.monotonic()
        if now >= self.next_game_check:
            self.next_game_check = now + 15
            self._check_game()
        if self.auto_enabled.get() and now >= self.next_read:
            self.next_read = now + 30
            if self._game.get("game_running") and not self._reading:
                self.read_game()
        self.after(950, self._tick)

    def _auto_changed(self):
        self.next_read = time.monotonic() + 1
        self._log("Automatyczne odczyty: " +
                  ("włączone" if self.auto_enabled.get() else "wyłączone"))

    def _load_settings(self):
        if self.game_dir:
            return
        try:
            value = json.loads(self._settings_file.read_text(encoding="utf-8")).get("game_dir")
            if isinstance(value, str):
                self.game_dir = value
                os.environ["WOW_GAME_DIR"] = value
        except (OSError, ValueError):
            pass

    def choose_game(self):
        directory = filedialog.askdirectory(
            parent=self, initialdir=self.game_dir or str(Path.home()),
            title="Wybierz folder WoW 3.3.5a")
        if not directory:
            return
        if not (Path(directory) / "Wow.exe").is_file():
            messagebox.showerror("Folder WoW", "Nie znaleziono Wow.exe.", parent=self)
            return
        self.game_dir = directory
        os.environ["WOW_GAME_DIR"] = directory
        self._settings_file.parent.mkdir(parents=True, exist_ok=True)
        self._settings_file.write_text(
            json.dumps({"game_dir": directory}, ensure_ascii=False), encoding="utf-8")
        self._log("Zapisano nowy katalog WoW.")
        self._check_game()
        self.view_key = None

    def copy_config(self):
        self.clipboard_clear()
        self.clipboard_append("WOW_MCP_NATIVE_BRIDGE=1\nWOW_MCP_NATIVE_HUB=1")
        self._log("Skopiowano konfigurację.")

    def read_game(self):
        if self._reading:
            return
        folder = self.game_dir
        if not folder or not (Path(folder) / "Wow.exe").is_file():
            messagebox.showinfo("Folder gry", "Najpierw wskaż folder z Wow.exe.",
                                parent=self)
            self.show("Ustawienia")
            return
        self._reading = True
        self._log("Odczyt danych z addonu...")
        def worker():
            try:
                import server
                server.GAME = Path(folder).expanduser().resolve()
                result = server.live_game_data()
            except Exception as exc:
                result = {"available": False, "reason": str(exc)}
            self.pending.put(("visual", result))
        threading.Thread(target=worker, daemon=True).start()

    def run_demo(self):
        root = (Path(sys.executable).resolve().parent
                if getattr(sys, "frozen", False)
                else Path(__file__).resolve().parent)
        demo = root / "native_bridge_demo.exe"
        if not demo.is_file():
            demo = root / "build" / "native-bridge" / "Release" / "native_bridge_demo.exe"
        if not demo.is_file():
            messagebox.showinfo("Demo DLL", "Nadajnik demo wymaga kompilacji CMake "
                                "lub pobrania paczki ZIP z Actions.", parent=self)
            return
        def worker():
            try:
                result = subprocess.run([str(demo)], text=True,
                                        capture_output=True, timeout=5)
                info = "Wysłano demo DLL." if result.returncode == 0 else (
                    "Błąd DLL: " + result.stderr.strip())
            except (OSError, subprocess.TimeoutExpired) as exc:
                info = "Błąd DLL: " + str(exc)
            self.pending.put(("log", info))
        threading.Thread(target=worker, daemon=True).start()

    def _check_game(self):
        folder = self.game_dir
        def worker():
            installed = bool(folder and (Path(folder) / "Wow.exe").is_file())
            running = False
            if os.name == "nt":
                try:
                    output = subprocess.run(
                        ["tasklist", "/fi", "IMAGENAME eq Wow.exe", "/fo", "csv", "/nh"],
                        capture_output=True, text=True, timeout=5)
                    running = '"Wow.exe"' in output.stdout
                except (OSError, subprocess.TimeoutExpired):
                    pass
            self.pending.put(("game", {"game_installed": installed,
                                       "game_running": running}))
        threading.Thread(target=worker, daemon=True).start()

    def _log(self, message):
        self.events.insert(0, f'[{datetime.now().strftime("%H:%M:%S")}] {message}')
        del self.events[100:]

    def _close(self):
        try:
            self.hub.stop()
        finally:
            self.destroy()


def main():
    ControlCenter().mainloop()


if __name__ == "__main__":
    main()
