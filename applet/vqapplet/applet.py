# Applet na liště MATE: štítek s počty, kontextové menu, předvolby a vyskakovací agenda.
# Jeden proces pro všechny instance; jeden sdílený klient pomocníka vqd.
import datetime
import os
import subprocess
import threading
import warnings

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("MatePanelApplet", "4.0")
from gi.repository import Gio, GLib, Gtk, MatePanelApplet  # noqa: E402

from . import form, formlogic, logic, popup, prefs, store, texts  # noqa: E402
from .client import Client  # noqa: E402
from .work import run_async, spawn as _spawn  # noqa: E402

FACTORY_ID = "VaultQuickTasksFactory"
APPLET_ID = "VaultQuickTasks"
APPLET_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # desktop/applet
REFRESH_SECONDS = 60

APPLETS = []  # živé instance TaskApplet (pro D-Bus Toggle)

_client = None
_client_lock = threading.Lock()  # klienta si můžou poprvé vyžádat dvě vlákna naráz
_instances = None
_timers_started = False

MENU_XML = """
<menuitem name="VqPrefs" action="VqPrefs" />
<menuitem name="VqRefresh" action="VqRefresh" />
<menuitem name="VqObsidian" action="VqObsidian" />
"""


def client():
    global _client
    with _client_lock:
        if _client is None:
            _client = Client(logic.vqd_argv(APPLET_DIR))
        return _client


def instances():
    """Nastavení instancí; při prvním načtení smaže instance, které už nejsou na panelu."""
    global _instances
    if _instances is None:
        _instances = store.Instances()
        _prune(_instances)
    return _instances


def _prune(inst):
    try:
        out = subprocess.run(["gsettings", "get", "org.mate.panel", "object-id-list"],
                             capture_output=True, text=True, timeout=5).stdout
    except (OSError, subprocess.SubprocessError):
        return
    ids = logic.parse_object_ids(out)
    if ids is None:
        return  # seznam nejde přečíst → raději nic nemazat
    inst.prune(logic.live_keys(inst.keys(), ids))


def refresh_all():
    for a in list(APPLETS):
        a.refresh()


BUS_NAME = "cz.pesstudios.VaultQuickDesktop"
OBJECT_PATH = "/cz/pesstudios/VaultQuickDesktop"
DBUS_XML = """
<node>
  <interface name="cz.pesstudios.VaultQuickDesktop">
    <method name="Toggle"><arg type="s" name="label" direction="in"/></method>
  </interface>
</node>
"""

_dbus_started = False


def toggle(label):
    """Otevře/zavře okno instance vybrané popiskem (viz logic.toggle_target)."""
    idx = logic.toggle_target([a.settings() for a in APPLETS], label)
    if idx is not None:
        APPLETS[idx].toggle_popup()


def _on_method_call(_conn, _sender, _path, _iface, method, params, invocation):
    if method == "Toggle":
        try:
            toggle(params.unpack()[0])
        except Exception as e:  # noqa: BLE001 – chyba nesmí shodit applet
            invocation.return_dbus_error("cz.pesstudios.VaultQuickDesktop.Error", str(e))
            return
        invocation.return_value(None)
    else:
        invocation.return_dbus_error("org.freedesktop.DBus.Error.UnknownMethod", method)


def _start_dbus():
    global _dbus_started
    if _dbus_started:
        return
    _dbus_started = True
    node = Gio.DBusNodeInfo.new_for_xml(DBUS_XML)

    def acquired(conn, _name):
        conn.register_object(OBJECT_PATH, node.interfaces[0], _on_method_call, None, None)
    Gio.bus_own_name(Gio.BusType.SESSION, BUS_NAME, Gio.BusNameOwnerFlags.NONE,
                     acquired, None, None)


def _start_timers():
    global _timers_started
    if _timers_started:
        return
    _timers_started = True
    _start_dbus()
    GLib.timeout_add_seconds(REFRESH_SECONDS, lambda: refresh_all() or True)
    _schedule_midnight()


def _schedule_midnight():
    def fire():
        refresh_all()
        _schedule_midnight()
        return False
    GLib.timeout_add_seconds(logic.seconds_until_midnight(datetime.datetime.now()), fire)


class _Callbacks(popup.Callbacks):
    def __init__(self, owner):
        self.owner = owner

    def refresh(self):
        refresh_all()

    def toggle_overdue(self):
        self.owner.toggle_setting("overdueExpanded")

    def toggle_no_date(self):
        self.owner.toggle_setting("noDateExpanded")

    def complete(self, entry, check):
        self.owner.complete(entry)

    def open_task(self, entry):
        self.owner.open_task(entry.get("path"))

    def add(self, date, day_box):
        self.owner.quick_add(date, day_box)


class TaskApplet:
    def __init__(self, applet):
        self.applet = applet
        self.key = applet.get_preferences_path() or f"anon:{id(applet)}"
        self.agenda = None
        self.agenda_today = None
        self.error = None
        self.projects = []
        self._busy = False
        self._again = False
        self._popup = None
        self._render_pending = False  # obnovení přišlo při rozepsaném řádku zapsání
        self._callbacks = _Callbacks(self)

        applet.set_flags(MatePanelApplet.AppletFlags.EXPAND_MINOR)
        applet.set_background_widget(applet)  # průhledné pozadí podle panelu
        self.label = Gtk.Label()
        self.label.set_margin_start(4)
        self.label.set_margin_end(4)
        applet.add(self.label)
        applet.connect("button-press-event", self._on_press)
        applet.connect("destroy", self._on_destroy)
        self._setup_menu()
        self._show_bar_initial()
        applet.show_all()

        APPLETS.append(self)
        _start_timers()
        self.refresh()

    # --- nastavení ---
    def settings(self):
        return instances().get(self.key)

    def save_settings(self, values):
        instances().set(self.key, values)

    def toggle_setting(self, name):
        s = self.settings()
        s[name] = not s.get(name)
        self.save_settings(s)
        self._render_popup()

    # --- lišta ---
    def _show_bar_initial(self):
        s = self.settings()
        self.label.set_markup(f'<span alpha="50%">{logic.escape(s["label"])}</span>')
        self.applet.set_tooltip_text(s["label"])

    def _update_bar(self):
        s = self.settings()
        if self.error is not None:
            text, tip = logic.error_bar(self.error.code)
            self.label.set_text(text)
            self.applet.set_tooltip_text(tip)
        elif self.agenda is not None:
            self.label.set_markup(logic.bar_markup(s["label"], self.agenda.get("counts") or {}))
            self.applet.set_tooltip_text(logic.bar_tooltip(s["label"], self.agenda.get("top")))

    # --- obnovení ---
    def refresh(self):
        if self._busy:
            self._again = True
            return
        self._busy = True
        s = self.settings()
        today = datetime.date.today()

        def fetch():
            return client().request("agenda", project=s["project"], days=int(s["days"]),
                                    noDate=s["noDate"], today=today.isoformat())

        def done(result, error):
            self._busy = False
            if self.applet is None:
                return
            old_agenda, old_error = self.agenda, self.error
            if error is None:
                self.agenda, self.agenda_today, self.error = result, today, None
            else:
                self.error = error
            if logic.refresh_changed(old_agenda, old_error, self.agenda, self.error):
                self._update_bar()
                self._render_popup()
            if self._again:
                self._again = False
                self.refresh()
        run_async(fetch, done)

    # --- okno ---
    def _ensure_popup(self):
        if self._popup is None:
            self._popup = popup.AgendaPopup(self.applet)
        return self._popup

    def _content(self):
        s = self.settings()
        if self.error is not None:
            code = self.error.code
            if code == "vault":
                return popup.build_message_box(s, texts.VAULT_UNAVAILABLE, self._callbacks)
            msg = texts.TIMEOUT if code == "timeout" else texts.HELPER_NOT_RUNNING
            return popup.build_message_box(s, msg, self._callbacks, retry=True)
        if self.agenda is None:
            return popup.build_message_box(s, texts.LOADING, self._callbacks)
        return popup.build_agenda_box(self.agenda, s, self.agenda_today, self._callbacks)

    def _render_popup(self):
        p = self._popup
        if p is None or not p.is_visible():
            return
        if p.keep_open:
            # rozepsaný řádek zapsání – obsah se nepřestaví, dožene se po jeho zavření
            self._render_pending = True
            return
        self._render_pending = False
        p.set_content(self._content())

    def toggle_popup(self):
        p = self._ensure_popup()
        if p.is_visible():
            p.hide()
            return
        if p.recently_hidden():
            return  # klik na applet právě zavřel okno ztrátou fokusu
        p.set_content(self._content())
        p.show()
        self.refresh()

    def _on_press(self, _w, event):
        if event.button == 1:
            self.toggle_popup()
            return True
        return False

    # --- akce ---
    def complete(self, entry):
        today = datetime.date.today().isoformat()

        def work():
            return client().request("complete", path=entry["path"],
                                    expected=entry.get("date"), today=today)

        def done(_result, error):
            code = error.code if error is not None else None
            if code == "failed":
                self.open_task(entry["path"])  # nejde odškrtnout → formulář úkolu
            msg = logic.complete_error_message(code)
            if msg:
                self._show_message(msg, texts.ERROR_DETAIL.format(code=code))
            refresh_all()  # i po `stale` a jiných chybách – agenda se načte znovu
        run_async(work, done)

    def open_task(self, path):
        if path:
            form.open_form(client(), path, refresh_all, font_size=self.settings()["fontSize"])

    def quick_add(self, date, day_box):
        """＋ u dne: řádek rychlého zapsání; Enter → `create` s datem dne a projektem instance."""
        p = self._popup
        if p is None or not p.is_visible():
            return
        project = self.settings()["project"]

        def submit(text):
            params = formlogic.quick_create_params(text, date, project)
            entry = p.quick
            if params is None or entry is None:
                cancel()
                return
            entry.set_sensitive(False)

            def done(result, error):
                if p.quick is entry:
                    p.end_quick()
                if error is not None and error.code != "empty":
                    self._show_message(texts.CREATE_FAILED,
                                       texts.ERROR_DETAIL.format(code=error.code))
                elif error is None:
                    warning = formlogic.create_warning(params, result)
                    if warning:
                        self._show_message(warning)
                refresh_all()
            run_async(lambda: client().request("create", **params), done)

        def cancel():
            p.end_quick()
            if self._render_pending:
                self._render_popup()
        p.start_quick(day_box, submit, cancel)

    def _show_message(self, text, detail=""):
        d = Gtk.MessageDialog(message_type=Gtk.MessageType.WARNING,
                              buttons=Gtk.ButtonsType.OK, text=text)
        if detail:
            d.format_secondary_text(detail)
        d.set_keep_above(True)
        d.connect("response", lambda dlg, _r: dlg.destroy())
        d.show()

    # --- kontextové menu ---
    def _setup_menu(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")  # Gtk.Action je zastaralé, ale applet ho vyžaduje
            group = Gtk.ActionGroup(name="VaultQuickTasksActions")
            for name, label, cb in (("VqPrefs", texts.PREFERENCES, self._on_prefs),
                                    ("VqRefresh", texts.REFRESH, lambda *_a: self.refresh()),
                                    ("VqObsidian", texts.OPEN_OBSIDIAN, self._on_obsidian)):
                action = Gtk.Action(name=name, label=label, tooltip=None)
                action.connect("activate", cb)
                group.add_action(action)
            self.applet.setup_menu(MENU_XML, group)
        self._menu_group = group

    def _on_obsidian(self, *_a):
        vault = store.load_config()["vault"]
        _spawn(["xdg-open", logic.obsidian_url(vault, self.settings()["project"])])

    def _on_prefs(self, *_a):
        def save(values):
            self.save_settings(values)
            self.agenda = None  # jiný projekt / dny – stará agenda neplatí
            self._show_bar_initial()
            self.refresh()
        dlg = prefs.PrefsDialog(self.settings(), self.projects, save)
        dlg.show()

        def done(result, error):
            if error is None:
                self.projects = list(result.get("projects") or [])
                dlg.set_projects(self.projects)
        run_async(lambda: client().request("meta"), done)

    def _on_destroy(self, *_a):
        if self in APPLETS:
            APPLETS.remove(self)
        if self._popup is not None:
            self._popup.window.destroy()
            self._popup = None
        self.applet = None
        if not APPLETS and _client is not None:
            _client.close()


def factory_cb(applet, iid, _data):
    if iid != APPLET_ID:
        return False
    TaskApplet(applet)
    return True


def main():
    MatePanelApplet.Applet.factory_main(FACTORY_ID, True, MatePanelApplet.Applet.__gtype__,
                                        factory_cb, None)
