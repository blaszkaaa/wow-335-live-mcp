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

## DLL — uruchamianie przez przygotowany LichLoader

**Tryb DLL jest opcjonalny.** Aplikacja nie pobiera ani nie instaluje zewnętrznego loadera automatycznie; może uruchomić istniejący, prawidłowo skonfigurowany `LichLoader.exe` zamiast zwykłego `Wow.exe`.

### Przygotowanie plików (tylko w środowisku z odpowiednią zgodą)

1. Pobierz `LichLoader.exe` i `LichCore.dll` z [oficjalnej strony wydań LichLoader](https://github.com/brues-code/LichLoader/releases). Umieść oba pliki obok `Wow.exe`.
2. Pobierz wynik workflow **Experimental Lua DLL (offline only)** z Actions tego repozytorium. W pliku ZIP jest zbudowany adapter `WrathClassicAPI-offline-with-WoWMCP.dll`. Skopiuj go do folderu `dll` obok gry pod nazwą `WoWMCPNativeLua.dll`. Nie używaj zwykłej DLL WrathClassicAPI bez modułu WoWMCP.
3. W katalogu gry utwórz lub uzupełnij `lichloader.txt` o pojedynczą linię `dll\WoWMCPNativeLua.dll`. Zachowaj pozostałe wpisy i pliki.
4. W WoW Connect otwórz **Ustawienia → Sposób uruchamiania → Przez LichLoader (DLL)**. Aplikacja sprawdzi, czy klient i pliki wykonawcze są w formacie Win32 x86 oraz czy konfiguracja istnieje.
5. Zamknij działające WoW i kliknij **Uruchom WoW z DLL**. Wejdź na postać i wpisz `/wowmcpnative` w czacie gry. Gdy połączenie działa, status powinien pokazać poprawnie wysłany pakiet, a ekran WoW Connect wyświetli „DLL · Przesyła dane”.

**Ważne:** sama obecność plików lub start LichLoadera nie stanowią dowodu działania DLL. Status zmienia się dopiero po odebraniu świeżych danych postaci. Ten tryb wymaga rzeczywistego testu na wybranym kliencie. W razie niepowodzenia wybierz **Standardowy** — odczyt przez addon nadal działa.

Tryb DLL może być niezgodny z zasadami konkretnego serwera i jego zabezpieczeniami. Nie jest dostarczany mechanizm ich obchodzenia.

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
