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


class Callbacks:
    """Akce z okna; applet si přepíše, co potřebuje. Výchozí = nic."""

    def refresh(self):
        pass

    def retry(self):
        self.refresh()

    def toggle_overdue(self):
        pass

    def toggle_no_date(self):
        pass

    def complete(self, entry, check):
        pass

    def open_task(self, entry):
        pass

    def add(self, date, day_box):
        """＋ u dne; day_box = svislý box dne (nadpis je na pozici 0) – rychlé zapsání (Task 7)."""
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


def _entry_row(entry, show_project, overdue, callbacks):
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
    if overdue and entry.get("date"):
        d = logic.parse_date(entry["date"])
        row.pack_start(_label(fmt.short_date(d), dim=True, name="vq-date"), False, False, 0)
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


def _header(title, callbacks):
    box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
    box.pack_start(_label(f"<b>{logic.escape(title)}</b>", markup=True, name="vq-header"),
                   True, True, 0)
    r = _flat_button("⟳", name="vq-refresh")
    r.set_tooltip_text(texts.REFRESH)
    r.connect("clicked", lambda _b: callbacks.refresh())
    box.pack_end(r, False, False, 0)
    return box


def _vbox():
    b = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
    b.set_border_width(6)
    return b


def build_agenda_box(agenda, settings, today, callbacks):
    """Strom widgetů okna z agendy {overdue, days, noDate, counts, top} a nastavení instance."""
    cb = callbacks or Callbacks()
    show_project = not settings.get("project")
    root = _vbox()
    root.pack_start(_header(settings.get("label") or "", cb), False, False, 0)

    overdue = agenda.get("overdue") or []
    if overdue:
        expanded = bool(settings.get("overdueExpanded"))
        text = texts.OVERDUE.format(n=len(overdue))
        root.pack_start(_section_toggle(
            f'<span foreground="{logic.ORANGE}">{logic.escape(text)}</span>',
            expanded, cb.toggle_overdue, "vq-overdue"), False, False, 0)
        if expanded:
            for e in overdue:
                root.pack_start(_entry_row(e, show_project, True, cb), False, False, 0)

    for day in agenda.get("days") or []:
        d = logic.parse_date(day["date"])
        day_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        day_box.set_name("vq-day")
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
                day_box.pack_start(_entry_row(e, show_project, False, cb), False, False, 0)
        else:
            empty = _label(texts.NO_TASKS, dim=True, name="vq-empty")
            empty.set_margin_start(24)
            day_box.pack_start(empty, False, False, 0)
        root.pack_start(day_box, False, False, 2)

    no_date = agenda.get("noDate") or []
    if no_date:
        expanded = bool(settings.get("noDateExpanded", True))
        root.pack_start(_section_toggle(f"<b>{logic.escape(texts.NO_DATE)}</b>", expanded,
                                        cb.toggle_no_date, "vq-nodate"), False, False, 0)
        if expanded:
            for e in no_date:
                root.pack_start(_entry_row(e, show_project, False, cb), False, False, 0)

    apply_font(root, settings.get("fontSize", 11))
    return root


def build_message_box(settings, message, callbacks, retry=False):
    """Obsah okna pro chybu nebo načítání: záhlaví + zpráva (+ Zkusit znovu)."""
    cb = callbacks or Callbacks()
    root = _vbox()
    root.pack_start(_header(settings.get("label") or "", cb), False, False, 0)
    msg = _label(message, xalign=0.5, name="vq-message")
    msg.set_margin_top(12)
    msg.set_margin_bottom(12)
    root.pack_start(msg, False, False, 0)
    if retry:
        b = Gtk.Button(label=texts.RETRY)
        b.set_name("vq-retry")
        b.connect("clicked", lambda _b: cb.retry())
        root.pack_start(b, False, False, 0)
    apply_font(root, settings.get("fontSize", 11))
    return root


def apply_font(widget, size_pt):
    """Velikost písma pro celý strom widgetu (CSS na každý widget, i vnitřní)."""
    provider = Gtk.CssProvider()
    provider.load_from_data(f"* {{ font-size: {float(size_pt):g}pt; }}".encode())

    def walk(w):
        w.get_style_context().add_provider(provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        if isinstance(w, Gtk.Container):
            w.forall(walk)
    walk(widget)


def iter_widgets(widget):
    """Všechny widgety stromu (pro testy a hledání)."""
    yield widget
    if isinstance(widget, Gtk.Container):
        for child in widget.get_children():
            yield from iter_widgets(child)


class AgendaPopup:
    """Okno bez dekorace nad appletem; zavře se Esc nebo ztrátou fokusu."""

    def __init__(self, applet):
        self.applet = applet
        self._hidden_at = 0.0
        self.keep_open = False  # Task 7: při psaní do řádku zapsání okno nezavírat
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

    def is_visible(self):
        return self.window.get_visible()

    def recently_hidden(self):
        return time.monotonic() - self._hidden_at < REOPEN_GUARD

    def set_content(self, widget):
        """Vymění obsah; zachová posun a okno znovu umístí podle nové výšky."""
        adj = self.scrolled.get_vadjustment()
        pos = adj.get_value() if adj else 0
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

    def _monitor(self):
        display = self.applet.get_display()
        gdk_win = self.applet.get_window()
        mon = display.get_monitor_at_window(gdk_win) if gdk_win else display.get_primary_monitor()
        if mon is None:
            mon = display.get_monitor(0)
        return mon.get_workarea()

    def _place(self):
        area = self._monitor()
        self.scrolled.set_max_content_height(max(100, int(area.height * 0.7)))
        _min, nat = self.window.get_preferred_size()
        gdk_win = self.applet.get_window()
        if gdk_win is not None:
            _ok, ox, oy = gdk_win.get_origin()
            alloc = self.applet.get_allocation()
            rect = (ox, oy, alloc.width, alloc.height)
        else:
            rect = (area.x, area.y + area.height, 0, 0)
        x, y = logic.popup_position(self._orient(), rect, (nat.width, nat.height),
                                    (area.x, area.y, area.width, area.height))
        self.window.move(x, y)

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
        self.window.present_with_time(Gtk.get_current_event_time())

    def hide(self):
        if self.is_visible():
            self.window.hide()
            self._hidden_at = time.monotonic()

    def _on_key(self, _w, event):
        if event.keyval == Gdk.KEY_Escape:
            self.hide()
            return True
        return False

    def _on_focus_out(self, _w, _e):
        if not self.keep_open:
            self.hide()
        return False


def today():
    return datetime.date.today()
