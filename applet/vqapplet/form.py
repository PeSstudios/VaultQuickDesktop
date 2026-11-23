# Formulář úkolu (samostatné okno): název, termín + čas, stav, priorita, projekt, text.
# Tlačítka Uložit, Hotovo, Smazat, Otevřít v Obsidianu; konflikt a neuložené změny přes dialogy.
import datetime
import os

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, Gtk, Pango  # noqa: E402

from . import formlogic, logic, popup, store, texts  # noqa: E402
from .work import run_async, spawn  # noqa: E402

NONE_ID = ""  # id položky „žádný“ v seznamu projektů
OTHER_ID = "vq:other"  # položka „Jiná stránka…“ (výběr libovolné stránky z vaultu)
FORM_MARGIN = 16  # okraj formuláře vlevo a vpravo

_open = {}  # cesta úkolu → otevřený formulář (jeden formulář na úkol)


def open_form(client, path, on_done, font_size=None, vault=None):
    """Otevře (nebo vyzvedne už otevřený) formulář úkolu; po uložení, odškrtnutí nebo smazání
    zavolá on_done() (= obnovit všechny instance)."""
    f = _open.get(path)
    if f is not None and not f.closed:
        f.window.present()
        return f
    f = TaskForm(client, path, on_done, font_size=font_size, vault=vault)
    _open[path] = f
    f.show()
    f.load()
    return f


def add_page(combo, name):
    """Přidá stránku do seznamu projektů (není-li tam) před „Jiná stránka…“, která zůstává poslední."""
    ids = [row[1] for row in combo.get_model()]
    if name not in ids:
        combo.insert(len(ids) - 1 if OTHER_ID in ids else len(ids), name, name)


def run_page_chooser(parent, vault):
    """Dialog výběru .md stránky z vaultu (projekt); vrátí cestu nebo None (zrušeno)."""
    c = Gtk.FileChooserDialog(title=texts.PROJECT_CHOOSER_TITLE, transient_for=parent,
                              action=Gtk.FileChooserAction.OPEN, modal=True)
    c.add_button(texts.CANCEL, Gtk.ResponseType.CANCEL)
    c.add_button(texts.ICON_CHOOSER_OPEN, Gtk.ResponseType.ACCEPT)
    c.set_default_response(Gtk.ResponseType.ACCEPT)
    c.set_keep_above(True)
    flt = Gtk.FileFilter()
    flt.set_name(texts.PROJECT_FILTER)
    flt.add_pattern("*.[mM][dD]")
    c.add_filter(flt)
    if vault and os.path.isdir(vault):
        c.set_current_folder(vault)
    response = c.run()
    filename = c.get_filename() if response == Gtk.ResponseType.ACCEPT else None
    c.destroy()
    return filename


class TaskForm:
    def __init__(self, client, path, on_done, font_size=None, vault=None):
        self.client = client
        self.path = path
        self.on_done = on_done or (lambda: None)
        self.vault = vault
        self.closed = False
        self.task = None
        self.mtime = None
        self.initial = None
        self.meta = None
        self.date = None
        self._filling = False
        self._month_nav = False

        w = Gtk.Window(title=texts.FORM_TITLE.format(title=path))
        w.set_default_size(480, 440)
        w.set_position(Gtk.WindowPosition.CENTER)
        w.connect("delete-event", self._on_delete)
        w.connect("key-press-event", self._on_key)
        if font_size:
            popup.apply_font(w, font_size)
        self.window = w

        # záhlaví jako v okně agendy: název úkolu na podkladu, vpravo otevření v Obsidianu
        popup.install_css()
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        header.set_name("vq-header-row")
        self.header = Gtk.Label(xalign=0)
        self.header.set_name("vq-header")
        self.header.set_ellipsize(Pango.EllipsizeMode.END)
        self.header.set_margin_start(6)
        self._set_header(path)
        header.pack_start(self.header, True, True, 0)
        self.obsidian = popup._flat_button(popup.target_icon("file"),
                                           name="vq-form-obsidian")
        self.obsidian.set_tooltip_text(texts.OPEN_OBSIDIAN)
        self.obsidian.connect("clicked", lambda _b: self.open_obsidian())
        header.pack_end(self.obsidian, False, False, 0)

        grid = Gtk.Grid(row_spacing=10, column_spacing=16)
        grid.set_margin_start(FORM_MARGIN)
        grid.set_margin_end(FORM_MARGIN)
        grid.set_margin_top(14)
        grid.set_margin_bottom(10)
        self.title = Gtk.Entry()
        self.title.set_hexpand(True)
        self.title.connect("changed", lambda e: self._set_header(e.get_text()))

        # Termín: kalendář v rozbalovacím tlačítku + čas + Bez termínu
        self.calendar = Gtk.Calendar()
        self.calendar.connect("month-changed", self._on_month_changed)
        self.calendar.connect("day-selected", self._on_day_selected)
        self.calendar.connect("day-selected-double-click", lambda _c: self.date_popover.popdown())
        self.date_popover = Gtk.Popover()
        self.date_popover.add(self.calendar)
        self.calendar.show()
        self.date_button = Gtk.MenuButton(label=texts.FORM_NO_DATE)
        self.date_button.set_popover(self.date_popover)
        self.date_button.set_name("vq-form-date")
        self.time = Gtk.Entry()
        self.time.set_width_chars(6)
        self.time.set_placeholder_text(texts.FORM_TIME_PLACEHOLDER)
        self.no_date = Gtk.Button(label=texts.FORM_NO_DATE)
        self.no_date.connect("clicked", lambda _b: self._set_date(None))
        date_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        date_row.pack_start(self.date_button, True, True, 0)
        date_row.pack_start(self.time, False, False, 0)
        date_row.pack_start(self.no_date, False, False, 0)

        self.status = Gtk.ComboBoxText()
        self.priority = Gtk.ComboBoxText()
        self.project = Gtk.ComboBoxText()
        self.project.connect("changed", self._on_project_changed)
        self._project_prev = NONE_ID  # výběr před „Jiná stránka…“ (zrušení výběru ho vrátí)
        self.recurrence = Gtk.Label(xalign=0)
        self.recurrence.set_no_show_all(True)

        self.body = Gtk.TextView()
        self.body.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.body.set_left_margin(4)
        self.body.set_right_margin(4)
        body_scroll = Gtk.ScrolledWindow()
        body_scroll.set_shadow_type(Gtk.ShadowType.IN)
        body_scroll.set_vexpand(True)
        body_scroll.set_min_content_height(120)
        body_scroll.add(self.body)

        rows = ((texts.FORM_NAME, self.title), (texts.FORM_DATE, date_row),
                (texts.FORM_STATUS, self.status), (texts.FORM_PRIORITY, self.priority),
                (texts.FORM_PROJECT, self.project), (None, self.recurrence),
                (texts.FORM_TEXT, body_scroll))
        for i, (name, widget) in enumerate(rows):
            if name:
                lab = Gtk.Label(label=name, xalign=0, yalign=0 if widget is body_scroll else 0.5)
                lab.get_style_context().add_class("dim-label")
                if widget is body_scroll:
                    lab.set_margin_top(4)
                grid.attach(lab, 0, i, 1, 1)
            widget.set_hexpand(True)
            grid.attach(widget, 1, i, 1, 1)

        buttons = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        buttons.get_style_context().add_class("vq-section")
        buttons.set_margin_start(FORM_MARGIN)
        buttons.set_margin_end(FORM_MARGIN)
        buttons.set_margin_bottom(12)
        self.delete = Gtk.Button(label=texts.FORM_DELETE)
        self.delete.connect("clicked", lambda _b: self.ask_delete())
        self.done = Gtk.Button(label=texts.FORM_DONE)
        self.done.connect("clicked", lambda _b: self.complete())
        self.save_button = Gtk.Button(label=texts.SAVE)
        self.save_button.get_style_context().add_class("suggested-action")
        self.save_button.connect("clicked", lambda _b: self.save())
        buttons.pack_start(self.delete, False, False, 0)
        buttons.pack_end(self.save_button, False, False, 0)
        buttons.pack_end(self.done, False, False, 0)
        for b in (self.delete, self.done, self.save_button):
            b.set_margin_top(8)

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        root.pack_start(header, False, False, 0)
        root.pack_start(grid, True, True, 0)
        root.pack_start(buttons, False, False, 0)
        w.add(root)
        self._set_busy(True)

    # --- okno ---
    def _set_header(self, title):
        self.header.set_markup(
            f'<span size="larger"><b>{logic.escape(title.strip() or self.path)}</b></span>')

    def show(self):
        self.window.show_all()
        self.window.present()

    def close(self):
        if self.closed:
            return
        self.closed = True
        if _open.get(self.path) is self:
            del _open[self.path]
        self.window.destroy()

    def _on_delete(self, *_a):
        self.request_close()
        return True  # okno se zavře samo v request_close

    def _on_key(self, _w, event):
        if event.keyval == Gdk.KEY_Escape:
            self.request_close()
            return True
        return False

    def request_close(self):
        """Zavření; s neuloženými změnami se zeptá Uložit / Zahodit / Zrušit."""
        if not self.dirty():
            self.close()
            return

        def answer(r):
            if r == "save":
                self.save()
            elif r == "discard":
                self.close()
        self.ask(texts.UNSAVED_TEXT, "", ((texts.CANCEL, "cancel"), (texts.FORM_DISCARD, "discard"),
                                          (texts.SAVE, "save")), answer, default="save")

    def _set_busy(self, busy):
        loaded = self.task is not None
        for wdg in (self.title, self.date_button, self.time, self.no_date, self.status,
                    self.priority, self.project, self.body, self.delete, self.save_button):
            wdg.set_sensitive(loaded and not busy)
        self.done.set_sensitive(loaded and not busy and bool(self.task.get("completable", True)))
        self.obsidian.set_sensitive(True)
        if loaded and not busy:
            self.time.set_sensitive(self.date is not None)

    # --- dialogy (testy si je přepíšou) ---
    def ask(self, text, detail, buttons, on_answer, default):
        """Dialog s tlačítky [(popisek, odpověď)]; on_answer(odpověď) – zavření křížkem = None.
        default = odpověď na Enter (výslovně – Enter nesmí nic nevratně přepsat)."""
        d = Gtk.MessageDialog(transient_for=self.window, modal=True,
                              message_type=Gtk.MessageType.QUESTION,
                              buttons=Gtk.ButtonsType.NONE, text=text)
        if detail:
            d.format_secondary_text(detail)
        for i, (label, _key) in enumerate(buttons):
            d.add_button(label, i)
        keys = [key for _label, key in buttons]
        d.set_default_response(keys.index(default))

        def response(dlg, r):
            dlg.destroy()
            on_answer(buttons[r][1] if 0 <= r < len(buttons) else None)
        d.connect("response", response)
        d.show()

    def message(self, text, detail=""):
        d = Gtk.MessageDialog(transient_for=None if self.closed else self.window, modal=False,
                              message_type=Gtk.MessageType.WARNING,
                              buttons=Gtk.ButtonsType.OK, text=text)
        if detail:
            d.format_secondary_text(detail)
        d.connect("response", lambda dlg, _r: dlg.destroy())
        d.show()

    # --- načtení ---
    def load(self):
        self._set_busy(True)
        meta = self.meta

        def work():
            got = self.client.request("get", path=self.path)
            return got, meta if meta is not None else self.client.request("meta")
        run_async(work, self._loaded)

    def _loaded(self, result, error):
        if self.closed:
            return
        if error is not None:
            self.close()  # nejdřív zavřít, zpráva pak nemá mrtvého rodiče
            if error.code == "missing":
                self.message(texts.TASK_MISSING)
                self.on_done()
            else:
                self.message(texts.LOAD_FAILED, texts.ERROR_DETAIL.format(code=error.code))
            return
        got, meta = result
        self.meta = meta
        self.fill(got, meta)

    def fill(self, got, meta):
        """Naplní pole z odpovědi `get` a seznamy z `meta`."""
        task = got["task"]
        self.task, self.mtime = task, got.get("mtime")
        self.initial = formlogic.initial_values(task, got.get("body"))
        v = self.initial
        self._filling = True
        try:
            self.window.set_title(texts.FORM_TITLE.format(title=v["title"]))
            self.title.set_text(v["title"])
            self.time.set_text(v["time"])
            self._set_date(v["date"])
            self._fill_combo(self.status, formlogic.with_current(meta.get("statuses"), v["status"]),
                             v["status"])
            self._fill_combo(self.priority,
                             formlogic.with_current(meta.get("priorities"), v["priority"]),
                             v["priority"])
            self.project.remove_all()
            self.project.append(NONE_ID, texts.FORM_PROJECT_NONE)
            for p in formlogic.with_current(meta.get("projects"), v["project"]):
                self.project.append(p, p)
            self.project.append(OTHER_ID, texts.FORM_PROJECT_OTHER)
            self.project.set_active_id(v["project"] or NONE_ID)
            self._project_prev = self.project.get_active_id()
            rec = formlogic.recurrence_label(task.get("recurrence"))
            self.recurrence.set_text(rec or "")
            self.recurrence.set_visible(bool(rec))
            self.body.get_buffer().set_text(v["body"])
        finally:
            self._filling = False
        self._set_busy(False)

    # --- projekt: libovolná stránka vaultu ---
    def _vault(self):
        return self.vault or store.load_config()["vault"]

    def _on_project_changed(self, combo):
        if self._filling:
            return
        active = combo.get_active_id()
        if active != OTHER_ID:
            self._project_prev = active
            return
        # „Jiná stránka…“: výběr souboru; zrušení vrátí předchozí projekt
        filename = self._run_project_chooser()
        if filename is None or not self.choose_project_file(filename):
            self._select_project(self._project_prev)

    def _select_project(self, pid):
        self._filling = True
        try:
            self.project.set_active_id(pid or NONE_ID)
        finally:
            self._filling = False
        self._project_prev = self.project.get_active_id()

    def choose_project_file(self, filename):
        """Vybraný soubor → projekt (název stránky bez .md), musí to být .md ve vaultu.
        Vrátí True, když se projekt změnil."""
        name, err = formlogic.page_from_file(self._vault(), filename)
        if err is not None:
            self.message(*err)
            return False
        add_page(self.project, name)
        self._select_project(name)
        return True

    def _run_project_chooser(self):
        return run_page_chooser(self.window, self._vault())

    @staticmethod
    def _fill_combo(combo, items, active):
        combo.remove_all()
        for it in items:
            combo.append(it, it)
        if active:
            combo.set_active_id(active)

    # --- termín ---
    def _set_date(self, iso):
        self.date = iso
        self.date_button.set_label(formlogic.date_label(iso))
        self.time.set_sensitive(iso is not None and self.task is not None)
        d = datetime.date.fromisoformat(iso) if iso else datetime.date.today()
        was = self._filling
        self._filling = True  # výběr v kalendáři z kódu není volba uživatele
        try:
            self.calendar.select_month(d.month - 1, d.year)
            self.calendar.select_day(d.day)
        finally:
            self._filling = was

    def _on_month_changed(self, _c):
        if not self._filling:
            self._month_nav = True  # následující day-selected je jen listování měsíci

    def _on_day_selected(self, cal):
        if self._filling:
            return
        if self._month_nav:
            self._month_nav = False
            return
        y, m, d = cal.get_date()
        self._set_date(datetime.date(y, m + 1, d).isoformat())

    # --- hodnoty ---
    def values(self):
        buf = self.body.get_buffer()
        return {
            "title": self.title.get_text(),
            "date": self.date,
            "time": self.time.get_text(),
            "status": self.status.get_active_id() or "",
            "priority": self.priority.get_active_id() or "",
            "project": self.project.get_active_id() or None,
            "body": buf.get_text(buf.get_start_iter(), buf.get_end_iter(), True),
        }

    def dirty(self):
        return self.task is not None and formlogic.is_dirty(self.initial, self.values())

    def _changes(self, task):
        try:
            return formlogic.build_changes(task, self.values())
        except ValueError:
            self.message(texts.BAD_TIME.format(time=self.time.get_text().strip()))
            self.time.grab_focus()
            return None

    # --- akce ---
    def save(self, then=None):
        """Uloží formulář; then(changes) po úspěchu (jinak formulář zavře)."""
        changes = self._changes(self.task)
        if changes is None:
            return
        self._set_busy(True)
        mtime = self.mtime
        run_async(lambda: self.client.request("save", path=self.path, mtime=mtime,
                                              changes=changes),
                  lambda r, e: self._saved(changes, then, r, e))

    def _saved(self, changes, then, result, error):
        if self.closed:
            return
        if error is None:
            self.mtime = result.get("mtime")
            self.on_done()
            if then:
                then(changes)
            else:
                self.close()
            return
        self._set_busy(False)
        if error.code == "conflict":
            self._conflict(then)
        elif error.code == "missing":
            self.close()
            self.message(texts.TASK_MISSING)
            self.on_done()
        else:
            self.message(texts.SAVE_FAILED, texts.ERROR_DETAIL.format(code=error.code))

    def _conflict(self, then):
        def answer(r):
            if r == "overwrite":
                self.overwrite(then)
            elif r == "reload":
                self.load()
        self.ask(texts.CONFLICT_TEXT, texts.CONFLICT_DETAIL,
                 ((texts.CANCEL, "cancel"), (texts.CONFLICT_RELOAD, "reload"),
                  (texts.CONFLICT_OVERWRITE, "overwrite")), answer, default="reload")

    def overwrite(self, then=None):
        """Přepsat: znovu `get` pro nové mtime (a aktuální ostatní projekty, kontexty), pak `save`."""
        self._set_busy(True)

        def got(result, error):
            if self.closed:
                return
            if error is not None:
                self._saved(None, then, None, error)
                return
            self.task, self.mtime = result["task"], result.get("mtime")
            self._set_busy(False)
            self.save(then)
        run_async(lambda: self.client.request("get", path=self.path), got)

    def complete(self):
        """Hotovo; neuložené změny se nejdřív uloží (expected = termín po uložení)."""
        if self.dirty():
            self.save(then=lambda changes: self._complete(changes["date"]))
        else:
            self._complete(self.task.get("date"))

    def _complete(self, expected):
        self._set_busy(True)
        today = datetime.date.today().isoformat()

        def done(_r, error):
            if self.closed:
                return
            self.on_done()
            if error is None:
                self.close()
                return
            if error.code == "stale":
                self.message(texts.TASK_STALE)
                self.load()
            elif error.code == "missing":
                self.close()
                self.message(texts.TASK_MISSING)
            else:
                self._set_busy(False)
                self.message(texts.COMPLETE_FAILED, texts.ERROR_DETAIL.format(code=error.code))
                self.load()  # po případném uložení je nové mtime
        run_async(lambda: self.client.request("complete", path=self.path, expected=expected,
                                              today=today), done)

    def ask_delete(self):
        title = self.title.get_text().strip() or (self.task or {}).get("title", "")

        def answer(r):
            if r == "delete":
                self.archive()
        self.ask(texts.DELETE_CONFIRM.format(title=title), texts.DELETE_DETAIL,
                 ((texts.CANCEL, "cancel"), (texts.FORM_DELETE, "delete")), answer,
                 default="cancel")

    def archive(self):
        self._set_busy(True)

        def done(_r, error):
            if self.closed:
                return
            if error is None or error.code == "missing":
                self.on_done()
                self.close()
                return
            self._set_busy(False)
            self.message(texts.DELETE_FAILED, texts.ERROR_DETAIL.format(code=error.code))
        run_async(lambda: self.client.request("archive", path=self.path), done)

    def open_obsidian(self):
        vault = self.vault or store.load_config()["vault"]
        spawn(["xdg-open", formlogic.obsidian_file_url(vault, self.path)])
