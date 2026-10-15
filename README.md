# WoW 3.3.5a Live MCP — WoW Connect

Lokalny asystent World of Warcraft 3.3.5a dla Windows, z minimalistyczną aplikacją desktopową w **ciemnym motywie** i serwerem MCP do odczytu danych postaci. Działający wcześniej tryb **WoWMCPData RGB** został przywrócony: **brak DLL, wstrzykiwania kodu i LichLoadera** w bieżącej wersji.

## Jak to działa

```text
WoW 3.3.5a (oryginalny Wow.exe)
  → addon WoWMCPData
  → kolorowy kwadrat 32×16 w lewym dolnym rogu ekranu
  → screenshot dekodowany lokalnie na żądanie
  → WoW Connect / lokalny serwer MCP
  → ChatGPT (jeśli jest osobno poprawnie podłączony do MCP)
```

Addon używa API Lua gry i rysuje dane w rogu ekranu. Serwer nie skanuje pamięci procesu, nie wstrzykuje DLL i nie wykonuje działań w grze.

## Szybki start

1. Zainstaluj instalator Windows z [GitHub Actions — Tauri Windows Desktop](https://github.com/blaszkaaa/wow-335-live-mcp/actions/workflows/tauri.yml).
2. Uruchom **WoW Connect** i wskaż folder zawierający `Wow.exe`.
3. Kliknij **Uruchom WoW**. Aplikacja automatycznie zainstaluje addon WoWMCPData (z kopią wcześniejszego) i uruchomi **oryginalny** klient.
4. Upewnij się, że addon jest włączony na ekranie wyboru postaci. Wejdź do gry i sprawdź kolorowy kwadrat w lewym dolnym rogu.
5. Pozostaw grę widoczną i kliknij **Odczytaj postać**. Odczyt może potrwać kilkanaście sekund — kwadrat nadaje dane na kilku stronach.

**Poprzednia konfiguracja DLL jest ignorowana.** Nowy instalator nie dołącza bibliotek ani loadera. Dodatkowe wskazówki, bezpieczna obsługa starych plików i informacje o połączeniu MCP: [desktop-next/README.md](desktop-next/README.md).

## Dostępne narzędzia MCP

- `wow_status` — stan okna WoW i możliwość odczytu wizualnego
- `read_wow_live_data` — dane postaci, zadań, ekwipunku, umiejętności, celu i innych sekcji z addonu
- `capture_wow` — zrzut samego okna gry na wyraźne żądanie
- `list_wow_addons` — lista dodatków
- `read_wow_game_data` — zapisane dane z `/reload` lub wylogowania (to **nie** odczyt na żywo)
- `read_wow_combat_log` — ostatni dziennik walki, jeśli włączono `/combatlog`

`read_wow_live_data` próbuje przechwycić wszystkie strony kolorowego panelu (zwykle kilka–kilkanaście sekund). Nie minimalizuj WoW i nie zakrywaj paska. Odbiór danych wymaga osobnego, działającego połączenia serwera MCP z klientem ChatGPT. Sam status aplikacji nie potwierdza połączenia z chmurą.

## Kompilacja

Workflow `.github/workflows/tauri.yml` buduje aplikację Tauri 2, Python sidecar i zgodny serwer stdio `wow-mcp-stdio.exe`. W obecnej wersji **nie buduje ani nie pakuje LichLoadera i WoWMCPNativeLua.dll**.

Eksperymentalne źródła `native_bridge/` pozostają w historii projektu, ale nie są uruchamiane ani dołączane do instalatora. Projekt jest niezależny od Blizzard, Warmane, Questie i WoWpoPolsku.
