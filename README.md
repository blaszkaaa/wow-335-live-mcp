# WoW 3.3.5a Live MCP

A local, read-only MCP server for **World of Warcraft: Wrath of the Lich King 3.3.5a (build 12340)** on Windows. It pairs an in-game addon with a Python server so an MCP client can request current character data without reading game memory, modifying MPQ files, or controlling the character.

This project is independent of Blizzard, Warmane, Questie, and WoWpoPolsku. It does not include game files or third-party addons.

## How it works

```text
WoW 3.3.5a API -> WoWMCPData addon -> visible color strip -> local screen capture
                                                       -> Python decoder -> MCP client
```

The addon draws a **32 × 16 cell strip** in the lower-left corner. The strip must remain visible and unobstructed for live reads. It cycles through pages, so a request may take a few seconds. Data is refreshed between page cycles. The MCP server reads pixels on demand; it does not poll continuously, inject code, inspect process memory, or send game commands.

## Available tools

| Tool | Data |
| --- | --- |
| `wow_status` | Whether the configured game is installed, running, and capturable. |
| `read_wow_live_data` | Current character, location, target, pet, quests and objectives, bags, equipment, spellbook, action bar, skills, stats, talents, group, auras, recent combat summary, and an open NPC interaction. |
| `capture_wow` | One screenshot of the game window rectangle. |
| `list_wow_addons` | Addon folder names and `.toc` filenames. |
| `read_wow_game_data` | A **saved snapshot** written by WoW on `/reload` or logout. It is not live. |
| `read_wow_combat_log` | Recent lines from `Logs/WoWCombatLog.txt`, only if WoW's `/combatlog` is enabled. |

`read_wow_live_data` reports `age_seconds`. Trainer, merchant, gossip, and quest-dialog details are available while the corresponding window is open and for up to 30 seconds afterward. The combat summary describes the latest fight since the addon was loaded; it is not a full combat log. Large snapshots may omit spells, actions, or bags and mark the omitted section with a `*_truncated` flag. The live strip does not include Questie's map database or a complete history of every quest.

## Uruchamianie gry bezpośrednio z aplikacji

W nowej, minimalistycznej aplikacji **WoW Connect** wybierz folder z `Wow.exe`, a następnie
kliknij **Uruchom WoW**. Aplikacja instaluje/aktualizuje oba pliki
addonu `WoWMCPData`, tworzy kopię zapasową starszej wersji, włącza
odbiornik MCP i uruchamia grę. Jeśli WoW już działa, nie uruchamia
drugiej instancji i informuje, czy wymagane jest `/reload`.
Na głównym ekranie pozostają tylko przyciski uruchomienia i odczytu postaci; zmianę folderu znajdziesz pod ikoną ustawień.

Opcjonalny tryb **Przez LichLoader (DLL)** pozwala jednym kliknięciem
przygotować i uruchomić natywną integrację. Instalator Windows zawiera
sprawdzoną wersję LichLoadera i zbudowany adapter Lua→DLL; przy pierwszym
uruchomieniu aplikacja instaluje te składniki, zachowuje obce pliki i
istniejącą konfigurację oraz uruchamia grę. Tryb jest dobrowolny i nie
obchodzi zabezpieczeń klienta.
[Instrukcja automatycznego trybu DLL](desktop-next/README.md).

## Opcjonalna integracja Lua → DLL (offline)

Źródło modułu: [WoWMCPNativeLua.cpp](native_bridge/adapter/WoWMCPNativeLua.cpp).
Adapter rejestruje funkcję WoWMCP.Publish(json) za pomocą WrathClassicAPI.
Addon WoWMCPData wysyła natywne snapshoty mniej więcej co 3 sekundy i nadal
renderuje pasek kolorowy. Kiedy WOW_MCP_NATIVE_BRIDGE=1, standardowe
read_wow_live_data najpierw odczytuje świeży pakiet DLL, a gdy go brak,
wraca do odczytu wizualnego. Pakiety z nadajnika demonstracyjnego nie są
traktowane jako faktyczna telemetria gry.

**To kod eksperymentalny do autoryzowanych testów offline. Nie używaj
niezatwierdzonych hooków DLL na Warmane — ryzyko blokady konta.** Natywne
uruchomienie w samym Wow.exe wymaga odrębnego testu i zgody operatora.

## Nowa aplikacja desktopowa (zalecana)

**WoW Connect** to minimalistyczna aplikacja Windows (Tauri 2 + React),
która uruchamia grę i wyświetla podstawowe informacje o postaci, zadaniach
i stanie połączenia MCP. Opcjonalny tryb DLL można wybrać w ustawieniach.

Tauri uruchamia usługę Python (PyInstaller sidecar), która nadal obsługuje
MCP, addon i eksperymentalny kanał DLL. Nie trzeba osobno uruchamiać
starego GUI w Pythonie. Instalator Windows jest budowany przez workflow
**Tauri Windows Desktop** na GitHub Actions.

Szczegóły i instrukcja: [desktop-next/README.md](desktop-next/README.md).

**Opcjonalny adapter Lua→DLL został zaimplementowany i przechodzi kompilację
Win32, ale nie został sprawdzony w działającym kliencie ani na Warmane.**
Odczyt wizualny pozostaje rozwiązaniem domyślnym i zapasowym.
[Instrukcja testowa native Lua](native_bridge/adapter/README.md).

**Zielony status DLL w WoW Connect oznacza rzeczywiste odebrane pakiety,
nie tylko aktywny odbiornik. Tryb DLL automatycznie przygotowuje wymagane
pliki z własnego instalatora, ale nadal wymaga autoryzowanego testu na
prawdziwym kliencie.**

### Poprzednie GUI (tryb legacy)

Stary interfejs CustomTkinter z pliku desktop_app.py jest pozostawiony
wyłącznie jako rozwiązanie zapasowe.

## Desktop Control Center 2.0 (legacy / experimental)

The Windows application has a polished dark interface built with
[CustomTkinter](https://customtkinter.tomschimansky.com/):

- **Przegląd**: hero panel, live status, level, health, ready quests and quick actions.
- **Postać**: character and realm, health/power/XP progress bars, zone and money.
- **Zadania**: quest search, "Wszystkie/Gotowe/W toku" filters and progress.
- **Ekwipunek**: equipped items and bag inventory.
- **Diagnostyka**: received/rejected packets, data source, errors and event feed.
- **Ustawienia**: WoW directory, connection configuration and opt-in periodic
  visual reads every 30 seconds (may briefly foreground WoW).

Run from source with **py -3 desktop_app.py**, or download the packaged Windows
EXE from the GitHub Actions artifact associated with the PR. Documentation in
Polish: [docs/GUI_PL.md](docs/GUI_PL.md).

The UI owns the optional native pipe and shares status over an authenticated
127.0.0.1 hub with other MCP processes. Set \`WOW_MCP_NATIVE_BRIDGE=1\`
and \`WOW_MCP_NATIVE_HUB=1\` in the MCP server environment to enable it.

**Important:** Native pipe transfer is tested independently of the game.
In-game DLL/Lua integration is **not** implemented. Real WoW data can be
requested using the existing visual addon; no game DLL injection is needed.
The experimental DLL should not be loaded into Warmane WoW.exe.


## Requirements

- Windows 10/11 with a running WoW 3.3.5a client (`Wow.exe`).
- Python 3.9 or newer with `numpy` and `Pillow`.
- A local MCP client. A remote ChatGPT connection requires a separately configured private tunnel.

The addon `.toc` declares interface **30300**. It targets the 3.3.5a client, including Warmane realms that actually use that client. It is not an addon for modern WoW Classic or TBC clients.

## Install

From PowerShell:

```powershell
git clone https://github.com/blaszkaaa/wow-335-live-mcp.git
Set-Location .\wow-335-live-mcp
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\scripts\install-addon.ps1 -GameDir 'C:\Games\World of Warcraft 3.3.5a'
```

Replace the example game path with the folder containing your `Wow.exe`. The installer backs up any existing `WoWMCPData` folder to `Interface\AddOns-backups` before copying the two addon files. It leaves other addons and character settings alone. You can also copy the `WoWMCPData` folder manually to `Interface\AddOns` and check that `WoWMCPData.toc` sits directly inside it.

On the character selection screen, enable **WoW MCP Data** in **AddOns**. Enter the world or type `/reload` if the game is already open. Keep the small strip visible in the lower-left corner.

## Configure an MCP client

The server uses **stdio**. Set `WOW_GAME_DIR` to the game folder and launch `server.py` with the virtual environment's Python. For Codex, an example `config.toml` entry is:

```toml
[mcp_servers.wow_335_live]
command = 'C:\path\to\wow-335-live-mcp\.venv\Scripts\python.exe'
args = ['C:\path\to\wow-335-live-mcp\server.py']
env = { WOW_GAME_DIR = 'C:\Games\World of Warcraft 3.3.5a' }
```

Edit both paths. Restart the MCP client after changing its configuration. The server does not need an OpenAI API key for local stdio use. Codex's `mcp_servers` settings are described in the [official OpenAI configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference).

For ChatGPT on another process or device, use a private connection such as [OpenAI Secure MCP Tunnel](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels). Keep its tunnel ID, runtime key, credentials, and local profile **outside this repository**. A public GitHub repository containing source code does not make the user's local MCP server publicly reachable.

## Verify

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
'{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | .\.venv\Scripts\python.exe .\server.py
```

Ask the MCP client to call `wow_status`, then `read_wow_live_data`. A successful live response has `available: true`, `wire_version: 3` under `data`, and a small `age_seconds`. If it times out, check that the addon is enabled, the game is not minimized, the strip is visible, and `WOW_GAME_DIR` points to the correct installation.

## Privacy and limitations

- Tool calls can reveal character and realm names, group members, inventory, quests, NPC text, and screenshots to the connected MCP client. A remote client or tunnel may transmit these responses to its provider. Connect only a client you trust.
- `capture_wow` briefly brings the game forward. Windows that overlap the game's rectangle can appear in the captured image. The previous foreground window is restored when possible.
- `read_wow_game_data` reads only the addon's saved export, not account credentials. The export still contains character data; do not commit it.
- Live reads may fail when WoW is minimized, the strip is covered, Windows blocks capture, or an addon errors. A failed read must not be treated as current game state.
- The server does not log in, move the character, purchase items, accept quests, or alter the game client.

## Development

Run tests with `python -m unittest discover -s tests -v`. The Windows CI job checks Python syntax and exercises the packet decoder and MCP responses with synthetic data. Live WoW behavior was checked manually on one 3.3.5a client; CI does not launch the game. Keep fixture data synthetic and never commit screenshots, `WTF`, logs, credentials, or tunnel profiles.

Contributions should preserve 3.3.5a API compatibility, read-only behavior, and the byte-level strip protocol. Update both `WoWMCPData.lua` and the Python decoder when changing wire keys or packet layout.

## License

MIT for this project's original code. World of Warcraft and third-party addons retain their respective owners and licenses.
