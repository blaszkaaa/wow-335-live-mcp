# WoW MCP Control Center — Tauri Desktop

Nowy interfejs Windows bazuje na **Tauri 2, React i TypeScript**, zamiast
Tkinter. Obsługuje systemowy WebView2 oraz usługę Python działającą lokalnie.

## Poprawki stabilności i skalowania (v0.3.1)

- Kompilacja release Tauri korzysta z podsystemu okienkowego Windows,
  więc nie otwiera dodatkowej konsoli CMD obok aplikacji.
- Pomocnicze sprawdzanie procesu `Wow.exe` uruchamia `tasklist` bez
  widocznego okna i wykonuje to asynchronicznie, z cache co 8 sekund.
- W **Ustawienia → Skalowanie interfejsu** można wybrać **80–140%**.
  Preferencja zapamiętuje się na tym komputerze.
- Skróty: **Ctrl++**, **Ctrl+-**, **Ctrl+0** (przywrócenie 100%).
- Responsywny układ działa również w mniejszym oknie; minimalny rozmiar
  okna zmniejszono, aby działało lepiej przy 125–150% DPI Windows.
- Interfejs korzysta z czcionek systemowych w trybie offline.

Zmiany w kodzie wymagają ponownej instalacji **nowego EXE z GitHub Actions**;
stary instalator nie otrzyma poprawek samodzielnie.

## Uruchom WoW jednym kliknięciem

1. Otwórz WoW MCP Control Center i wybierz **Ustawienia**.
2. Wskaż folder zawierający `Wow.exe`, np.
   `C:\Users\mati\Downloads\World of Warcraft 3.3.5a`.
3. Kliknij **Uruchom WoW z addonem** lub na pulpicie **Uruchom WoW**.
4. Aplikacja instaluje/zaktualizuje `WoWMCPData.toc` i
   `WoWMCPData.lua` w `Interface\AddOns\WoWMCPData`, zachowując
   kopię poprzedniej wersji w `Interface\AddOns-backups`, jeśli się różni.
5. Uruchamia oryginalny `Wow.exe`. Jeśli gra już działa, nie otwiera drugiej
   instancji. Po zmianie addonu wpisz `/reload`.
6. Na ekranie postaci włącz **WoW MCP Data** w AddOns, jeśli dotąd nie
   był włączony. Po wejściu do gry kliknij **Odczytaj grę** w panelu.

Odbiornik Named Pipe i lokalny hub MCP uruchamiają się wraz z aplikacją.
**Ważne:** ten automat NIE instaluje i NIE wstrzykuje eksperymentalnej DLL do
klienta Warmane. Jest to nadal testowany oddzielnie moduł C++.
Jego obecność w repozytorium nie oznacza, że jest bezpieczny lub
zgodny z antycheatem danego serwera.

## Możliwości

- Przegląd z kartą postaci, statystykami, zadaniami i paskami HP / XP.
- Postać, wyszukiwarka questów, ekwipunek i diagnostyka transportu.
- Natywny wybór folderu Wow.exe.
- Ręczny odczyt danych addonu WoWMCPData.
- Tryb demonstracyjny, wyraźnie oznaczony jako DEMO.
- Usługa lokalna uruchamiana jako PyInstaller sidecar.
- Współdzielony hub MCP chroniony losowym tokenem.

## Instalator Windows

Wejdź na GitHub Actions > Tauri Windows Desktop > ostatni udany run.
Pobierz artefakt WoW-MCP-Control-Center-Tauri-Windows i uruchom instalator
z archiwum ZIP. Aplikacja korzysta z WebView2, dostępnego w Windows 10/11.

## Build lokalny

Wymagane: Node.js 22, Rust, Python 3.11, Visual Studio C++ Build Tools.

Z katalogu głównego projektu przygotuj usługę:

    python -m pip install -r requirements.txt pyinstaller
    pyinstaller --clean --noconfirm --onefile --windowed --hidden-import server --add-data "WoWMCPData/WoWMCPData.lua;WoWMCPData" --name wow-mcp-service desktop_service.py
    mkdir desktop-next\src-tauri\binaries
    copy dist\wow-mcp-service.exe desktop-next\src-tauri\binaries\wow-mcp-service-x86_64-pc-windows-msvc.exe
    python desktop-next\scripts\generate_icons.py
    cd desktop-next
    npm install
    npm run tauri build -- --bundles nsis

Podczas instalacji EXE usługa Python jest dołączana jako sidecar i uruchamiana
automatycznie. Tauri komunikuje się z nią wyłącznie przez lokalne API.

## Ważne

Dodano opcjonalny adapter C++ rejestrujący WoWMCP.Publish(json) w Lua
przez WrathClassicAPI. Kod kompiluje się jako Win32, ale nie jest jeszcze
zweryfikowany w działającym kliencie WoW i nie wolno zakładać zgodności z
antycheatem Warmane. Nie wstrzykuj DLL do WoW na serwerach bez zgody.
Domyślnie odczyt nadal działa przez wizualny addon WoWMCPData.
Dokumentacja: native_bridge/adapter/README.md.
