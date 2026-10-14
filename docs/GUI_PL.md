# WoW MCP Control Center — instrukcja (Windows)

Gra: World of Warcraft 3.3.5a (w tym klient 12340).
Interfejs aplikacji jest po polsku.

## Instalacja aplikacji

1. Pobierz artefakt **WoW-MCP-Control-Center-Windows** z GitHub Actions przy PR #1.
2. Rozpakuj oba archiwa: GitHub pobierze ZIP z plikiem
   **WoW-MCP-Control-Center-Windows-x86-bridge.zip**.
3. Uruchom **WoW-MCP-Control-Center.exe**. Nie trzeba instalować Pythona.
4. Otwórz **Ustawienia → Wybierz katalog WoW** i wskaż folder zawierający Wow.exe.
5. Otwórz **Przegląd**.

## Odczyt prawdziwych danych z gry już teraz

- Musisz mieć zainstalowany addon **WoWMCPData**, z widocznym kolorowym paskiem.
- Uruchom grę, nie minimalizuj okna.
- Kliknij **Odczytaj WoW z addonu**.
- Aplikacja pokaże prawdziwe dane postaci, questy i statystyki, jeżeli uda się
  odczytać kompletną ramkę transmisji. Odczyt jest wykonywany na żądanie, nie
  automatycznie co sekundę. Po 60 sekundach dane przestają być oznaczane jako aktualne.
- W **Zadaniach** zobaczysz cele questów, a w **Postaci** szczegóły bohatera.

To jest obecny, sprawdzony transport przez piksele, a nie transport DLL.

## Test DLL bez uruchamiania WoW

Kliknij **Wyślij demo DLL**. Dołączony program demonstracyjny wysyła przykładowy
snapshot przez natywną bibliotekę DLL do named pipe, a aplikacja pokazuje postać
"Demo". Ten test sprawdza tylko transport. NIE przedstawia aktualnego stanu gry.

## ChatGPT + GUI

Aplikacja udostępnia dane odebrane przez DLL przez lokalne API na 127.0.0.1.
Aby ten sam kanał odczytywał MCP, w jego środowisku ustaw:

    WOW_MCP_NATIVE_BRIDGE=1
    WOW_MCP_NATIVE_HUB=1
    WOW_GAME_DIR=C:\ścieżka\do\World of Warcraft 3.3.5a

**Kolejność uruchamiania:** najpierw GUI, następnie MCP/ChatGPT. Jeśli
MCP działał wcześniej, uruchom połączenie MCP ponownie.

Nowe narzędzia MCP:
- wow_native_status — bieżący status transmisji DLL.
- read_wow_native_data — ostatni poprawny snapshot DLL.

Odczyt addonu wykonany w GUI nie jest tym samym kanałem co DLL. W ChatGPT
prawdziwy odczyt za pomocą addonu nadal działa przez **read_wow_live_data**.

## Bezpieczeństwo i ograniczenia

- W tej wersji nie istnieje jeszcze funkcja WoWMCP_Publish w Lua wewnątrz WoW.
  DLL z PR to autonomiczny transport, NIE gotowe rozszerzenie gry.
- NIE wstrzykuj DLL do WoW.exe. Modyfikacja klienta może naruszać regulamin
  Warmane i skutkować blokadą konta.
- Lokalny serwer GUI nie jest publicznym serwerem WWW. Używa tokenu zapisanego
  w profilu bieżącego użytkownika Windows. Nie publikuj pliku
  %LOCALAPPDATA%\WoWMCP\control-center.json.
- Zamknięcie GUI zatrzymuje hub odczytów. Używaj aplikacji tylko na zaufanym PC.
- MCP nie steruje postacią.

## Uruchomienie ze źródeł (programiści)

Z folderu repozytorium:

    py -3 -m pip install -r requirements.txt
    py -3 desktop_app.py

DLL i nadajnik demo:

    cmake -S native_bridge -B build/native-bridge -A Win32
    cmake --build build/native-bridge --config Release

Szczegóły protokołu: native_bridge/README.md.
