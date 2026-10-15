# WoW Connect — lekka aplikacja Windows

Aplikacja desktopowa Tauri 2 + React dla WoW 3.3.5a. Jeden jasny ekran zamiast kilku zakładek: uruchamianie gry, odczyt postaci, podstawowy stan zadań oraz uczciwy wskaźnik połączenia.

## Pierwsze uruchomienie

1. Zainstaluj aktualny instalator z artefaktu **WoW-MCP-Control-Center-Tauri-Windows** w GitHub Actions (**Tauri Windows Desktop**).
2. W aplikacji kliknij **Uruchom WoW** i wskaż katalog zawierający `Wow.exe`. Przykład: `C:\Users\mati\Downloads\World of Warcraft 3.3.5a`.
3. Aplikacja automatycznie aktualizuje addon WoWMCPData (z kopią poprzedniej wersji) i uruchamia **oryginalną** grę. Jeśli jest już włączona, wykonaj `/reload`.
4. Sprawdź na ekranie wyboru postaci, że addon **WoW MCP Data** jest aktywny. Wejdź do świata i kliknij **Odczytaj postać**.
5. Opcja zmiany folderu znajduje się pod ikoną ustawień.

Odczyt wizualny wymaga niezminimalizowanego okna gry oraz widocznego paska addonu. Nie zachodzi automatyczne odczytywanie obrazu co kilka sekund: przycisk pozwala świadomie wywołać odczyt. Gdy prawdziwe dane są dostępne, widać imię postaci, poziom, paski HP/XP i liczbę gotowych zadań.

## ChatGPT / lokalny MCP

Usługa desktopowa automatycznie uruchamia lokalny hub z losowym tokenem. Oddzielny proces MCP może teraz sam wykryć działający hub i wybraną w aplikacji ścieżkę do gry. Gdy gra dostarcza prawdziwe, świeże dane natywne, `read_wow_live_data` preferuje je bez osobnych zmiennych `WOW_MCP_NATIVE_BRIDGE`; gdy ich nie ma, korzysta z odczytu paska WoWMCPData.

Nadal trzeba osobno skonfigurować lokalny serwer MCP lub prywatne połączenie z ChatGPT; samo uruchomienie programu nie rejestruje go w zdalnej sesji.

## DLL: ważne ograniczenie

**Zielona etykieta DLL** jest pokazywana wyłącznie wtedy, gdy do aplikacji docierają rzeczywiste dane postaci przez eksperymentalny Named Pipe. Uruchomiony odbiornik bez pakietów to **Brak danych z DLL**, a nie „połączono”.

Repo zawiera działający protokół Named Pipe, testowy natywny nadajnik Win32 oraz eksperymentalny adapter Lua→DLL oparty o WrathClassicAPI. Test transportu lub kompilacja adaptera **nie potwierdzają**, że biblioteka działa w Twojej grze. Aplikacja **nie ładuje ani nie wstrzykuje DLL** do klienta Warmane. Test w rzeczywistym kliencie wymaga autoryzowanego środowiska; tego nie da się zweryfikować w CI. Zwykły addon pozostaje obsługiwanym rozwiązaniem.

## Kompilacja Windows

Źródło jest kompilowane i pakowane przez `.github/workflows/tauri.yml` (Windows, Node 22, Python 3.11, Rust). Workflow uruchamia testy Pythona, kompilację TypeScript, budowę sidecar PyInstaller i instalatora NSIS. Kompilacja nie wymaga dodatkowego CMD przy uruchamianiu aplikacji.

Bezpośrednio z checkoutu:

```powershell
python -m pip install -r requirements.txt pyinstaller
pyinstaller --clean --noconfirm --onefile --windowed --hidden-import server --add-data "WoWMCPData;WoWMCPData" --name wow-mcp-service desktop_service.py
New-Item -ItemType Directory -Force desktop-next/src-tauri/binaries
Copy-Item dist/wow-mcp-service.exe desktop-next/src-tauri/binaries/wow-mcp-service-x86_64-pc-windows-msvc.exe
python desktop-next/scripts/generate_icons.py
cd desktop-next
npm install
npm run tauri build -- --bundles nsis
```
