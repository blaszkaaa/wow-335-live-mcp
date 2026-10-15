# WoW Connect 0.7 — ciemny motyw, addon RGB, bez DLL

Przywrócono bezpieczny, wcześniej działający odczyt WoW 3.3.5a za pomocą addonu **WoWMCPData**. W lewym dolnym rogu gry pojawia się **kolorowy kwadrat 32×16**, którego piksele aplikacja odczytuje na żądanie. WoW Connect nie wstrzykuje DLL, nie uruchamia LichLoadera i nie modyfikuje Wow.exe.

## Uruchomienie

1. Zainstaluj najnowszy instalator Windows z [GitHub Actions](https://github.com/blaszkaaa/wow-335-live-mcp/actions/workflows/tauri.yml).
2. Zamknij poprzednią grę uruchomioną przez LichLoader i WoW Connect. Nowa wersja ignoruje zapisany tryb natywny.
3. Uruchom WoW Connect, wskaż folder gry z `Wow.exe` i kliknij **Uruchom WoW**.
4. Program automatycznie instaluje nowy addon WoWMCPData (poprzednią wersję zachowuje jako kopię) oraz uruchamia **bezpośrednio Wow.exe**.
5. Na ekranie wyboru postaci upewnij się, że addon **WoW MCP Data** jest włączony. Po wejściu do gry powinien pojawić się kolorowy kwadrat **na dole po lewej**.
6. Nie minimalizuj WoW i nie zasłaniaj kwadratu. Kliknij **Odczytaj postać**; odbiór wszystkich stron kodowanych danych może potrwać kilkanaście sekund.

Gdy WoW już działa, kliknięcie uruchomienia jedynie zaktualizuje addon. W takim wypadku wpisz w grze `/reload`, by go odświeżyć.

## Co z pozostałościami po DLL?

Nowa aplikacja **nie ładuje** LichLoadera ani plików DLL nawet wtedy, gdy pozostały w katalogu gry. Nie usuwa automatycznie cudzych lub wcześniej zainstalowanych plików, aby nie uszkodzić Twojej gry. Jeśli chcesz usunąć poprzednią instalację WoW MCP, gdy gra jest zamknięta, zrób kopię i usuń tylko pliki, które wcześniej dodał WoW Connect: `LichLoader.exe`, `LichCore.dll`, `dll\WoWMCPNativeLua.dll` oraz wpis `dll\WoWMCPNativeLua.dll` w `lichloader.txt`. Nie kasuj plików należących do innych programów/modów. **Sam prawidłowy start przez Wow.exe nie wymaga tego czyszczenia.**

## MCP i ChatGPT

Aplikacja korzysta z lokalnej usługi do pokazywania ostatniego odczytu. Klient MCP może także użyć `read_wow_live_data`, który wykonuje nowy odczyt **widocznego kwadratu** na żądanie. Odczyt ten wymaga prawidłowego okna gry, czasem przełączy fokus WoW, i może potrwać do 20 sekund.

Windows CI pakuje osobny serwer `wow-mcp-stdio.exe` (artefakt **WoW-MCP-Addon-STDIO-Windows**) z zachowaną nazwą pliku dla istniejącej konfiguracji lokalnego MCP. Przykładowa konfiguracja klientów wspierających stdio:

```toml
[mcp_servers.wow_335_addon]
command = 'C:\path\to\wow-mcp-stdio.exe'
```

Połączenie ChatGPT ze zdalną wtyczką/tunelem jest osobną konfiguracją i samo zainstalowanie programu jej nie naprawia. Status MCP w aplikacji informuje o aktywności lokalnego procesu, nie potwierdza automatycznie połączenia z chmurą.

## Budowanie

Windows workflow kompiluje wyłącznie aplikację Tauri, usługę Python i visual MCP stdio; nie pobiera ani nie pakuje bibliotek DLL. Oryginalny kod eksperymentalnego DLL może pozostać w repozytorium do celów archiwalnych, ale jest wyłączony z tej aplikacji.
