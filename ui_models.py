"""Pure data formatting for the desktop UI. No game or Tk dependencies."""
import datetime
import time


def time_label(timestamp):
    if not isinstance(timestamp, (float, int)):
        return "—"
    try:
        return datetime.datetime.fromtimestamp(timestamp).strftime("%H:%M:%S")
    except (OSError, OverflowError, ValueError):
        return "—"


def as_mapping(value):
    return value if isinstance(value, dict) else {}


def as_list(value):
    return value if isinstance(value, list) else []


def is_demo(snapshot):
    data = as_mapping(as_mapping(snapshot).get("data"))
    character = as_mapping(data.get("character"))
    return character.get("name") == "Demo" and snapshot.get("source") != "WoW addon visual data strip"


def source_label(snapshot):
    snapshot = as_mapping(snapshot)
    if not snapshot.get("available"):
        return "Brak świeżych danych"
    if snapshot.get("source") == "WoW addon visual data strip":
        return "Addon WoW · odczyt na żądanie"
    if is_demo(snapshot):
        return "DEMO · dane testowe, nie z gry"
    return "DLL · dane natywne (eksperymentalne)"


def select_snapshot(native_snapshot, visual_snapshot, now=None, visual_ttl=60):
    """Prefer actual visual game data over native demo; never show old data as live."""
    now = time.time() if now is None else now
    native = as_mapping(native_snapshot)
    visual = as_mapping(visual_snapshot)
    vdata = as_mapping(visual.get("data"))
    captured = vdata.get("captured_at", visual.get("captured_at"))
    visual_valid = (
        visual.get("available") is True and
        isinstance(captured, (float, int)) and
        0 <= now - captured <= visual_ttl
    )
    if visual_valid and (not native.get("available") or is_demo(native)):
        return visual
    if native.get("available"):
        return native
    if visual_valid:
        return visual
    return {"available": False, "source": "none", "data": None}


def metrics(snapshot):
    data = as_mapping(as_mapping(snapshot).get("data"))
    character = as_mapping(data.get("character"))
    location = as_mapping(data.get("location"))
    quests = [q for q in as_list(data.get("quests")) if isinstance(q, dict)]
    return {
        "name": character.get("name") or "Nieznana postać",
        "realm": character.get("realm") or "Nieznany serwer",
        "class": character.get("class") or "—",
        "race": character.get("race") or "—",
        "level": character.get("level", "—"),
        "health": character.get("health", 0),
        "health_max": character.get("health_max", 0),
        "power": character.get("power", 0),
        "power_max": character.get("power_max", 0),
        "xp": character.get("xp", 0),
        "xp_max": character.get("xp_max", 0),
        "money_copper": character.get("money_copper", 0),
        "zone": location.get("zone") or "Nieznana lokalizacja",
        "subzone": location.get("subzone") or "",
        "quest_count": len(quests),
        "ready_count": sum(bool(q.get("ready_to_turn_in")) for q in quests),
        "quests": quests,
        "bags": as_list(data.get("bags")),
        "equipment": as_list(data.get("equipment")),
    }


def ratio(value, maximum):
    try:
        value = float(value)
        maximum = float(maximum)
        return max(0.0, min(1.0, value / maximum)) if maximum > 0 else 0.0
    except (ValueError, TypeError, ZeroDivisionError):
        return 0.0


def gold(copper):
    try:
        amount = max(0, int(copper))
    except (ValueError, TypeError):
        amount = 0
    return f"{amount // 10000}g {(amount % 10000) // 100}s {amount % 100}c"


def quest_view(quests, query="", mode="Wszystkie"):
    needle = (query or "").strip().casefold()
    filtered = []
    for q in as_list(quests):
        if not isinstance(q, dict):
            continue
        ready = bool(q.get("ready_to_turn_in"))
        if mode == "Gotowe" and not ready:
            continue
        if mode == "W toku" and ready:
            continue
        title = str(q.get("title") or "Bez nazwy")
        objectives = [o for o in as_list(q.get("objectives")) if isinstance(o, dict)]
        if needle and needle not in (title + " " + " ".join(str(o.get("text", "")) for o in objectives)).casefold():
            continue
        filtered.append({"title": title, "ready": ready,
                         "level": q.get("level"), "objectives": objectives,
                         "complete": bool(q.get("complete"))})
    return sorted(filtered, key=lambda row: (not row["ready"], row["title"].casefold()))
