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
      const data = await getDashboard();
      setDashboard(data);
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
        setNotice("Zapisano lokalizację gry.");
        await update();
      }
    } catch (error) {
      setNotice("Nie udało się wybrać folderu: " + String(error));
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
      const response = await backend("launch");
      setNotice(response.started ? "Przygotowuję addon i uruchamiam WoW…" :
        response.reason === "already_starting" ? "Gra już jest uruchamiana." :
        "Najpierw wskaż prawidłowy folder z Wow.exe.");
      await update();
    } catch (error) {
      setNotice("Nie udało się uruchomić WoW: " + String(error));
    } finally {
      setPending("");
    }
  };

  const readGame = async () => {
    if (pending || dashboard.read_in_progress) return;
    setPending("read");
    try {
      const response = await backend("refresh");
      setNotice(response.started ? "Odczytuję dane z gry…" :
        response.reason === "already_running" ? "Odczyt już trwa." :
        "Najpierw wskaż folder gry.");
      await update();
    } catch (error) {
      setNotice("Błąd odczytu: " + String(error));
    } finally {
      setPending("");
    }
  };

  const native = dashboard.transport;
  const dllConnected = Boolean(connected && dashboard.source === "experimental native DLL named pipe" && native?.available);
  const connected = Boolean(dashboard.available && !dashboard.demo);
  const data = connected ? dashboard.data : null;
  const character = data?.character;
  const quests = useMemo(() => Array.isArray(data?.quests) ? data.quests.filter(q => q && q.title) : [], [data?.quests]);
  const ready = quests.filter(isReady).length;
  const running = Boolean(dashboard.game?.running);
  const configured = Boolean(dashboard.game?.installed);
  const launching = Boolean(dashboard.launch?.busy || pending === "launch");
  const status = serviceError ? "Usługa nie odpowiada" : connected ? "Dane gry dostępne"
    : dashboard.read_in_progress ? "Trwa odczyt" : running ? "Gra uruchomiona" : "Niepołączono";
  const subtitle = serviceError ? "Spróbuj uruchomić aplikację ponownie."
    : !configured ? "Wybierz folder z plikiem Wow.exe, aby rozpocząć."
    : !running ? "Uruchom grę, następnie wejdź na postać."
    : !connected ? "Włącz addon WoWMCPData i użyj /reload, potem kliknij Odczytaj."
    : "Połączenie z Twoją postacią jest gotowe.";

  return (
    <div className="app">
      <header className="top">
        <div className="brand"><span className="mark"><Swords size={19} strokeWidth={2.2}/></span>
          <div><strong>WoW Connect</strong><span>3.3.5a · MCP</span></div>
        </div>
        <button className="icon-button" title="Ustawienia" aria-label="Ustawienia" aria-expanded={showSettings}
          onClick={() => setShowSettings(v => !v)}><Settings2 size={19}/></button>
      </header>

      <main>
        <div className="intro">
          <span className="eyebrow">POŁĄCZENIE Z GRĄ</span>
          <h1>Wszystko w jednym miejscu.</h1>
          <p>Uruchom WoW, połącz dane postaci z ChatGPT i graj.</p>
        </div>

        <section className="main-card" aria-label="Stan gry">
          <div className="state-row">
            <span className={`status-icon ${connected ? "ok" : serviceError ? "error" : "idle"}`}>
              {connected ? <Wifi size={22}/> : serviceError ? <WifiOff size={22}/> : <Swords size={22}/>}
            </span>
            <div className="state-copy"><h2>{status}</h2><p>{subtitle}</p></div>
            <span className={`state-pill ${connected ? "positive" : ""}`}>
              <span className="status-dot"/>{connected ? "Połączono" : "Offline"}
            </span>
          </div>
          <div className="buttons">
            <button className="button primary" onClick={() => void startGame()}
              disabled={Boolean(pending || dashboard.launch?.busy || serviceError)}>
              <Play size={17} fill="currentColor"/>{launching ? "Uruchamianie…" : running ? "WoW uruchomiony" : "Uruchom WoW"}
            </button>
            <button className="button secondary" onClick={() => void readGame()}
              disabled={Boolean(pending || dashboard.read_in_progress || serviceError || !configured)}>
              <RefreshCw size={17} className={dashboard.read_in_progress ? "spin" : ""}/>
              {dashboard.read_in_progress ? "Odczytywanie…" : "Odczytaj postać"}
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
            <div className="card-heading"><h3>Twoja postać</h3><span>{connected ? "Aktualne dane" : "Brak odczytu"}</span></div>
            {character ? <>
              <div className="character-row"><div className="character-avatar">{(character.name || "?").slice(0, 1).toUpperCase()}</div>
                <div className="character-name"><strong>{character.name || "Nieznana postać"}</strong>
                  <span>Poziom {number(character.level)} · {character.class || "Postać"}</span></div></div>
              <div className="resource"><div><span>Zdrowie</span><strong>{percent(character.health, character.health_max)}%</strong></div>
                <div className="track"><div className="fill health" style={{width: `${percent(character.health, character.health_max)}%`}}/></div></div>
              <div className="resource"><div><span>Doświadczenie</span><strong>{percent(character.xp, character.xp_max)}%</strong></div>
                <div className="track"><div className="fill xp" style={{width: `${percent(character.xp, character.xp_max)}%`}}/></div></div>
            </> : <p className="card-empty">Po odczycie gry zobaczysz tutaj swoją postać.</p>}
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
                  <span className={isReady(quest) ? "ready-quest" : ""}>{isReady(quest) ? <Check size={16}/> : <ArrowRight size={16}/>}</span>
                  <span>{quest.title}</span>
                </div>)}
                {quests.length > 10 && <small>Pozostałe zadania ({quests.length - 10}) są dostępne przez MCP.</small>}
              </div>}
            </> : <p className="card-empty">Zadania pojawią się po połączeniu.</p>}
          </section>
        </div>

        <section className="connection-footer" aria-label="Źródła danych">
          <div><span className={`mini-dot ${dllConnected ? "good" : ""}`}/><strong>DLL</strong><span>{dllConnected ? "Przesyła dane" : "Brak danych z DLL"}</span></div>
          <div><span className={`mini-dot ${connected && !dllConnected ? "good" : ""}`}/><strong>Addon</strong><span>{dashboard.game?.addon_installed ? "Zainstalowany" : "Nie zainstalowano"}</span></div>
          <button className="help" title="DLL nie jest automatycznie wstrzykiwana do WoW. Zielony status pojawia się dopiero po otrzymaniu prawdziwych pakietów." aria-label="Informacja o DLL"><CircleHelp size={16}/></button>
        </section>

        {showSettings && <section className="settings" aria-label="Ustawienia gry">
          <h3>Folder gry</h3>
          <p>{dashboard.game?.directory || "Nie wybrano folderu."}</p>
          <button className="button secondary" onClick={() => void changeFolder()} disabled={Boolean(pending || serviceError)}>
            <FolderOpen size={17}/>Zmień folder
          </button>
          <p className="settings-note">DLL nie jest wstrzykiwana do klienta Warmane. Jej połączenie pojawi się dopiero po otrzymaniu prawdziwych danych. Odczyt z addonu pozostaje dostępny.</p>
        </section>}
      </main>
      <footer>WoW MCP <span>·</span> Tylko lokalny odczyt danych</footer>
    </div>
  );
}
