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

## DLL — automatyczne przygotowanie i uruchamianie

**Nie trzeba samodzielnie pobierać LichLoadera, kompilować adaptera, kopiować DLL ani edytować `lichloader.txt`.** Wersja instalatora Windows budowana z `.github/workflows/tauri.yml` zawiera potrzebne pliki.

1. Zainstaluj najnowszy instalator Windows **WoW Connect** z GitHub Actions.
2. Wybierz katalog gry zawierający `Wow.exe`.
3. W **Ustawienia → Sposób uruchamiania** wybierz jednorazowo **Przez LichLoader (DLL)**. Jest to opcjonalny tryb, wyłącznie dla środowisk, w których ładowanie modułów jest dozwolone.
4. Kliknij **Uruchom WoW z DLL**. Aplikacja sama zainstaluje/odświeży addon, przygotuje pliki DLL z własnego pakietu, dopisze adapter do konfiguracji i uruchomi grę przez LichLoader.
5. Po zalogowaniu do postaci zobacz w aplikacji, czy status **DLL: Przesyła dane** zmienił się na zielony. Tylko odebranie prawdziwych pakietów potwierdza działanie połączenia. W WoW można wpisać `/wowmcpnative` dla diagnostyki.

### Skąd pochodzą pliki?

- `LichLoader.exe` i `LichCore.dll`: oficjalne wydanie `v1.1.0` projektu [LichLoader](https://github.com/brues-code/LichLoader/releases/tag/v1.1.0), pobierane i weryfikowane według SHA-256 podczas budowania instalatora.
- `WoWMCPNativeLua.dll`: adapter zbudowany w CI z przypiętej rewizji [WrathClassicAPI](https://github.com/brues-code/WrathClassicAPI) oraz pliku `native_bridge/adapter/WoWMCPNativeLua.cpp`.
- Pełne źródła adaptera udostępnia artefakt **WoWMCP-Native-Corresponding-Source** w tym samym workflow GitHub Actions. Kod źródłowy LichLoadera jest dostępny w jego repozytorium.

**Zabezpieczenia:** nie modyfikujemy `Wow.exe`; nie nadpisujemy innych wersji `LichLoader.exe` ani `LichCore.dll`. Aktualizowana poprzednia DLL otrzymuje kopię w `WoWMCPBackups`, a inne wpisy w `lichloader.txt` pozostają. Jeśli gra już działa, uruchomienie w trybie DLL wymaga jej zamknięcia.

**Ograniczenia:** dostępność plików oraz poprawne uruchomienie programu nie dowodzą, że dany klient WoW przyjął moduł. Adapter nie był jeszcze zweryfikowany na działającym kliencie Warmane. Nie jest zapewnione obchodzenie zabezpieczeń gry, a zasady serwera mogą zabraniać takich bibliotek. Możesz zawsze przełączyć się na tryb **Standardowy** z odczytem wizualnym.

## Kompilacja Windows

Źródło jest kompilowane i pakowane przez `.github/workflows/tauri.yml` (Windows, Node 22, Python 3.11, Rust). Workflow uruchamia testy Pythona, kompilację TypeScript, budowę sidecar PyInstaller i instalatora NSIS. Kompilacja nie wymaga dodatkowego CMD przy uruchamianiu aplikacji.

Bezpośrednio z checkoutu:

```powershell
python -m pip install -r requirements.txt pyinstaller
# Najpierw zbuduj pakiet native_runtime: LichLoader.exe, LichCore.dll i WoWMCPNativeLua.dll.
pyinstaller --clean --noconfirm --onefile --windowed --hidden-import server --add-data "WoWMCPData;WoWMCPData" --add-data "native_runtime;native_runtime" --name wow-mcp-service desktop_service.py
New-Item -ItemType Directory -Force desktop-next/src-tauri/binaries
Copy-Item dist/wow-mcp-service.exe desktop-next/src-tauri/binaries/wow-mcp-service-x86_64-pc-windows-msvc.exe
python desktop-next/scripts/generate_icons.py
cd desktop-next
npm install
npm run tauri build -- --bundles nsis
```
