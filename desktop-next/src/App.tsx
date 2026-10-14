import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Activity, ArrowRight, BookOpen, Check, CheckCircle2, CircleHelp, Clock3,
  Compass, Copy, Cpu, Database, FolderOpen, HeartPulse, LayoutDashboard,
  Layers, MapPin, Package, Play, RefreshCcw, Search, Settings2, ShieldCheck, Signal,
  Sparkles, Swords, WifiOff, X,
} from "lucide-react";
import {backend, chooseGameDirectory, getDashboard} from "./api";
import type {Dashboard,GameData,Item,Page,Quest} from "./types";

const MENU: {group:string;items:{id:Page;label:string;Icon:typeof Activity}[]}[] = [
  {group:"TWOJA GRA",items:[
    {id:"overview",label:"Przegląd",Icon:LayoutDashboard},
    {id:"character",label:"Moja postać",Icon:ShieldCheck},
    {id:"quests",label:"Dziennik zadań",Icon:BookOpen},
    {id:"inventory",label:"Ekwipunek",Icon:Package},
  ]},
  {group:"NARZĘDZIA",items:[
    {id:"diagnostics",label:"Diagnostyka",Icon:Activity},
    {id:"settings",label:"Ustawienia",Icon:Settings2},
  ]},
];
const TITLES:Record<Page,string>={overview:"Przegląd",character:"Moja postać",quests:"Dziennik zadań",inventory:"Ekwipunek",diagnostics:"Diagnostyka",settings:"Ustawienia"};
const EMPTY:Dashboard={available:false,data:null,game:{installed:false,running:false,directory:""}};
const num=(v?:number)=>typeof v==="number"?v.toLocaleString("pl-PL"):"—";
const percentage=(v?:number,max?:number)=>max&&v!==undefined?Math.max(0,Math.min(100,Math.round(v/max*100))):0;
const time=(v?:number)=>v?new Date(v*1000).toLocaleTimeString("pl-PL"):"—";
const questReady=(q:Quest)=>Boolean(q.ready_to_turn_in);
const listQuests=(data:GameData|null)=>Array.isArray(data?.quests)?data.quests.filter(Boolean):[];
const items=(a?:Item[])=>Array.isArray(a)?a.filter(Boolean):[];
const cx=(...a:(string|false|undefined)[])=>a.filter(Boolean).join(" ");
const SCALE_MIN=80;
const SCALE_MAX=140;
const SCALE_STEP=10;
const SCALE_STORAGE_KEY="wowmcp.ui-scale";
const clampScale=(value:number)=>Math.min(SCALE_MAX,Math.max(SCALE_MIN,Math.round(value/SCALE_STEP)*SCALE_STEP));
function readSavedScale():number {
  try {
    const saved=Number(window.localStorage.getItem(SCALE_STORAGE_KEY)??100);
    return Number.isFinite(saved)?clampScale(saved):100;
  } catch {
    return 100;
  }
}

function Dot({on}:{on:boolean}){return <span className={cx("dot",on?"yes":"no")}/>;}
function Header({title,subtitle,action}:{title:string;subtitle?:string;action?:React.ReactNode}){return <div className="panel-head"><div><h3>{title}</h3>{subtitle&&<p>{subtitle}</p>}</div>{action}</div>;}
function Empty({title,body,Icon=Layers}:{title:string;body:string;Icon?:typeof Activity}){return <div className="empty"><span className="empty-art"><Icon size={24}/></span><strong>{title}</strong><p>{body}</p></div>;}
function Bar({label,value,max,color}:{label:string;value?:number;max?:number;color:string}){return <div className="bar-row"><div className="bar-label"><span>{label}</span><b>{num(value)} <i>/ {num(max)}</i></b></div><div className="bar-track"><div className={"bar-fill "+color} style={{width:percentage(value,max)+"%"}}/></div></div>;}
function Stat({label,value,detail,Icon,tone=""}:{label:string;value:string;detail:string;Icon:typeof Activity;tone?:string}){return <div className={"stat "+tone}><div className="stat-label"><span>{label}</span><Icon size={18}/></div><strong>{value}</strong><small>{detail}</small></div>;}
function QuestRow({q}:{q:Quest}){const objectives=Array.isArray(q.objectives)?q.objectives:[];return <div className="quest-row"><div className={cx("quest-symbol",questReady(q)&&"ready")}>{questReady(q)?<Check size={17}/>:<Compass size={17}/>}</div><div className="quest-text"><b>{q.title||"Zadanie bez nazwy"}</b><span>{questReady(q)?"Gotowe do oddania":objectives.length?String(objectives.filter(x=>x.done).length)+" / "+String(objectives.length)+" celów":"W trakcie"}</span></div><span className={cx("tag",questReady(q)&&"green")}>{questReady(q)?"Gotowe":"Aktywne"}</span></div>;}
function ItemRow({item}:{item:Item}){return <div className="item-row"><div className="item-box"><Package size={18}/></div><div><b>{item.name||"Przedmiot #"+String(item.id||"?")}</b><small>ID: {item.id??"—"}</small></div><span className="qty">×{item.count||1}</span></div>;}

export default function App(){
  const [page,setPage]=useState<Page>("overview");
  const [snapshot,setSnapshot]=useState<Dashboard>(EMPTY);
  const [serviceError,setServiceError]=useState("");
  const [loading,setLoading]=useState("");
  const [message,setMessage]=useState("");
  const [search,setSearch]=useState("");
  const [questFilter,setQuestFilter]=useState<"all"|"ready"|"active">("all");
  const [itemFilter,setItemFilter]=useState("");
  const [menuOpen,setMenuOpen]=useState(false);
  const [uiScale,setUiScale]=useState<number>(readSavedScale);
  const [viewportWidth,setViewportWidth]=useState(()=>window.innerWidth);
  const logicalWidth=viewportWidth/(uiScale/100);
  const compact=logicalWidth<1030;
  const narrow=logicalWidth<820;

  useEffect(()=>{
    document.documentElement.style.setProperty("--ui-scale",String(uiScale/100));
    try{window.localStorage.setItem(SCALE_STORAGE_KEY,String(uiScale));}catch{}
  },[uiScale]);
  useEffect(()=>{
    const onResize=()=>setViewportWidth(window.innerWidth);
    window.addEventListener("resize",onResize);
    return()=>window.removeEventListener("resize",onResize);
  },[]);
  useEffect(()=>{
    const onZoomKey=(e:KeyboardEvent)=>{
      if(!(e.ctrlKey||e.metaKey)||e.altKey)return;
      if(e.key==="+"||e.key==="="){e.preventDefault();setUiScale(z=>clampScale(z+SCALE_STEP));}
      else if(e.key==="-"){e.preventDefault();setUiScale(z=>clampScale(z-SCALE_STEP));}
      else if(e.key==="0"){e.preventDefault();setUiScale(100);}
    };
    window.addEventListener("keydown",onZoomKey);
    return()=>window.removeEventListener("keydown",onZoomKey);
  },[]);

  const refresh=useCallback(async()=>{
    try{setSnapshot(await getDashboard());setServiceError("");}
    catch(e){setServiceError(String(e));setSnapshot(EMPTY);}
  },[]);
  useEffect(()=>{void refresh();const t=setInterval(()=>void refresh(),2500);return()=>clearInterval(t);},[refresh]);
  useEffect(()=>{if(!message)return;const t=setTimeout(()=>setMessage(""),4500);return()=>clearTimeout(t);},[message]);

  const action=async(name:"refresh"|"demo")=>{
    setLoading(name);
    try{const result=await backend(name);
      setMessage(name==="demo"?"Uruchomiono podgląd demonstracyjny.":result.started?"Odczyt rozpoczęty.":"Wskaż folder gry lub sprawdź, czy odczyt już trwa.");
      await refresh();
    }catch(e){setMessage("Błąd: "+String(e));}
    finally{setLoading("");}
  };
  const selectFolder=async()=>{
    try{const dir=await chooseGameDirectory();if(!dir)return;await backend("set_settings",{game_dir:dir});setMessage("Zapisano folder gry.");await refresh();}
    catch(e){setMessage("Nie można ustawić folderu: "+String(e));}
  };
  const launchGame=async()=>{
    if(loading||snapshot.launch?.busy)return;
    setLoading("launch");
    try{
      if(!snapshot.game?.installed){
        const dir=await chooseGameDirectory();
        if(!dir)return;
        await backend("set_settings",{game_dir:dir});
      }
      const result=await backend("launch");
      setMessage(result.started?"Przygotowuję addon i uruchamiam WoW…":result.reason==="already_starting"?"Uruchamianie już trwa.":"Wybierz poprawny folder z Wow.exe.");
      await refresh();
    }catch(e){setMessage("Nie udało się rozpocząć uruchamiania: "+String(e));}
    finally{setLoading("");}
  };
  const go=(dest:Page)=>{setPage(dest);setMenuOpen(false);};
  const data=snapshot.available?(snapshot.data||null):null;
  const hero=data?.character||{};
  const quests=listQuests(data);
  const ready=quests.filter(questReady).length;
  const bags=items(data?.bags);
  const gear=items(data?.equipment);
  const shown=useMemo(()=>quests.filter(q=>{
    if(questFilter==="ready"&&!questReady(q))return false;
    if(questFilter==="active"&&questReady(q))return false;
    return (String(q.title||"")+" "+(q.objectives||[]).map(o=>o.text||"").join(" ")).toLocaleLowerCase().includes(search.toLocaleLowerCase());
  }),[quests,questFilter,search]);
  const shownItems=bags.filter(x=>(x.name||String(x.id||"")).toLocaleLowerCase().includes(itemFilter.toLocaleLowerCase()));
  const genuine=snapshot.available&&!snapshot.demo;
  const statusText=snapshot.demo?"Podgląd demonstracyjny":genuine?"Dane gry dostępne":snapshot.read_in_progress?"Trwa odczyt gry":"Brak danych gry";

  return <div className={cx("shell",compact&&"compact",narrow&&"narrow")}>
    <button className="hamburger" onClick={()=>setMenuOpen(v=>!v)}><Layers size={23}/></button>
    <aside className={cx("sidebar",menuOpen&&"show")}>
      <div className="identity"><div className="logo">W</div><div className="identity-text"><b>WoW <span>MCP</span></b><small>CONTROL CENTER</small></div></div>
      <nav>{MENU.map(section=><div className="nav-set" key={section.group}><div className="nav-caption">{section.group}</div>{section.items.map(({id,label,Icon})=><button key={id} className={cx("nav-link",page===id&&"selected")} onClick={()=>go(id)}><Icon size={19}/><span>{label}</span>{id==="quests"&&quests.length>0&&<em>{quests.length}</em>}</button>)}</div>)}</nav>
      <div className="nav-foot"><div className="server-card"><span className="server-icon"><Signal size={17}/></span><div><b>Lokalne połączenie</b><small>{snapshot.transport?.pipe?"Kanał Named Pipe gotowy":"Oczekiwanie na transport"}</small></div><Dot on={Boolean(snapshot.transport?.pipe)}/></div><div className="app-version">WoW 3.3.5a <span>•</span> Wersja rozwojowa</div></div>
    </aside>
    {menuOpen&&<div className="shade" onClick={()=>setMenuOpen(false)}/>}
    <div className="workspace">
      <header className="topbar"><div className="breadcrumb"><span>WoW MCP</span><ArrowRight size={13}/><strong>{TITLES[page]}</strong></div><div className="top-actions"><div className={cx("connection",genuine&&"is-online",snapshot.demo&&"is-demo")}><Dot on={genuine}/>{statusText}</div><button className="refresh-icon" onClick={()=>void refresh()} title="Odśwież panel"><RefreshCcw size={18}/></button></div></header>
      <main className="scroll">
        {page==="overview"&&<div className="page">
          <div className="page-title"><div><span className="eyebrow">PULPIT GRACZA</span><h1>Twój świat, pod kontrolą.</h1><p>Wszystkie informacje o Twojej postaci w jednym miejscu.</p></div><div className="game-launch-actions"><button className="btn primary right-button" onClick={()=>void launchGame()} disabled={Boolean(loading)||snapshot.launch?.busy}><Play size={17}/>{snapshot.launch?.busy?"Uruchamianie…":"Uruchom WoW"}</button><button className="btn secondary" onClick={()=>void action("refresh")} disabled={Boolean(loading)||snapshot.read_in_progress}><RefreshCcw size={17}/>Odczytaj grę</button></div></div>
          {snapshot.launch?.status && snapshot.launch.status!=="idle" && <div className={cx("launch-banner",snapshot.launch.status==="error"&&"launch-error")}><Signal size={17}/><span>{snapshot.launch.message}</span></div>}
          {snapshot.demo&&<div className="demo-alert"><CircleHelp size={17}/>Przeglądasz dane przykładowe — nie pochodzą one z Twojej gry.</div>}
          <section className="hero"><div className="halo"/><div className="hero-body"><div className="avatar">{hero.name?.slice(0,1)||"W"}</div><div className="hero-description"><div className="hero-state"><Dot on={genuine}/>{genuine?"POSTAĆ POŁĄCZONA":snapshot.demo?"TRYB DEMO":"OCZEKIWANIE NA POŁĄCZENIE"}</div><h2>{data?hero.name||"Nieznana postać":"Witaj w Azeroth"}</h2><p>{data?(hero.race||"Rasa")+"  •  "+(hero.class||"Klasa")+"  •  "+(hero.realm||"Realm"):"Uruchom WoW i podłącz addon WoWMCPData."}</p><div className="hero-details"><span><MapPin size={15}/>{data?.location?.zone||"Nieznana lokalizacja"}</span><span><Clock3 size={15}/>{snapshot.last_visual_read?"Odczyt: "+time(snapshot.last_visual_read):"Brak odczytu"}</span></div></div><div className="hero-level"><small>POZIOM</small><strong>{num(hero.level)}</strong></div></div><div className="hero-bottom"><span><ShieldCheck size={16}/>Tylko odczyt — bez sterowania postacią</span><button onClick={()=>go("character")}>Otwórz profil <ArrowRight size={16}/></button></div></section>
          <div className="stats"><Stat label="POZIOM POSTACI" value={num(hero.level)} detail={hero.class||"Nieznana klasa"} Icon={Swords} tone="mint"/><Stat label="ZDROWIE" value={hero.health_max?percentage(hero.health,hero.health_max)+"%":"—"} detail={hero.health_max?num(hero.health)+" / "+num(hero.health_max)+" HP":"Brak danych HP"} Icon={HeartPulse}/><Stat label="AKTYWNE ZADANIA" value={data?String(quests.length):"—"} detail="Dziennik questów" Icon={BookOpen} tone="blue"/><Stat label="DO ODDANIA" value={data?String(ready):"—"} detail="Ukończone zadania" Icon={CheckCircle2} tone="yellow"/></div>
          <div className="dashboard-grid"><div className="panel quests-preview"><Header title="Najbliższe zadania" subtitle="Aktualny dziennik" action={<button className="inline-action" onClick={()=>go("quests")}>Wszystkie <ArrowRight size={15}/></button>}/>{quests.length?quests.slice(0,5).map((q,i)=><QuestRow key={i} q={q}/>):<Empty Icon={BookOpen} title="Brak danych o zadaniach" body="Odczytaj postać, aby zobaczyć aktywne questy."/>}</div><div className="right-panels"><div className="panel"><Header title="Zasoby bohatera" subtitle="Aktualny stan postaci"/><Bar label="Punkty życia" value={hero.health} max={hero.health_max} color="rose"/><Bar label="Mana / energia" value={hero.power} max={hero.power_max} color="blue"/><Bar label="Doświadczenie" value={hero.xp} max={hero.xp_max} color="mint"/></div><div className="panel system-panel"><Header title="Status systemu"/><div className="system-detail"><span><Dot on={Boolean(snapshot.game?.running)}/>Proces WoW</span><b>{snapshot.game?.running?"Uruchomiony":"Nieaktywny"}</b></div><div className="system-detail"><span><Dot on={Boolean(snapshot.transport?.pipe)}/>Kanał DLL</span><b>{snapshot.transport?.pipe?"Aktywny":"Niedostępny"}</b></div><div className="system-detail"><span><Dot on={genuine}/>Odczyt postaci</span><b>{genuine?"Dostępny":"Brak danych"}</b></div></div></div></div>
        </div>}
        {page==="character"&&<div className="page"><div className="page-title"><div><span className="eyebrow">TWOJA POSTAĆ</span><h1>Profil bohatera</h1><p>Statystyki, zasoby i lokalizacja postaci.</p></div><button className="btn secondary" onClick={()=>void action("refresh")}><RefreshCcw size={16}/>Odczytaj ponownie</button></div>{!data?<div className="panel"><Empty title="Nie odczytano jeszcze postaci" body="Uruchom grę, a następnie wykonaj odczyt z addonu." Icon={ShieldCheck}/></div>:<><div className="profile-card"><div className="profile-avatar">{hero.name?.charAt(0)||"?"}</div><div><span className="eyebrow">AKTYWNA POSTAĆ</span><h2>{hero.name||"Nieznana postać"}</h2><p>{hero.race||"Rasa"} · {hero.class||"Klasa"} · {hero.realm||"Realm"}</p></div><div className="profile-level">LVL <b>{num(hero.level)}</b></div></div><div className="two-cols"><div className="panel"><Header title="Zasoby postaci" subtitle="Punkty życia, moc i doświadczenie"/><Bar label="Zdrowie" value={hero.health} max={hero.health_max} color="rose"/><Bar label="Mana / energia" value={hero.power} max={hero.power_max} color="blue"/><Bar label="Doświadczenie" value={hero.xp} max={hero.xp_max} color="mint"/></div><div className="panel"><Header title="Szczegóły"/><Detail label="Lokalizacja" value={data.location?.zone||"—"}/><Detail label="Podstrefa" value={data.location?.subzone||"—"}/><Detail label="Zadania aktywne" value={String(quests.length)}/><Detail label="Gotowe do oddania" value={String(ready)}/><Detail label="Złoto" value={String(Math.floor((hero.money_copper||0)/10000))+"g"}/></div></div></>}</div>}
        {page==="quests"&&<div className="page"><div className="page-title"><div><span className="eyebrow">DZIENNIK ZADAŃ</span><h1>Twoje questy</h1><p>Wyszukuj zadania i śledź ukończone cele.</p></div><span className="count-chip"><BookOpen size={17}/>{data?String(quests.length)+" zadań":"Brak odczytu"}</span></div><div className="filter-bar"><div className="search"><Search size={19}/><input placeholder="Szukaj po nazwie lub celu..." value={search} onChange={e=>setSearch(e.target.value)}/></div><div className="segments">{([["all","Wszystkie"],["ready","Gotowe"],["active","W toku"]] as const).map(([id,name])=><button key={id} className={questFilter===id?"active":""} onClick={()=>setQuestFilter(id)}>{name}</button>)}</div></div><div className="quest-count"><span><CheckCircle2 size={17}/>{ready} gotowych do oddania</span><span>{shown.length} wyświetlanych zadań</span></div>{shown.length?<div className="quest-list">{shown.map((q,i)=><div className="quest-card" key={i}><div className="quest-card-top"><span className="quest-card-icon">{questReady(q)?<CheckCircle2 size={19}/>:<BookOpen size={19}/>}</span><div><b>{q.title||"Bez nazwy"}</b><p>{q.level?"Poziom "+q.level+" • ":""}{questReady(q)?"Gotowe do oddania":"W trakcie"}</p></div><span className={cx("tag",questReady(q)&&"green")}>{questReady(q)?"GOTOWE":"W TOKU"}</span></div>{q.objectives&&q.objectives.length>0&&<div className="objectives">{q.objectives.map((o,j)=><div className={cx("objective",o.done&&"finished")} key={j}><span>{o.done?<Check size={14}/>:<span className="ring"/>}</span>{o.text||"Cel bez opisu"}</div>)}</div>}</div>)}</div>:<div className="panel"><Empty Icon={BookOpen} title="Brak zadań" body={quests.length?"Zmień filtr lub wyszukiwanie.":"Odczytaj postać, aby pobrać dziennik questów."}/></div>}</div>}
        {page==="inventory"&&<div className="page"><div className="page-title"><div><span className="eyebrow">PRZEDMIOTY</span><h1>Twój ekwipunek</h1><p>Wszystko, co masz na sobie i w torbach.</p></div><span className="count-chip"><Package size={17}/>{data?String(gear.length+bags.length)+" pozycji":"Brak danych"}</span></div><div className="two-cols"><div className="panel"><Header title="Wyposażenie" subtitle={gear.length+" przedmiotów"}/>{gear.length?gear.map((x,i)=><ItemRow key={i} item={x}/>):<Empty Icon={Package} title="Brak ekwipunku" body="Wczytaj dane z postaci."/ >}</div><div className="panel"><Header title="Zawartość toreb" subtitle={bags.length+" rodzajów przedmiotów"}/><div className="search compact"><Search size={17}/><input placeholder="Filtruj przedmioty..." value={itemFilter} onChange={e=>setItemFilter(e.target.value)}/></div>{shownItems.length?shownItems.map((x,i)=><ItemRow key={i} item={x}/>):<Empty Icon={Package} title="Nic tu nie ma" body="Brak danych lub wyników wyszukiwania."/ >}</div></div></div>}
        {page==="diagnostics"&&<div className="page"><div className="page-title"><div><span className="eyebrow">STAN TECHNICZNY</span><h1>Diagnostyka</h1><p>Podgląd źródeł, pakietów i stanu połączenia.</p></div><button className="btn secondary" onClick={()=>void refresh()}><RefreshCcw size={17}/>Odśwież</button></div><div className="stats"><Stat Icon={Database} label="ODEBRANE" value={String(snapshot.transport?.accepted_frames||0)} detail="Poprawne pakiety" tone="mint"/><Stat Icon={X} label="ODRZUCONE" value={String(snapshot.transport?.rejected_frames||0)} detail="Niepoprawne pakiety" tone="yellow"/><Stat Icon={Cpu} label="SEKWENCJA" value={String(snapshot.transport?.sequence??"—")} detail="Ostatnia odebrana"/><Stat Icon={Activity} label="WIEK DANYCH" value={snapshot.transport?.age_seconds!==undefined&&snapshot.transport.age_seconds!==null?snapshot.transport.age_seconds.toFixed(1)+" s":"—"} detail="Od ostatniego pakietu" tone="blue"/></div><div className="two-cols"><div className="panel"><Header title="Źródła danych"/><Detail label="Źródło" value={snapshot.source_label||"—"}/><Detail label="Wow.exe" value={snapshot.game?.running?"Uruchomiony":"Nie wykryto"}/><Detail label="Folder gry" value={snapshot.game?.installed?"Skonfigurowany":"Nie skonfigurowany"}/><Detail label="Named Pipe" value={snapshot.transport?.pipe?"Aktywny":"Nieaktywny"}/><Detail label="Odczyt wizualny" value={time(snapshot.last_visual_read)}/></div><div className="panel"><Header title="Terminal MCP" subtitle="Kanał lokalny"/><div className="terminal"><div><span>$</span> wow-mcp status</div><div><span>✓</span> pipe: {snapshot.transport?.pipe?"ready":"waiting"}</div><div><span>✓</span> data: {snapshot.available?"available":"not available"}</div><div><span>i</span> source: {snapshot.source||"none"}</div></div><p className="tiny-note">DLL nie jest obecnie podłączona do Lua gry. Unikaj modyfikacji klienta Warmane.</p></div></div>{snapshot.error&&<div className="notice">{snapshot.error}</div>}</div>}
        {page==="settings"&&<div className="page"><div className="page-title"><div><span className="eyebrow">KONFIGURACJA</span><h1>Ustawienia</h1><p>Połącz WoW z aplikacją i skonfiguruj MCP.</p></div></div><div className="settings-stack"><div className="panel"><Header title="Uruchamianie gry" subtitle="Jednym kliknięciem przygotuj addon i włącz WoW"/><div className="folder-row"><div className="folder-icon"><FolderOpen size={23}/></div><div><b>{snapshot.game?.directory?"WoW 3.3.5a":"Brak wskazanego folderu"}</b><span>{snapshot.game?.directory||"Wybierz katalog z Wow.exe"}</span></div><button className="btn secondary" onClick={()=>void selectFolder()}><FolderOpen size={16}/>Wybierz</button></div><div className="launch-settings-actions"><button className="btn primary" onClick={()=>void launchGame()} disabled={Boolean(loading)||snapshot.launch?.busy}><Play size={17}/>{snapshot.launch?.busy?"Przygotowywanie…":"Uruchom WoW z addonem"}</button><span className="launch-addon-state">{snapshot.game?.addon_installed?"Addon jest zainstalowany":"Addon zainstaluje się automatycznie"}</span></div>{snapshot.launch?.status&&snapshot.launch.status!=="idle"&&<p className={cx("launch-note",snapshot.launch.status==="error"&&"launch-error-text")}>{snapshot.launch.message}</p>}</div><div className="panel"><Header title="Źródła danych" subtitle="Aktualnie dostępne metody odczytu"/><div className="setting-option"><span className="option-icon"><Layers size={20}/></span><div><b>Addon WoWMCPData</b><p>Odczyt prawdziwych danych za pomocą paska wizualnego.</p></div><span className="tag green">DOSTĘPNY</span></div><div className="setting-option"><span className="option-icon blue"><Cpu size={20}/></span><div><b>DLL Native Bridge</b><p>Odbiornik jest uruchamiany automatycznie, ale DLL nie jest wstrzykiwana do klienta. Wymaga osobnego, dozwolonego środowiska testowego.</p></div><span className="tag">BETA</span></div></div><div className="panel"><Header title="Skalowanie interfejsu" subtitle="Dopasuj wielkość do ekranu i ustawień DPI Windows"/><div className="scale-controls"><button className="scale-step" aria-label="Zmniejsz skalę" disabled={uiScale<=SCALE_MIN} onClick={()=>setUiScale(z=>clampScale(z-SCALE_STEP))}>−</button><input aria-label="Skala interfejsu" type="range" min={SCALE_MIN} max={SCALE_MAX} step={SCALE_STEP} value={uiScale} onChange={e=>setUiScale(clampScale(Number(e.target.value)))}/><button className="scale-step" aria-label="Zwiększ skalę" disabled={uiScale>=SCALE_MAX} onClick={()=>setUiScale(z=>clampScale(z+SCALE_STEP))}>+</button><strong>{uiScale}%</strong><button className="scale-reset" onClick={()=>setUiScale(100)}>Resetuj</button></div><p className="setting-copy">Skala 80–140% jest zapamiętywana. Możesz też używać Ctrl + / Ctrl − / Ctrl 0.</p></div><div className="panel"><Header title="Przetestuj interfejs" subtitle="Podgląd bez konieczności uruchamiania WoW"/><p className="setting-copy">Wyświetlane będą wyłącznie przykładowe dane, wyraźnie oznaczone jako demonstracyjne.</p><button className="btn secondary" onClick={()=>void action("demo")}><Sparkles size={16}/>Włącz tryb demo</button></div><div className="panel"><Header title="Połączenie z ChatGPT" subtitle="Zmienne środowiskowe MCP"/><div className="code-copy">WOW_MCP_NATIVE_BRIDGE=1<br/>WOW_MCP_NATIVE_HUB=1<button onClick={async()=>{try{await navigator.clipboard.writeText("WOW_MCP_NATIVE_BRIDGE=1\nWOW_MCP_NATIVE_HUB=1");setMessage("Skopiowano konfigurację.");}catch{setMessage("Kopiowanie jest niedostępne.")}}}><Copy size={17}/></button></div></div></div></div>}
        <footer className="footer"><span>WoW MCP Control Center <i>·</i> Tauri Desktop</span><span>Dane gry pozostają lokalnie na Twoim komputerze</span></footer>
      </main>
    </div>
    {serviceError&&<div className="service-error"><WifiOff size={18}/><span>Trwa łączenie z lokalną usługą. {serviceError.length<120?serviceError:"Sprawdź uruchomienie aplikacji."}</span><button onClick={()=>setServiceError("")}><X size={17}/></button></div>}
    {message&&<div className="toast"><CheckCircle2 size={18}/><span>{message}</span><button onClick={()=>setMessage("")}><X size={17}/></button></div>}
  </div>;
}
function Detail({label,value}:{label:string;value:string}){return <div className="detail"><span>{label}</span><b>{value}</b></div>;}
