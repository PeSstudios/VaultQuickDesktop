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
    """Cesta k pomocníku: $VQD_BIN, nainstalovaný, nebo sestavený v repu vedle appletu."""
    env = os.environ if env is None else env
    home = os.path.expanduser("~") if home is None else home
    if env.get("VQD_BIN"):
        return [env["VQD_BIN"]]
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


def escape(text):
    return (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;").replace("'", "&#39;"))


def bar_markup(label, counts):
    """Pango markup štítku na liště: `popisek N` + oranžové `⚠M`; 0 a 0 → ztlumené."""
    text, overdue, dimmed = fmt.bar_label(label, counts)
    m = escape(text)
    if overdue:
        m += f' <span foreground="{ORANGE}">{escape(overdue)}</span>'
    if dimmed:
        m = f'<span alpha="50%">{m}</span>'
    return m


def bar_tooltip(label, top):
    return "\n".join(top) if top else label


def error_bar(code):
    """Štítek a tooltip pro chybu pomocníka."""
    if code == "vault":
        return texts.BAR_VAULT_ERROR, texts.VAULT_UNAVAILABLE
    return texts.BAR_HELPER_DOWN, texts.HELPER_DOWN


def error_code(error):
    return getattr(error, "code", None) if error is not None else None


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
