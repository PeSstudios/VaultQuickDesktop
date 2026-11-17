# Čistá logika formuláře úkolu a rychlého zapsání (bez GTK, testovatelná).
import re
import urllib.parse
import os

from . import fmt, logic, texts

_TIME = re.compile(r"^(\d{1,2})[:.](\d{2})$")


def parse_time(text):
    """Text pole Čas → "HH:mm", prázdný → None; neplatný čas → ValueError."""
    s = (text or "").strip()
    if not s:
        return None
    m = _TIME.match(s)
    if not m:
        raise ValueError(s)
    h, mi = int(m.group(1)), int(m.group(2))
    if h > 23 or mi > 59:
        raise ValueError(s)
    return f"{h:02d}:{mi:02d}"


def first_project(projects):
    """Projekt, který ukazuje rozbalovací seznam (první projekt úkolu), nebo None."""
    return projects[0] if projects else None


def merge_projects(projects, selected):
    """Výběr v seznamu nahradí první projekt úkolu, ostatní zůstanou za ním;
    „žádný“ (None) odebere jen první projekt."""
    rest = list(projects[1:]) if projects else []
    if not selected:
        return rest
    return [selected] + [p for p in rest if p.lower() != selected.lower()]


def with_current(options, current):
    """Položky rozbalovacího seznamu; hodnota úkolu, která v seznamu chybí, se přidá na začátek."""
    out = list(options or [])
    if current and current not in out:
        out.insert(0, current)
    return out


def initial_values(task, body):
    """Hodnoty polí formuláře z odpovědi `get` (porovnávají se s nimi neuložené změny)."""
    date = task.get("date")
    return {
        "title": task.get("title") or "",
        "date": date,
        "time": (task.get("time") or "") if date else "",
        "status": task.get("status") or "",
        "priority": task.get("priority") or "",
        "project": first_project(task.get("projects") or []),
        "body": body or "",
    }


def is_dirty(initial, current):
    """Liší se formulář od načteného úkolu? (Mezery kolem názvu a času se nepočítají.)"""
    def norm(v):
        v = dict(v)
        v["title"] = (v.get("title") or "").strip()
        v["time"] = (v.get("time") or "").strip() if v.get("date") else ""
        v["project"] = v.get("project") or None
        return v
    return norm(initial) != norm(current)


def build_changes(task, values):
    """`changes` pro příkaz `save` z hodnot formuláře; neplatný čas → ValueError.
    Kontexty se předají beze změny; bez termínu = bez času."""
    date = values.get("date") or None
    time = parse_time(values.get("time")) if date else None
    title = (values.get("title") or "").strip() or task.get("title") or ""
    return {
        "title": title,
        "date": date,
        "time": time,
        "status": values.get("status") or task.get("status"),
        "priority": values.get("priority") or task.get("priority"),
        "projects": merge_projects(task.get("projects") or [], values.get("project")),
        "contexts": list(task.get("contexts") or []),
        "body": values.get("body") or "",
    }


def date_label(date_iso):
    """Popisek tlačítka Termín: „st 18. 11. 2026“, bez data „Bez termínu“."""
    d = logic.parse_date(date_iso)
    if d is None:
        return texts.NO_DATE
    return f"{fmt.DNY[d.weekday()]} {fmt.short_date(d)} {d.year}"


def recurrence_label(recurrence):
    return f"{texts.RECURRING} {recurrence}" if recurrence else None


def quick_create_params(text, date, project):
    """Parametry `create` z řádku rychlého zapsání; prázdný text → None (zrušit)."""
    t = (text or "").strip()
    if not t:
        return None
    return {"text": t, "date": date, "project": project or None}


def create_warning(params, result):
    """Upozornění po `create`: projekt byl požadovaný, ale vqd úkol uložil bez něj
    (stránka projektu ve vaultu neexistuje – stejně jako v telefonu). Jinak None."""
    wanted = (params or {}).get("project")
    if not wanted or (result or {}).get("project"):
        return None
    return texts.CREATE_NO_PROJECT.format(name=wanted)


def obsidian_file_url(vault_path, path):
    """Odkaz na soubor úkolu v Obsidianu (cesta ve vaultu bez přípony .md)."""
    vault = os.path.basename(os.path.normpath(vault_path))
    file = path[:-3] if path.lower().endswith(".md") else path
    q = urllib.parse.quote
    return f"obsidian://open?vault={q(vault, safe='')}&file={q(file, safe='')}"
