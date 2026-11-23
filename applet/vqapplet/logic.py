# Čistá logika appletu bez GTK (testovatelná): umístění okna, půlnoc, cesty, odkazy, markup lišty.
import ast
import datetime
import os
import re
import urllib.parse

from . import fmt, texts

ORANGE = "#e67e22"


def parse_object_ids(output):
    """Výstup `gsettings get org.mate.panel object-id-list` → seznam id, nebo None, nejde-li číst."""
    s = (output or "").strip()
    if s.startswith("@as "):
        s = s[4:].strip()
    try:
        value = ast.literal_eval(s)
    except (ValueError, SyntaxError):
        return None
    if not isinstance(value, (list, tuple)) or not all(isinstance(v, str) for v in value):
        return None
    return list(value)


_OBJ = re.compile(r"/objects/([^/]+)/")


def object_id_of(key):
    """Id objektu panelu z klíče instance (`/org/mate/panel/objects/object_8/prefs/` → `object_8`)."""
    m = _OBJ.search(key if key.endswith("/") else key + "/")
    return m.group(1) if m else None


def live_keys(stored_keys, object_ids):
    """Uložené klíče instancí, jejichž objekt je ještě na panelu."""
    ids = set(object_ids)
    return {k for k in stored_keys if object_id_of(k) in ids}


def seconds_until_midnight(now, slack=5):
    """Sekundy do příští půlnoci (+ malá rezerva, aby už byl nový den)."""
    tomorrow = (now + datetime.timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0)
    return max(1, int((tomorrow - now).total_seconds()) + slack)


def vqd_argv(applet_dir, env=None, home=None, exists=os.path.exists):
    """Cesta k pomocníku: $VQD_BIN, vedle appletu (balíček .deb i install.sh), nainstalovaný
    v ~/.local, nebo sestavený v repu."""
    env = os.environ if env is None else env
    home = os.path.expanduser("~") if home is None else home
    if env.get("VQD_BIN"):
        return [env["VQD_BIN"]]
    sibling = os.path.normpath(os.path.join(applet_dir, "../vqd/bin/vqd"))
    if exists(sibling):
        return [sibling]
    installed = os.path.join(home, ".local/share/vaultquick-desktop/vqd/bin/vqd")
    if exists(installed):
        return [installed]
    return [os.path.normpath(os.path.join(applet_dir, "../vqd/build/install/vqd/bin/vqd"))]


def toggle_target(instances, label):
    """Index instance pro zkratku: "" → instance Vše (project null), jinak první s popiskem
    (bez ohledu na velikost písmen), jinak první na liště; žádná instance → None."""
    if not instances:
        return None
    wanted = (label or "").strip().casefold()
    if not wanted:
        for i, s in enumerate(instances):
            if s.get("project") is None:
                return i
        return 0
    for i, s in enumerate(instances):
        if str(s.get("label", "")).strip().casefold() == wanted:
            return i
    return 0


def obsidian_url(vault_path, project):
    """Odkaz na stránku projektu v Obsidianu; instance Vše → stránka TaskNotes."""
    vault = os.path.basename(os.path.normpath(vault_path))
    page = project if project else "TaskNotes"
    q = urllib.parse.quote
    return f"obsidian://open?vault={q(vault, safe='')}&file={q(page, safe='')}"


def obsidian_file_url(vault_path, relative):
    """Odkaz na libovolný soubor vaultu (cesta relativně k vaultu, s příponou)."""
    vault = os.path.basename(os.path.normpath(vault_path))
    q = urllib.parse.quote
    return f"obsidian://open?vault={q(vault, safe='')}&file={q(relative, safe='')}"


def project_folder(vault_path, project):
    """Složka se stránkou projektu (absolutní); Vše nebo nenalezená stránka → kořen vaultu.
    Hledá jako pomocník: <projekt>.md kdekoli ve vaultu (bez skrytých složek), bez ohledu
    na velikost písmen, při shodě první podle abecedy cesty."""
    wanted = (project or "").strip().casefold()
    if not wanted:
        return vault_path
    found = []
    for dirpath, dirs, files in os.walk(vault_path):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        rel = os.path.relpath(dirpath, vault_path)
        for f in files:
            if f.startswith(".") or not f.endswith(".md"):
                continue
            if f[:-3].casefold() == wanted:
                found.append(f if rel == "." else f"{rel}/{f}")
    if not found:
        return vault_path
    return os.path.join(vault_path, os.path.dirname(min(found)))


def open_target(settings, vault_path, kind):
    """Cíl řádku v okně podle projektu: kind "file" → obsidian URL stránky projektu
    (Vše → TaskNotes), kind "folder" → složka se stránkou projektu (Vše → kořen vaultu)."""
    if kind == "folder":
        return os.path.normpath(project_folder(vault_path, settings.get("project")))
    return obsidian_url(vault_path, settings.get("project"))


def open_icons(kind):
    """Názvy ikon řádku v okně podle pořadí přednosti (použije se první z tématu)."""
    if kind == "folder":
        return ("folder", "system-file-manager", "folder-symbolic")
    return ("obsidian", "md.obsidian.Obsidian", "text-x-generic", "text-x-generic-symbolic")


def open_target_name(settings, kind):
    """Krátký popis cíle (tooltip)."""
    project = settings.get("project")
    if kind == "folder":
        return texts.OPEN_PROJECT_FOLDER.format(project=project) if project else texts.OPEN_VAULT_ROOT
    return texts.OPEN_PROJECT_PAGE.format(project=project) if project else texts.OPEN_TASKNOTES_PAGE


def open_description(settings, kind):
    """Tooltip řádku Otevřít v průzkumníku / v Obsidianu."""
    tip = texts.OPEN_TIP_FOLDER if kind == "folder" else texts.OPEN_TIP_FILE
    return tip.format(target=open_target_name(settings, kind))


def escape(text):
    return (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;").replace("'", "&#39;"))


def bar_markup(label, counts, with_label=True, with_counts=True):
    """Pango markup štítku na liště: `popisek N` + oranžové `⚠M`; 0 a 0 → ztlumené.
    with_label=False (vedle ikony) → jen počty. with_counts=False (předvolba Zobrazovat počet
    úkolů) → bez čísel i bez ⚠: jen popisek (bez popisku prázdné – jen ikona)."""
    if not with_counts:
        if not (with_label and label):
            return ""
        dimmed = counts.get("today", 0) == 0 and counts.get("overdue", 0) == 0
        m = escape(label)
        return f'<span alpha="50%">{m}</span>' if dimmed else m
    text, overdue, dimmed = fmt.bar_label(label if with_label else None, counts)
    m = escape(text)
    if overdue:
        m += f' <span foreground="{ORANGE}">{escape(overdue)}</span>'
    if dimmed:
        m = f'<span alpha="50%">{m}</span>'
    return m


def bar_tooltip(label, top):
    """Tooltip lišty: vždy začíná popiskem (u ikony je popisek jen tady), pak první úkoly."""
    return "\n".join([label] + list(top or []))


# --- ikona na liště ---
IMAGE_EXTENSIONS = ("png", "jpg", "jpeg", "gif", "webp", "svg", "bmp")


def is_image(name):
    """Má soubor příponu obrázku (bez ohledu na velikost písmen)?"""
    base = os.path.basename(name or "")
    _root, ext = os.path.splitext(base)
    return ext[1:].lower() in IMAGE_EXTENSIONS


def icon_source(settings):
    """Odkud vzít ikonu instance: ("auto", None) = ze stránky projektu, ("none", None) = bez ikony,
    ("path", cesta) = vybraný obrázek (cesta relativně k vaultu)."""
    icon = settings.get("icon")
    if not isinstance(icon, str) or not icon.strip() or icon == "auto":
        return "auto", None
    if icon == "none":
        return "none", None
    return "path", icon


def vault_relative(vault_root, chosen_abs):
    """Absolutní cesta vybraného souboru → cesta relativně k vaultu (s `/`), nebo None,
    je-li soubor mimo vault. Symlinky se řeší přes realpath (vault i soubor)."""
    root = os.path.realpath(vault_root)
    path = os.path.realpath(chosen_abs)
    try:
        if os.path.commonpath([root, path]) != root or path == root:
            return None
    except ValueError:
        return None
    return os.path.relpath(path, root).replace(os.sep, "/")


def icon_abs(vault_root, relative):
    """Absolutní cesta ikony z cesty relativně k vaultu; žádná cesta → None."""
    if not relative:
        return None
    return os.path.join(vault_root, relative)


ICON_MARGIN = 4
ICON_MIN = 12


def icon_box(panel_size, vertical):
    """(šířka, výška) pro GdkPixbuf.new_from_file_at_scale se zachováním poměru stran
    (-1 = podle poměru). Obrázek se neořezává: vodorovná lišta omezuje výšku, svislá šířku."""
    n = max(int(panel_size) - ICON_MARGIN, ICON_MIN)
    return (n, -1) if vertical else (-1, n)


def show_label(settings, has_icon):
    """Ukázat popisek na liště? Bez ikony vždy, s ikonou jen se zaškrtnutým „Zobrazit i popisek“."""
    return True if not has_icon else bool(settings.get("showLabel"))


def error_bar(code):
    """Štítek a tooltip pro chybu pomocníka."""
    if code == "vault":
        return texts.BAR_VAULT_ERROR, texts.VAULT_UNAVAILABLE
    return texts.BAR_HELPER_DOWN, texts.HELPER_DOWN


def error_code(error):
    return getattr(error, "code", None) if error is not None else None


def empty_agenda():
    """Agenda instance s počtem dní 0: žádné úkoly (ani zpožděné, pozdější, bez termínu)."""
    return {"overdue": [], "days": [], "later": [], "noDate": [], "counts": {}, "top": []}


def shows_tasks(settings):
    """Počet dní 0 v předvolbách = okno bez úkolů (jen záhlaví a řádky Otevřít…)."""
    try:
        return int(settings.get("days", 7)) > 0
    except (TypeError, ValueError):
        return True


def open_kinds(settings):
    """Zaškrtnuté řádky Otevřít… v pořadí okna: "folder" (průzkumník), "file" (Obsidian)."""
    kinds = []
    if settings.get("showOpenFolder", True):
        kinds.append("folder")
    if settings.get("showOpenObsidian", True):
        kinds.append("file")
    return kinds


def direct_open(settings):
    """Klik na applet rovnou otevře cíl (místo okna), když je počet dní 0 a zaškrtnutý
    je jen jeden řádek Otevřít…: vrátí "folder" / "file", jinak None."""
    kinds = open_kinds(settings)
    if shows_tasks(settings) or len(kinds) != 1:
        return None
    return kinds[0]


def refresh_changed(old_agenda, old_error, new_agenda, new_error):
    """Má se po obnovení přestavět lišta a okno? Stejná agenda i stav chyby → ne
    (okno se nepřestaví pod kurzorem a klik trefí úkol, na který uživatel míří)."""
    return old_agenda != new_agenda or error_code(old_error) != error_code(new_error)


def complete_error_message(code):
    """Hláška po neúspěšném odškrtnutí, nebo None: `stale` jen obnoví agendu,
    `failed` otevře formulář úkolu."""
    if code is None or code in ("stale", "failed"):
        return None
    return {
        "not_running": texts.COMPLETE_HELPER_DOWN,
        "timeout": texts.COMPLETE_TIMEOUT,
        "vault": texts.COMPLETE_VAULT,
        "missing": texts.COMPLETE_MISSING,
    }.get(code, texts.COMPLETE_FAILED)


def popup_position(orient, applet_rect, size, monitor):
    """Levý horní roh okna u appletu. orient = up|down|left|right (směr, kam se okno otevírá),
    applet_rect = (x, y, w, h) na obrazovce, size = (w, h) okna, monitor = (x, y, w, h)."""
    ax, ay, aw, ah = applet_rect
    w, h = size
    mx, my, mw, mh = monitor
    if orient == "up":
        x, y = ax, ay - h
    elif orient == "down":
        x, y = ax, ay + ah
    elif orient == "left":
        x, y = ax - w, ay
    else:
        x, y = ax + aw, ay
    x = max(mx, min(x, mx + mw - w))
    y = max(my, min(y, my + mh - h))
    return x, y


def default_no_date(project):
    return "all" if project else "inProgress"


def default_label(project):
    return project if project else texts.ALL


def parse_date(s):
    return datetime.date.fromisoformat(s) if s else None


def font_css(size_pt):
    """Třída a CSS velikosti písma: třída se dá na okno (obsah) a platí i pro widgety
    přidané později (řádek rychlého zapsání)."""
    size = f"{float(size_pt):g}"
    cls = "vq-font-" + size.replace(".", "_")
    return cls, f".{cls}, .{cls} * {{ font-size: {size}pt; }}"


def looks_like_vault(path):
    """Složka je vault Obsidianu (obsahuje .obsidian)."""
    return bool(path) and os.path.isdir(os.path.join(path, ".obsidian"))
