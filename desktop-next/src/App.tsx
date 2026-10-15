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
      setNotice(result.started ? "Przygotowuję DLL, addon i uruchamiam grę…" :
        result.reason === "already_starting" ? "Gra jest już uruchamiana." :
        "Wybierz prawidłowy folder z Wow.exe.");
      await update();
    } catch (error) {
      setNotice("Błąd uruchomienia: " + String(error));
    } finally {
      setPending("");
    }
  };

  const checkDll = async () => {
    if (pending) return;
    setPending("read");
    try {
      const result = await backend("refresh");
      setNotice(result.available ? "Odczyt DLL działa. Dane postaci są aktualne." :
        "Brak świeżych danych DLL. W grze wpisz /wowmcpnative.");
      await update();
    } catch (error) {
      setNotice("Błąd połączenia DLL: " + String(error));
    } finally {
      setPending("");
    }
  };

  const connected = Boolean(dashboard.available && !dashboard.demo &&
    dashboard.source === "experimental native DLL named pipe");
  const mcpSeen = dashboard.mcp_client?.recent === true;
  const data = connected ? dashboard.data : null;
  const character = data?.character;
  const quests = useMemo(() => Array.isArray(data?.quests) ? data.quests.filter(q => q && q.title) : [], [data?.quests]);
  const ready = quests.filter(isReady).length;
  const running = Boolean(dashboard.game?.running);
  const configured = Boolean(dashboard.game?.installed);
  const launching = Boolean(dashboard.launch?.busy || pending === "launch");
  const nativeReady = dashboard.native_setup?.ready === true || dashboard.native_setup?.bundled === true;
  const age = dashboard.transport?.age_seconds;
  const status = serviceError ? "Usługa nie odpowiada" :
    connected ? "Dane z DLL dostępne" :
    running ? "Gra uruchomiona · czekam na DLL" : "Brak połączenia z DLL";
  const subtitle = serviceError ? "Uruchom ponownie WoW Connect." :
    !configured ? "Wybierz folder z Wow.exe i uruchom grę." :
    !nativeReady ? "Instalator nie zawiera plików DLL. Pobierz najnowszą wersję." :
    !running ? "Uruchom WoW przez LichLoader i wejdź na postać." :
    !connected ? "Sprawdź /wowmcpnative w grze. Nie używamy paska RGB." :
    "Dane postaci przesyłane są automatycznie przez DLL.";

  return (
    <div className="app">
      <header className="top">
        <div className="brand">
          <span className="mark"><Swords size={19} strokeWidth={2.2}/></span>
          <div><strong>WoW Connect</strong><span>3.3.5a · Native MCP</span></div>
        </div>
        <button className="icon-button" title="Ustawienia" aria-label="Ustawienia"
          aria-expanded={showSettings} onClick={() => setShowSettings(v => !v)}>
          <Settings2 size={19}/>
        </button>
      </header>

      <main>
        <div className="intro">
          <span className="eyebrow">LIVE TELEMETRY</span>
          <h1>WoW i ChatGPT. Bez paska na ekranie.</h1>
          <p>Informacje o postaci, zadania i stan połączenia. Odczyt wyłącznie przez DLL.</p>
        </div>

        <section className="main-card" aria-label="Stan gry">
          <div className="state-row">
            <span className={`status-icon ${connected ? "ok" : serviceError ? "error" : "idle"}`}>
              {connected ? <Wifi size={22}/> : serviceError ? <WifiOff size={22}/> : <Swords size={22}/>}
            </span>
            <div className="state-copy"><h2>{status}</h2><p>{subtitle}</p></div>
            <span className={`state-pill ${connected ? "positive" : ""}`}>
              <span className="status-dot"/>{connected ? "DLL połączona" : "DLL offline"}
            </span>
          </div>
          <div className="buttons">
            <button className="button primary" onClick={() => void startGame()}
              disabled={Boolean(pending || dashboard.launch?.busy || serviceError || (configured && !nativeReady))}>
              <Play size={17} fill="currentColor"/>
              {launching ? "Uruchamianie…" : running ? "WoW uruchomiony" : "Uruchom WoW z DLL"}
            </button>
            <button className="button secondary" onClick={() => void checkDll()}
              disabled={Boolean(pending || serviceError || !configured)}>
              <RefreshCw size={17} className={pending === "read" ? "spin" : ""}/>
              Sprawdź DLL
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
            <div className="card-heading"><h3>Twoja postać</h3><span>{connected ? "Na żywo" : "Oczekiwanie na DLL"}</span></div>
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
            </> : <p className="card-empty">Po otrzymaniu pakietu DLL pojawią się dane Twojej postaci.</p>}
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
            </> : <p className="card-empty">Zadania pojawią się automatycznie po połączeniu DLL.</p>}
          </section>
        </div>

        <section className="connection-footer" aria-label="Diagnostyka połączenia">
          <div><span className={`mini-dot ${connected ? "good" : ""}`}/><strong>DLL</strong>
            <span>{connected ? `Pakiety na żywo${typeof age === "number" ? ` · ${Math.round(age)} s` : ""}` : "Brak danych"}</span></div>
          <div><span className={`mini-dot ${mcpSeen ? "good" : ""}`}/><strong>MCP</strong>
            <span>{mcpSeen ? "Lokalny klient aktywny" : "Brak żądań klienta"}</span></div>
          <button className="help" title="MCP oznacza aktywność lokalnego klienta. Nie potwierdza, że ChatGPT jest połączony z serwerem. Zdalna wtyczka wymaga osobnej konfiguracji." aria-label="Informacja o MCP"><CircleHelp size={16}/></button>
        </section>
        {!mcpSeen && connected && <p className="connection-hint">
          DLL przesyła dane do WoW Connect. Aby ChatGPT je widział, musi też działać
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
          <p className="native-ready">Tylko DLL · automatyczne przesyłanie pakietów z addonu WoWMCPData bez widocznego kwadratu.</p>
          <p className="settings-note">Addon zbiera informacje z API gry. DLL przekazuje je do lokalnego odbiornika. Osobny klient MCP przekazuje odczyty do ChatGPT. Zielony status DLL nie jest potwierdzeniem połączenia ChatGPT.</p>
        </section>}
      </main>
      <footer>WoW Connect <span>·</span> Lokalne dane gry, tylko do odczytu</footer>
    </div>
  );
}
