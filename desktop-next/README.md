# WoW Connect 0.6 — ciemny interfejs, dane tylko z DLL

Aplikacja Windows (Tauri 2 + React) pokazuje dane WoW 3.3.5a w ciemnym motywie. Strumień danych jest jeden:

```text
WoW addon WoWMCPData (bez kwadratu RGB)
   → WoWMCP.Publish (adapter DLL)
   → Windows named pipe
   → lokalna usługa WoW Connect
   → osobny serwer MCP
   → skonfigurowany klient MCP / ChatGPT
```

**Ważne:** addon WoWMCPData nadal musi być włączony, ponieważ zbiera informacje przez API Lua gry. Nie rysuje już kwadratu w lewym dolnym rogu ani nie koduje danych na ekranie. Połączenie DLL wymaga, aby gra była uruchomiona przez dołączony LichLoader. Wybrana wersja 3.3.5a i zasady serwera muszą pozwalać na taki moduł.

## Uruchomienie

1. Pobierz i zainstaluj plik z artefaktu **WoW-MCP-Control-Center-Tauri-Windows** w [GitHub Actions](https://github.com/blaszkaaa/wow-335-live-mcp/actions/workflows/tauri.yml).
2. Wybierz katalog zawierający `Wow.exe` i kliknij **Uruchom WoW z DLL**.
3. Program automatycznie aktualizuje addon, dołącza zweryfikowaną wersję LichLoader i swój adapter DLL, przygotowuje `lichloader.txt` i uruchamia klienta.
4. Wejdź na postać. W WoW Connect powinna pojawić się etykieta **DLL połączona**, a dane postaci powinny odnawiać się bez klikania.
5. W razie problemu wpisz w grze `/wowmcpnative`. Odpowiedź „ostatni pakiet wyslany” oznacza jedynie lokalną transmisję do usługi.

**Żaden odczyt na żywo nie wraca do paska RGB ani zrzutu ekranu.** Przycisk „Sprawdź DLL” sprawdza stan lokalnego strumienia natywnego, nie uruchamia capture. Nie modyfikujemy samego `Wow.exe`, nie zastępujemy cudzych plików LichLoader i zapisujemy kopie poprzednich adapterów DLL.

## MCP i ChatGPT — osobne połączenie

Dwie kontrolki w aplikacji pokazują **różne** rzeczy:

- **DLL:** lokalna usługa otrzymała świeże pakiety z prawdziwej postaci.
- **MCP:** w ostatnich 90 sekundach do tej usługi zgłosił się lokalny proces MCP obsługujący inicjalizację lub narzędzia. To **nie jest** dowód, że połączyła się chmura ChatGPT.

Nowy workflow Windows publikuje również artefakt **WoW-MCP-Native-STDIO-Windows** zawierający `wow-mcp-stdio.exe`. To niewielki serwer MCP do wywoływania narzędzi `wow_status`, `wow_native_status` i `read_wow_live_data` wyłącznie przez DLL. Nie wymaga `WOW_GAME_DIR` ani żadnej konfiguracji zrzutów obrazu: wykrywa autoryzowaną lokalną usługę WoW Connect.

Aby uruchomić **lokalnego klienta obsługującego stdio**, ustaw jego komendę na pełną ścieżkę do `wow-mcp-stdio.exe`. Przykładowa konfiguracja klienta MCP w formacie TOML:

```toml
[mcp_servers.wow_335_native]
command = 'C:\path\to\wow-mcp-stdio.exe'
```

Aby ChatGPT zdalnie korzystał z tego procesu, trzeba **podłączyć lub ponownie skonfigurować wtyczkę/tunel MCP** zgodnie z mechanizmem połączenia danej instalacji. Samo zainstalowanie WoW Connect nie może zmienić ustawień istniejącego konektora ChatGPT. Jeśli ChatGPT pokazuje „MCP server is not initialized”, to jest błąd tego osobnego połączenia, nawet jeśli DLL jest zielona. Po ponownym podłączeniu wtyczki sprawdź `wow_status` i `read_wow_live_data`.

Otwierając zdalny tunel, używaj tylko prywatnego, uwierzytelnionego połączenia. Nie wystawiaj lokalnego endpointu kontrolnego ani pliku `control-center.json` publicznie.

## Kompilacja i licencja

CI kompiluje adapter Win32 ze źródeł GPL WrathClassicAPI, weryfikuje archiwum LichLoader `v1.1.0` przez SHA-256, buduje osobno serwis GUI i program MCP stdio oraz publikuje odpowiadające źródła GPL jako **WoWMCP-Native-Corresponding-Source**.

Status „DLL połączona” wymaga rzeczywistych pakietów, ale nie zapewnia zgodności z zasadami serwerów online. Działania w grze ani obchodzenie systemów antycheat nie są częścią tego projektu.
