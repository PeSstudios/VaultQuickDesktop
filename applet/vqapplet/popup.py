# Vyskakovací okno s agendou. Obsah se staví z obyčejného slovníku agendy (protokol `agenda`),
# takže jde sestavit a otestovat i bez appletu.
import datetime
import time

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, GLib, Gtk, Pango  # noqa: E402

from . import fmt, logic, texts  # noqa: E402

# Po zavření okna ztrátou fokusu (klik na applet) se okno hned znovu neotevře.
REOPEN_GUARD = 0.3
NO_DATE_BOX = "vq-nodate-box"  # svislý box sekce Bez termínu (nadpis na pozici 0)
SIDE_MARGIN = 12  # okraj obsahu vlevo a vpravo
# Kolikrát nejvýš okno po jedné změně obsahu znovu přesunout, když nesedí u appletu
# (správce oken by mohl přesun odmítat – pak se s ním nepřetahovat donekonečna).
MAX_FIXES = 5
VERIFY_DELAYS = (80, 250, 600)  # ms po změně obsahu – kontrola skutečné polohy okna

CSS = """
#vq-header-row {
  background-color: alpha(@theme_selected_bg_color, 0.35);
  border-bottom: 1px solid alpha(@theme_selected_bg_color, 0.9);
  padding: 3px 4px 3px 6px;
}
#vq-open-folder, #vq-open-obsidian { padding: 1px 4px 1px 0; }
#vq-overdue, #vq-nodate, #vq-later { padding-left: 0; padding-right: 4px; }
.vq-section { border-top: 1px solid alpha(@theme_fg_color, 0.10); padding-top: 4px; }
"""


def _server_time(window):
    try:
        gi.require_version("GdkX11", "3.0")
        from gi.repository import GdkX11
        gdk_window = window.get_window()
        if gdk_window is not None:
            return GdkX11.x11_get_server_time(gdk_window)
    except (ImportError, ValueError, AttributeError, TypeError):
        pass
    return Gdk.CURRENT_TIME


class Callbacks:
    """Akce z okna; applet si přepíše, co potřebuje. Výchozí = nic."""

    def refresh(self):
        pass

    def retry(self):
        self.refresh()

    def choose_vault(self):
        """Tlačítko Vybrat vault… ve zprávě o nenalezeném vaultu."""
        pass

    def toggle_overdue(self):
        pass

    def toggle_no_date(self):
        pass

    def toggle_later(self):
        pass

    def open_folder(self):
        """Řádek Otevřít v průzkumníku (složka z předvoleb, jinak kořen vaultu)."""
        pass

    def open_obsidian(self):
        """Řádek Otevřít v Obsidianu (soubor z předvoleb, jinak stránka projektu)."""
        pass

    def complete(self, entry, check):
        pass

    def open_task(self, entry):
        pass

    def add(self, date, day_box):
        """＋ u dne (date = ISO datum) nebo u Bez termínu (date = None); day_box = svislý box
        dne / sekce (nadpis je na pozici 0) – sem se vloží řádek rychlého zapsání."""
        pass


def _label(text, markup=False, xalign=0.0, dim=False, name=None):
    lab = Gtk.Label()
    if markup:
        lab.set_markup(text)
    else:
        lab.set_text(text)
    lab.set_xalign(xalign)
    if dim:
        lab.get_style_context().add_class("dim-label")
    if name:
        lab.set_name(name)
    return lab


def _flat_button(child, name=None):
    b = Gtk.Button()
    b.set_relief(Gtk.ReliefStyle.NONE)
    b.set_can_focus(False)
    if isinstance(child, str):
        child = _label(child, xalign=0.5)
    b.add(child)
    if name:
        b.set_name(name)
    return b


def _section_toggle(markup, expanded, on_click, name):
    """Řádek „⚠ N zpožděné ▸/▾“ nebo „Bez termínu ▸/▾“ jako plochý přepínač."""
    box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
    box.pack_start(_label(markup, markup=True), True, True, 0)
    box.pack_end(_label(texts.EXPANDED if expanded else texts.COLLAPSED), False, False, 0)
    b = _flat_button(box, name=name)
    b.connect("clicked", lambda _b: on_click())
    return b


def _entry_row(entry, show_project, date_fmt, callbacks):
    """Řádek úkolu; date_fmt = funkce data (zpožděné, Další dny), None = bez data."""
    row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
    row.set_name("vq-row")
    if entry.get("checkable"):
        check = Gtk.CheckButton()
        check.set_name("vq-check")
        check.set_can_focus(False)

        def toggled(c):
            if c.get_active():
                c.set_sensitive(False)
                callbacks.complete(entry, c)
        check.connect("toggled", toggled)
        row.pack_start(check, False, False, 0)
    else:
        rec = _label(texts.RECURRING, xalign=0.5, name="vq-recurring")
        rec.set_size_request(20, -1)
        row.pack_start(rec, False, False, 0)
    if date_fmt and entry.get("date"):
        d = logic.parse_date(entry["date"])
        row.pack_start(_label(date_fmt(d), dim=True, name="vq-date"), False, False, 0)
    if entry.get("time"):
        row.pack_start(_label(entry["time"], name="vq-time"), False, False, 0)
    title = _label(entry.get("title") or "", name="vq-title")
    title.set_ellipsize(Pango.EllipsizeMode.END)
    title.set_max_width_chars(40)
    tb = _flat_button(title, name="vq-title-button")
    tb.set_tooltip_text(entry.get("title") or "")
    tb.connect("clicked", lambda _b: callbacks.open_task(entry))
    row.pack_start(tb, True, True, 0)
    if show_project and entry.get("projects"):
        row.pack_end(_label(", ".join(entry["projects"]), dim=True, name="vq-project"),
                     False, False, 0)
    return row


HEADER_ICON_SIZE = 16


def target_icon(kind):
    """Ikona cíle: Obsidian (kind "file") nebo složka (kind "folder", správce souborů)."""
    names = logic.open_icons(kind)
    theme = Gtk.IconTheme.get_default()
    icon = next((n for n in names if theme is not None and theme.has_icon(n)), names[-1])
    img = Gtk.Image.new_from_icon_name(icon, Gtk.IconSize.MENU)
    img.set_pixel_size(HEADER_ICON_SIZE)
    img.set_name("vq-open-icon")
    return img


def _header(settings, callbacks):
    """Záhlaví přes celou šířku okna s podkladem: název a ⟳."""
    box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
    box.set_name("vq-header-row")
    title = settings.get("label") or ""
    name = _label(f'<span size="larger"><b>{logic.escape(title)}</b></span>', markup=True,
                  name="vq-header")
    name.set_ellipsize(Pango.EllipsizeMode.END)
    name.set_margin_start(6)
    box.pack_start(name, True, True, 0)
    r = _flat_button("⟳", name="vq-refresh")
    r.set_tooltip_text(texts.REFRESH)
    r.connect("clicked", lambda _b: callbacks.refresh())
    box.pack_end(r, False, False, 0)
    return box


def _open_row(settings, kind, text, on_click, name):
    """Řádek pod záhlavím: ikona + Otevřít v průzkumníku / v Obsidianu (tooltip = cíl)."""
    inner = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    inner.pack_start(target_icon(kind), False, False, 0)
    inner.pack_start(_label(text), False, False, 0)
    b = _flat_button(inner, name=name)
    b.set_tooltip_text(logic.open_description(settings, kind))
    b.connect("clicked", lambda _b: on_click())
    return b


def _open_rows(settings, callbacks):
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
    box.set_name("vq-open-rows")
    box.pack_start(_open_row(settings, "folder", texts.OPEN_FILE_MANAGER,
                             callbacks.open_folder, "vq-open-folder"), False, False, 0)
    box.pack_start(_open_row(settings, "file", texts.OPEN_OBSIDIAN,
                             callbacks.open_obsidian, "vq-open-obsidian"), False, False, 0)
    return box


_css_screens = set()


def install_css():
    """Vzhled okna (záhlaví, sekce) – jednou pro obrazovku."""
    screen = Gdk.Screen.get_default()
    if screen is None or hash(screen) in _css_screens:
        return
    provider = Gtk.CssProvider()
    provider.load_from_data(CSS.encode())
    Gtk.StyleContext.add_provider_for_screen(screen, provider,
                                             Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
    _css_screens.add(hash(screen))


def _frame(settings, callbacks, open_rows=True):
    """(root, body): root = záhlaví + body; body = obsah s okraji vlevo i vpravo,
    nahoře řádky Otevřít v průzkumníku / v Obsidianu (open_rows=False → bez nich)."""
    install_css()
    root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
    root.pack_start(_header(settings, callbacks), False, False, 0)
    body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
    body.set_margin_start(SIDE_MARGIN)
    body.set_margin_end(SIDE_MARGIN)
    body.set_margin_top(6)
    body.set_margin_bottom(8)
    if open_rows:
        body.pack_start(_open_rows(settings, callbacks), False, False, 0)
    root.pack_start(body, True, True, 0)
    return root, body


def _section(name=None):
    """Svislý box sekce (den, Další dny, Bez termínu) s jemnou čarou nahoře."""
    b = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
    b.get_style_context().add_class("vq-section")
    b.set_name(name or "vq-section")
    return b


def build_agenda_box(agenda, settings, today, callbacks):
    """Strom widgetů okna z agendy {overdue, days, noDate, counts, top} a nastavení instance.
    Dny podle předvoleb, úkoly s pozdějším termínem (agenda["later"]) ve sbalitelné sekci Další dny."""
    cb = callbacks or Callbacks()
    show_project = not settings.get("project")
    root, body = _frame(settings, cb)
    if not logic.shows_tasks(settings):
        apply_font(root, settings.get("fontSize", 11))
        return root  # počet dní 0 → žádné úkoly ani sekce

    overdue = agenda.get("overdue") or []
    if overdue:
        expanded = bool(settings.get("overdueExpanded"))
        text = texts.OVERDUE.format(n=len(overdue))
        body.pack_start(_section_toggle(
            f'<span foreground="{logic.ORANGE}">{logic.escape(text)}</span>',
            expanded, cb.toggle_overdue, "vq-overdue"), False, False, 0)
        if expanded:
            for e in overdue:
                body.pack_start(_entry_row(e, show_project, fmt.short_date, cb), False, False, 0)

    for day in agenda.get("days") or []:
        d = logic.parse_date(day["date"])
        day_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        day_box.set_name("vq-day")
        day_box.get_style_context().add_class("vq-section")
        head = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        head.pack_start(_label(f"<b>{logic.escape(fmt.day_heading(d, today))}</b>", markup=True,
                               name="vq-day-heading"), True, True, 0)
        add = _flat_button(texts.ADD, name="vq-add")
        add.connect("clicked", lambda _b, date=day["date"], box=day_box: cb.add(date, box))
        head.pack_end(add, False, False, 0)
        day_box.pack_start(head, False, False, 0)
        entries = day.get("entries") or []
        if entries:
            for e in entries:
                day_box.pack_start(_entry_row(e, show_project, None, cb), False, False, 0)
        else:
            day_box.pack_start(_empty_label(), False, False, 0)
        body.pack_start(day_box, False, False, 2)

    later = agenda.get("later") or []
    if later:
        expanded = bool(settings.get("laterExpanded", True))
        later_box = _section("vq-later-box")
        title = texts.LATER_COUNT.format(n=len(later))
        later_box.pack_start(_section_toggle(f"<b>{logic.escape(title)}</b>", expanded,
                                             cb.toggle_later, "vq-later"), False, False, 0)
        if expanded:
            for e in later:
                later_box.pack_start(
                    _entry_row(e, show_project, lambda d: fmt.later_date(d, today), cb),
                    False, False, 0)
        body.pack_start(later_box, False, False, 2)

    no_date = agenda.get("noDate") or []
    # sekce se ukazuje i prázdná (kvůli ＋), pokud ji předvolby nevypínají
    if no_date or settings.get("noDate") != "none":
        expanded = bool(settings.get("noDateExpanded", True))
        nd_box = _section(NO_DATE_BOX)
        head = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        head.pack_start(_section_toggle(f"<b>{logic.escape(texts.NO_DATE)}</b>", expanded,
                                        cb.toggle_no_date, "vq-nodate"), True, True, 0)
        add = _flat_button(texts.ADD, name="vq-nodate-add")
        add.set_tooltip_text(texts.ADD_NO_DATE)
        add.connect("clicked", lambda _b, box=nd_box: cb.add(None, box))
        head.pack_end(add, False, False, 0)
        nd_box.pack_start(head, False, False, 0)
        if expanded:
            for e in no_date:
                nd_box.pack_start(_entry_row(e, show_project, None, cb), False, False, 0)
        body.pack_start(nd_box, False, False, 2)

    apply_font(root, settings.get("fontSize", 11))
    return root


def build_message_box(settings, message, callbacks, retry=False, choose_vault=False):
    """Obsah okna pro chybu nebo načítání: záhlaví + zpráva (+ Zkusit znovu / Vybrat vault…)."""
    cb = callbacks or Callbacks()
    root, body = _frame(settings, cb, open_rows=not choose_vault)  # bez vaultu není co otevřít
    msg = _label(message, xalign=0.5, name="vq-message")
    msg.set_justify(Gtk.Justification.CENTER)
    msg.set_margin_top(12)
    msg.set_margin_bottom(12)
    body.pack_start(msg, False, False, 0)
    if retry:
        b = Gtk.Button(label=texts.RETRY)
        b.set_name("vq-retry")
        b.connect("clicked", lambda _b: cb.retry())
        body.pack_start(b, False, False, 0)
    if choose_vault:
        b = Gtk.Button(label=texts.CHOOSE_VAULT)
        b.set_name("vq-choose-vault")
        b.connect("clicked", lambda _b: cb.choose_vault())
        body.pack_start(b, False, False, 0)
    apply_font(root, settings.get("fontSize", 11))
    return root


def _empty_label():
    empty = _label(texts.NO_TASKS, dim=True, name="vq-empty")
    empty.set_margin_start(24)
    return empty


_font_classes = set()  # třídy velikosti písma, pro které už je CSS na obrazovce


def apply_font(widget, size_pt):
    """Velikost písma pro widget a vše uvnitř – i pro widgety přidané později (řádek
    rychlého zapsání): třída na widgetu + CSS pro obrazovku, jednou pro každou velikost."""
    cls, css = logic.font_css(size_pt)
    if cls not in _font_classes:
        screen = Gdk.Screen.get_default()
        if screen is not None:
            provider = Gtk.CssProvider()
            provider.load_from_data(css.encode())
            Gtk.StyleContext.add_provider_for_screen(
                screen, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
            _font_classes.add(cls)
    ctx = widget.get_style_context()
    for c in ctx.list_classes():
        if c.startswith("vq-font-"):
            ctx.remove_class(c)
    ctx.add_class(cls)


def add_quick_row(day_box, on_submit, on_cancel):
    """Pod nadpis dne (pozice 0 v day_box) vloží řádek rychlého zapsání.
    Enter → on_submit(text) (prázdný text → on_cancel()). Vrátí Gtk.Entry."""
    e = Gtk.Entry()
    e.set_name("vq-quick")
    e.set_placeholder_text(texts.QUICK_PLACEHOLDER)
    e.set_margin_start(24)

    def activate(entry):
        text = entry.get_text()
        if text.strip():
            on_submit(text)
        else:
            on_cancel()
    e.connect("activate", activate)
    day_box.pack_start(e, False, False, 0)
    day_box.reorder_child(e, 1)
    e.show()
    return e


def iter_widgets(widget):
    """Všechny widgety stromu (pro testy a hledání)."""
    yield widget
    if isinstance(widget, Gtk.Container):
        for child in widget.get_children():
            yield from iter_widgets(child)


def find_named(widget, name):
    """První widget stromu se jménem name, nebo None."""
    for w in iter_widgets(widget):
        if w.get_name() == name:
            return w
    return None


class AgendaPopup:
    """Okno bez dekorace nad appletem; zavře se Esc nebo ztrátou fokusu."""

    def __init__(self, applet):
        self.applet = applet
        self._hidden_at = 0.0
        self.keep_open = False  # rozepsaný řádek zapsání: okno nezavírat, obsah nepřestavovat
        self.quick = None  # Gtk.Entry rychlého zapsání, je-li otevřený
        self._quick_cancel = None  # zrušení rozepsaného řádku (Esc, prázdný Enter)
        w = Gtk.Window(type=Gtk.WindowType.TOPLEVEL)
        w.set_decorated(False)
        w.set_resizable(False)
        w.set_skip_taskbar_hint(True)
        w.set_skip_pager_hint(True)
        w.set_keep_above(True)
        w.set_type_hint(Gdk.WindowTypeHint.UTILITY)
        w.stick()
        w.connect("key-press-event", self._on_key)
        w.connect("focus-out-event", self._on_focus_out)
        w.connect("delete-event", lambda *_a: self.hide() or True)
        # Skutečná velikost okna se změní až po přestavbě obsahu (např. sbalení sekce) a správce
        # oken může přesun a změnu velikosti zpracovat zvlášť – okno pak zůstane viset na staré
        # pozici. Proto se po každé změně ověří skutečná geometrie okna na X serveru.
        w.connect("size-allocate", lambda *_a: self._schedule_verify())
        w.connect("configure-event", self._on_configure)
        frame = Gtk.Frame()
        frame.set_shadow_type(Gtk.ShadowType.OUT)
        self.scrolled = Gtk.ScrolledWindow()
        self.scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.scrolled.set_propagate_natural_height(True)
        self.scrolled.set_propagate_natural_width(True)
        self.scrolled.set_min_content_width(280)
        frame.add(self.scrolled)
        w.add(frame)
        self.window = w
        self._content = None
        self._fixes = 0  # opravné přesuny od poslední změny obsahu
        self._verify_pending = False

    def is_visible(self):
        return self.window.get_visible()

    def recently_hidden(self):
        return time.monotonic() - self._hidden_at < REOPEN_GUARD

    def set_content(self, widget):
        """Vymění obsah; zachová posun a okno znovu umístí podle nové výšky."""
        adj = self.scrolled.get_vadjustment()
        pos = adj.get_value() if adj else 0
        # řádek zapsání zanikne se starým obsahem
        self.quick, self.keep_open, self._quick_cancel = None, False, None
        if self._content is not None:
            self.scrolled.remove(self._content)
            self._content.destroy()
        self._content = widget
        self.scrolled.add(widget)
        widget.show_all()
        if self.is_visible():
            self.window.resize(1, 1)
            self._place()
            GLib.idle_add(lambda: adj.set_value(pos) and False)
            self._verify_later()

    def _monitor(self):
        display = self.applet.get_display()
        gdk_win = self.applet.get_window()
        mon = display.get_monitor_at_window(gdk_win) if gdk_win else display.get_primary_monitor()
        if mon is None:
            mon = display.get_monitor(0)
        return mon.get_workarea()

    def _target(self, size):
        """Kam patří levý horní roh okna velikosti size."""
        area = self._monitor()
        gdk_win = self.applet.get_window()
        if gdk_win is not None:
            _ok, ox, oy = gdk_win.get_origin()
            alloc = self.applet.get_allocation()
            rect = (ox, oy, alloc.width, alloc.height)
        else:
            rect = (area.x, area.y + area.height, 0, 0)
        return logic.popup_position(self._orient(), rect, size,
                                    (area.x, area.y, area.width, area.height))

    def _place(self):
        """Umístí okno k appletu podle přirozené velikosti (odhad před změnou velikosti)."""
        area = self._monitor()
        self.scrolled.set_max_content_height(max(100, int(area.height * 0.7)))
        _min, nat = self.window.get_preferred_size()
        self.window.move(*self._target((nat.width, nat.height)))

    def _verify_later(self):
        """Po změně obsahu: několik kontrol se zpožděním (správce oken odpovídá asynchronně)."""
        self._fixes = 0
        for ms in VERIFY_DELAYS:
            GLib.timeout_add(ms, lambda: self.verify() and False)

    def _schedule_verify(self):
        if not self._verify_pending:
            self._verify_pending = True
            GLib.idle_add(self._idle_verify)

    def _idle_verify(self):
        self._verify_pending = False
        self.verify()
        return False

    def _on_configure(self, _w, _event):
        self._schedule_verify()
        return False

    def verify(self):
        """Porovná skutečnou polohu a velikost okna (z X serveru, ne odhad GTK) s místem
        u appletu a případně okno přesune. Vrátí True, když okno sedí."""
        gw = self.window.get_window()
        if not self.is_visible() or gw is None:
            return True
        size = (gw.get_width(), gw.get_height())
        want = self._target(size)
        _ok, x, y = gw.get_origin()
        if (x, y) == tuple(want):
            return True
        if self._fixes < MAX_FIXES:
            self._fixes += 1
            self.window.move(*want)
        return False

    def _orient(self):
        try:
            from gi.repository import MatePanelApplet
            o = self.applet.get_orient()
            return {MatePanelApplet.AppletOrient.UP: "up",
                    MatePanelApplet.AppletOrient.DOWN: "down",
                    MatePanelApplet.AppletOrient.LEFT: "left",
                    MatePanelApplet.AppletOrient.RIGHT: "right"}.get(o, "up")
        except Exception:
            return "up"

    def show(self):
        self._place()
        self.window.show_all()
        self._place()
        self._verify_later()
        # Bez události (volání z D-Bus / zkratky) vezmeme čas X serveru, aby okno dostalo fokus.
        self.window.present_with_time(Gtk.get_current_event_time() or _server_time(self.window))

    def start_quick(self, day_box, on_submit, on_cancel):
        """Otevře řádek rychlého zapsání pod nadpisem dne (jiný rozepsaný zavře)."""
        self.end_quick()

        def cancel():
            self.end_quick()
            on_cancel()
        self.quick = add_quick_row(day_box, on_submit, cancel)
        self._quick_cancel = cancel
        self.keep_open = True
        self.quick.grab_focus()
        return self.quick

    def end_quick(self):
        q, self.quick = self.quick, None
        self.keep_open = False
        self._quick_cancel = None
        if q is not None:
            q.destroy()

    def hide(self):
        self.end_quick()
        if self.is_visible():
            self.window.hide()
            self._hidden_at = time.monotonic()

    def _on_key(self, _w, event):
        if event.keyval == Gdk.KEY_Escape:
            if self._quick_cancel is not None:  # Esc nejdřív zruší rozepsaný řádek
                self._quick_cancel()
            else:
                self.hide()
            return True
        return False

    def _on_focus_out(self, _w, _e):
        if not self.keep_open:
            self.hide()
        return False


def today():
    return datetime.date.today()
