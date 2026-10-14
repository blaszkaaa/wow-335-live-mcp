# WoW MCP Control Center — Tauri Desktop

Nowy interfejs Windows bazuje na **Tauri 2, React i TypeScript**, zamiast
Tkinter. Obsługuje systemowy WebView2 oraz usługę Python działającą lokalnie.

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
