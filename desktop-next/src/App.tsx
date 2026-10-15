import { useCallback, useEffect, useMemo, useState } from "react";
import { ArrowRight, Check, ChevronDown, ChevronUp, CircleHelp, FolderOpen, Play, RefreshCw, Settings2, Swords, Wifi, WifiOff } from "lucide-react";
import { backend, chooseGameDirectory, getDashboard } from "./api";
import type { Dashboard, Quest } from "./types";

const EMPTY: Dashboard = { available: false, data: null, game: { installed: false, running: false, directory: "" } };
const number = (value?: number) => typeof value === "number" ? value.toLocaleString("pl-PL") : "—";
const percent = (value?: number, max?: number) => max && typeof value === "number"
  ? Math.max(0, Math.min(100, Math.round((value / max) * 100))) : 0;
const isReady = (quest: Quest) => Boolean(quest.ready_to_turn_in || quest.complete === true || quest.complete === 1);

export default function App() {
  const [dashboard, setDashboard] = useState<Dashboard>(EMPTY);
  const [serviceError, setServiceError] = useState(false);
  const [pending, setPending] = useState<"" | "launch" | "read" | "folder">("");
  const [notice, setNotice] = useState("");
  const [showDetails, setShowDetails] = useState(false);
  const [showSettings, setShowSettings] = useState(false);

  const update = useCallback(async () => {
    try {
      const result = await getDashboard();
      setDashboard(result);
      setServiceError(false);
    } catch {
      setServiceError(true);
    }
  }, []);

  useEffect(() => {
    void update();
    const interval = window.setInterval(() => void update(), 2500);
    return () => window.clearInterval(interval);
  }, [update]);

  const changeFolder = async () => {
    if (pending) return;
    setPending("folder");
    try {
      const selected = await chooseGameDirectory();
      if (selected) {
        await backend("set_settings", { game_dir: selected });
        setNotice("Folder gry zapisany.");
        await update();
      }
    } catch (error) {
      setNotice("Nie można zmienić folderu: " + String(error));
    } finally {
      setPending("");
    }
  };

  const startGame = async () => {
    if (pending || dashboard.launch?.busy) return;
    setPending("launch");
    try {
      if (!dashboard.game?.installed) {
        const selected = await chooseGameDirectory();
        if (!selected) return;
        await backend("set_settings", { game_dir: selected });
      }
      const result = await backend("launch");
      setNotice(result.started ? "Instaluję addon i uruchamiam zwykły Wow.exe…" :
        result.reason === "already_starting" ? "Gra jest już uruchamiana." :
        "Wybierz prawidłowy folder z Wow.exe.");
      await update();
    } catch (error) {
      setNotice("Błąd uruchomienia: " + String(error));
    } finally {
      setPending("");
    }
  };

  const readGame = async () => {
    if (pending) return;
    setPending("read");
    try {
      const result = await backend("refresh");
      setNotice(result.started ? "Odczytuję kolorowy pasek WoWMCPData z okna gry…" :
        result.reason === "already_running" ? "Odczyt już trwa." :
        "Najpierw wskaż folder gry.");
      await update();
    } catch (error) {
      setNotice("Błąd odczytu addonu: " + String(error));
    } finally {
      setPending("");
    }
  };

  const connected = Boolean(dashboard.available && !dashboard.demo &&
    dashboard.source === "WoW addon visual data strip");
  const mcpSeen = dashboard.mcp_client?.recent === true;
  const data = connected ? dashboard.data : null;
  const character = data?.character;
  const quests = useMemo(() => Array.isArray(data?.quests) ? data.quests.filter(q => q && q.title) : [], [data?.quests]);
  const ready = quests.filter(isReady).length;
  const running = Boolean(dashboard.game?.running);
  const configured = Boolean(dashboard.game?.installed);
  const launching = Boolean(dashboard.launch?.busy || pending === "launch");
  const readyToLaunch = configured;
  const reading = Boolean(dashboard.read_in_progress);
  const status = serviceError ? "Usługa nie odpowiada" :
    reading ? "Odczytuję pasek addonu" :
    connected ? "Dane postaci dostępne" :
    running ? "Gra uruchomiona" : "Oczekiwanie na grę";
  const subtitle = serviceError ? "Uruchom ponownie WoW Connect." :
    !configured ? "Wybierz folder z Wow.exe i uruchom grę." :
    !running ? "Uruchom zwykły WoW i wejdź na postać." :
    reading ? "Okno WoW musi być widoczne, a kwadrat w lewym dolnym rogu niezasłonięty." :
    !connected ? "Włącz WoWMCPData i użyj /reload, następnie kliknij Odczytaj postać." :
    "Odczyt z kolorowego kwadratu addonu — bez DLL.";

  return (
    <div className="app">
      <header className="top">
        <div className="brand">
          <span className="mark"><Swords size={19} strokeWidth={2.2}/></span>
          <div><strong>WoW Connect</strong><span>3.3.5a · Addon MCP</span></div>
        </div>
        <button className="icon-button" title="Ustawienia" aria-label="Ustawienia"
          aria-expanded={showSettings} onClick={() => setShowSettings(v => !v)}>
          <Settings2 size={19}/>
        </button>
      </header>

      <main>
        <div className="intro">
          <span className="eyebrow">ODCZYT Z ADDONU</span>
          <h1>WoW i ChatGPT. Bez DLL.</h1>
          <p>Uruchom WoW normalnie i odczytuj postać z kwadratu w lewym dolnym rogu.</p>
        </div>

        <section className="main-card" aria-label="Stan gry">
          <div className="state-row">
            <span className={`status-icon ${connected ? "ok" : serviceError ? "error" : "idle"}`}>
              {connected ? <Wifi size={22}/> : serviceError ? <WifiOff size={22}/> : <Swords size={22}/>}
            </span>
            <div className="state-copy"><h2>{status}</h2><p>{subtitle}</p></div>
            <span className={`state-pill ${connected ? "positive" : ""}`}>
              <span className="status-dot"/>{connected ? "Odczyt gotowy" : "Brak odczytu"}
            </span>
          </div>
          <div className="buttons">
            <button className="button primary" onClick={() => void startGame()}
              disabled={Boolean(pending || dashboard.launch?.busy || serviceError)}>
              <Play size={17} fill="currentColor"/>
              {launching ? "Uruchamianie…" : running ? "WoW uruchomiony" : "Uruchom WoW"}
            </button>
            <button className="button secondary" onClick={() => void readGame()}
              disabled={Boolean(pending || reading || serviceError || !readyToLaunch)}>
              <RefreshCw size={17} className={reading || pending === "read" ? "spin" : ""}/>
              {reading ? "Odczytywanie…" : "Odczytaj postać"}
            </button>
          </div>
          {dashboard.launch?.status && dashboard.launch.status !== "idle" && (
            <p className={`inline-message ${dashboard.launch.status === "error" ? "danger" : ""}`}>
              {dashboard.launch.message}
            </p>
          )}
          {notice && <p className="inline-message" role="status">{notice}</p>}
        </section>

        <div className="two-col">
          <section className="small-card" aria-label="Postać">
            <div className="card-heading"><h3>Twoja postać</h3><span>{connected ? "Ostatni odczyt" : "Brak odczytu"}</span></div>
            {character ? <>
              <div className="character-row">
                <div className="character-avatar">{(character.name || "?").slice(0, 1).toUpperCase()}</div>
                <div className="character-name"><strong>{character.name || "Nieznana postać"}</strong>
                  <span>Poziom {number(character.level)} · {character.class || "Postać"}</span></div>
              </div>
              <div className="resource"><div><span>Zdrowie</span><strong>{percent(character.health, character.health_max)}%</strong></div>
                <div className="track"><div className="fill health" style={{width:`${percent(character.health, character.health_max)}%`}}/></div></div>
              <div className="resource"><div><span>Doświadczenie</span><strong>{percent(character.xp, character.xp_max)}%</strong></div>
                <div className="track"><div className="fill xp" style={{width:`${percent(character.xp, character.xp_max)}%`}}/></div></div>
            </> : <p className="card-empty">Odczytaj widoczny kwadrat WoWMCPData w grze.</p>}
          </section>

          <section className="small-card" aria-label="Zadania">
            <div className="card-heading"><h3>Zadania</h3><span>{connected ? `${quests.length} aktywnych` : "Brak odczytu"}</span></div>
            {connected ? <>
              <div className="quest-summary"><strong>{ready}</strong><span>gotowych do oddania</span></div>
              {quests.length > 0 && <button className="text-button" onClick={() => setShowDetails(v => !v)}>
                {showDetails ? "Ukryj zadania" : "Pokaż zadania"} {showDetails ? <ChevronUp size={16}/> : <ChevronDown size={16}/>}
              </button>}
              {showDetails && <div className="quests">
                {quests.slice(0, 10).map((quest, i) => <div className="quest" key={String(quest.title) + i}>
                  <span className={isReady(quest) ? "ready-quest" : ""}>
                    {isReady(quest) ? <Check size={16}/> : <ArrowRight size={16}/>}
                  </span>
                  <span>{quest.title}</span>
                </div>)}
                {quests.length > 10 && <small>Pozostałe zadania są dostępne przez MCP.</small>}
              </div>}
            </> : <p className="card-empty">Zadania pojawią się po odczycie addonu.</p>}
          </section>
        </div>

        <section className="connection-footer" aria-label="Diagnostyka połączenia">
          <div><span className={`mini-dot ${connected ? "good" : ""}`}/><strong>Addon RGB</strong>
            <span>{connected ? "Odczyt zakończony" : dashboard.game?.addon_installed ? "Zainstalowany" : "Nie zainstalowano"}</span></div>
          <div><span className={`mini-dot ${mcpSeen ? "good" : ""}`}/><strong>MCP</strong>
            <span>{mcpSeen ? "Lokalny klient aktywny" : "Brak żądań klienta"}</span></div>
          <button className="help" title="MCP oznacza aktywność lokalnego klienta; nie potwierdza połączenia z chmurą ChatGPT." aria-label="Informacja o MCP"><CircleHelp size={16}/></button>
        </section>
        {!mcpSeen && connected && <p className="connection-hint">
          WoW Connect odczytuje addon. Aby ChatGPT widział dane, musi też działać
          podłączony serwer MCP. Sprawdź konfigurację połączenia wtyczki ChatGPT.
        </p>}

        {showSettings && <section className="settings" aria-label="Ustawienia gry">
          <h3>Folder gry</h3>
          <p>{dashboard.game?.directory || "Nie wybrano folderu."}</p>
          <button className="button secondary" onClick={() => void changeFolder()}
            disabled={Boolean(pending || serviceError)}>
            <FolderOpen size={17}/>Zmień folder
          </button>
          <h3 className="settings-subheading">Źródło danych</h3>
          <p className="native-ready">Tylko addon WoWMCPData · widoczny kolorowy kwadrat w lewym dolnym rogu. Bez DLL i LichLoadera.</p>
          <p className="settings-note">Addon zbiera dane gry i pokazuje je jako kolorowy pasek. WoW Connect odczytuje go z widocznego okna WoW na żądanie. Osobny klient MCP musi być połączony, aby przekazywać odczyty do ChatGPT. W razie starej wersji addonu wpisz /reload.</p>
        </section>}
      </main>
      <footer>WoW Connect <span>·</span> Lokalne dane gry, tylko do odczytu</footer>
    </div>
  );
}
