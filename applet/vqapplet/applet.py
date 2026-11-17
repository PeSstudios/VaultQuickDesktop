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
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import GdkPixbuf, Gio, GLib, Gtk, MatePanelApplet  # noqa: E402

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


def vault_root():
    """Kořen vaultu z config.json (`~` rozvinutá) – pro absolutní cestu ikony."""
    return store.load_config()["vault"]


def load_icon(path, panel_size, vertical=False):
    """Pixbuf ikony zmenšený na lištu se zachováním poměru stran (bez ořezu); chyba → None."""
    if not path:
        return None
    w, h = logic.icon_box(panel_size, vertical)
    try:
        return GdkPixbuf.Pixbuf.new_from_file_at_scale(path, w, h, True)
    except (GLib.Error, TypeError):
        return None


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
    # stav ikony (výchozí i pro instance vytvořené bez __init__ v testech)
    icon_path = None  # cesta relativně k vaultu – jen v instanci, ne v nastavení
    has_icon = False  # obrázek je načtený a na liště
    _icon_gen = 0  # pořadí zjišťování – starší odpověď `icon` se zahodí
    _icon_failed = False  # pomocník neběžel → zkusit znovu po úspěšném obnovení

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
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
        self.image = Gtk.Image()
        self.image.set_margin_start(2)
        self.image.set_no_show_all(True)  # viditelnost řídí _apply_icon
        self.label = Gtk.Label()
        self.label.set_margin_start(4)
        self.label.set_margin_end(4)
        self.label.set_no_show_all(True)  # viditelnost řídí _set_bar_label
        box.pack_start(self.image, False, False, 0)
        box.pack_start(self.label, False, False, 0)
        applet.add(box)
        applet.connect("button-press-event", self._on_press)
        applet.connect("destroy", self._on_destroy)
        for signal in ("change-size", "change-orient"):  # jiná výška / orientace lišty
            try:
                applet.connect(signal, lambda *_a: self._apply_icon())
            except TypeError:
                pass  # falešný applet v testech tyto signály nemá
        self._setup_menu()
        self._show_bar_initial()
        applet.show_all()

        APPLETS.append(self)
        _start_timers()
        self.resolve_icon()
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

    # --- ikona ---
    def resolve_icon(self, retry=False):
        """Zjistí cestu ikony podle nastavení: vybraný obrázek, žádný, nebo (auto) příkaz `icon`
        pro projekt instance. Volá se jen při startu, po Předvolbách a při ručním Obnovit
        (`icon` prochází celý vault – ne při každém obnovení). retry=True = opakování po výpadku
        pomocníka; to se při další chybě už neopakuje."""
        self._icon_gen += 1
        gen = self._icon_gen
        self._icon_failed = False
        s = self.settings()
        kind, value = logic.icon_source(s)
        if kind == "path":
            self._set_icon_path(value)
            return
        if kind == "none" or not s["project"]:
            self._set_icon_path(None)  # instance Vše nemá stránku projektu
            return
        project = s["project"]

        def done(result, error):
            if self.applet is None or gen != self._icon_gen:
                return
            if error is not None:
                # znovu jen po výpadku pomocníka a nejvýš jednou (jiná chyba by se opakovala
                # při každém obnovení a pokaždé procházela vault)
                self._icon_failed = error.code in ("not_running", "timeout") and not retry
                self._set_icon_path(None)
                return
            self._set_icon_path((result or {}).get("path"))
        run_async(lambda: client().request("icon", project=project), done)

    def _set_icon_path(self, relative):
        self.icon_path = relative or None
        self._apply_icon()

    def _panel_size(self):
        try:
            return int(self.applet.get_size())
        except (AttributeError, TypeError):
            return 24

    def _vertical(self):
        try:
            o = self.applet.get_orient()
            return o in (MatePanelApplet.AppletOrient.LEFT, MatePanelApplet.AppletOrient.RIGHT)
        except (AttributeError, TypeError):
            return False

    def _apply_icon(self):
        """Načte obrázek podle velikosti lišty; neexistující / nečitelný → bez obrázku."""
        if self.applet is None:
            return
        pixbuf = None
        if self.icon_path:
            pixbuf = load_icon(logic.icon_abs(vault_root(), self.icon_path),
                               self._panel_size(), self._vertical())
        self.has_icon = pixbuf is not None
        if pixbuf is not None:
            self.image.set_from_pixbuf(pixbuf)
            self.image.show()
        else:
            self.image.clear()
            self.image.hide()
        if self.agenda is None and self.error is None:
            self._show_bar_initial()
        else:
            self._update_bar()

    # --- lišta ---
    def _set_bar_label(self, markup):
        """Štítek na liště; prázdný se skryje (jen ikona)."""
        self.label.set_markup(markup)
        self.label.set_visible(bool(markup))

    def _show_bar_initial(self):
        s = self.settings()
        if logic.show_label(s, self.has_icon):
            self._set_bar_label(f'<span alpha="50%">{logic.escape(s["label"])}</span>')
        else:
            self._set_bar_label("")
        self.applet.set_tooltip_text(s["label"])

    def _update_bar(self):
        s = self.settings()
        if self.error is not None:
            text, tip = logic.error_bar(self.error.code)
            self._set_bar_label(logic.escape(text))
            self.applet.set_tooltip_text(tip)
        elif self.agenda is not None:
            with_label = logic.show_label(s, self.has_icon)
            self._set_bar_label(logic.bar_markup(s["label"], self.agenda.get("counts") or {},
                                                 with_label=with_label))
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
            if error is None and self._icon_failed:
                self.resolve_icon(retry=True)  # pomocník předtím neběžel – ikona se zjistí teď
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
        """＋ u dne (nebo u Bez termínu, date=None): řádek rychlého zapsání;
        Enter → `create` s datem dne (bez data) a projektem instance."""
        p = self._popup
        if p is None or not p.is_visible():
            return
        s = self.settings()
        project = s["project"]
        if date is None and not s.get("noDateExpanded", True):
            # sbalená sekce Bez termínu se rozbalí; okno se přestaví → najít novou sekci
            p.end_quick()
            s["noDateExpanded"] = True
            self.save_settings(s)
            self._render_popup()
            day_box = popup.find_named(p.scrolled, popup.NO_DATE_BOX)
            if day_box is None:
                return

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
                                    ("VqRefresh", texts.REFRESH, self._on_refresh),
                                    ("VqObsidian", texts.OPEN_OBSIDIAN, self._on_obsidian)):
                action = Gtk.Action(name=name, label=label, tooltip=None)
                action.connect("activate", cb)
                group.add_action(action)
            self.applet.setup_menu(MENU_XML, group)
        self._menu_group = group

    def _on_refresh(self, *_a):
        self.refresh()
        self.resolve_icon()  # ruční Obnovit načte i změněnou ikonu stránky projektu

    def _on_obsidian(self, *_a):
        vault = store.load_config()["vault"]
        _spawn(["xdg-open", logic.obsidian_url(vault, self.settings()["project"])])

    def _on_prefs(self, *_a):
        def save(values):
            s = self.settings()  # mezitím se mohlo změnit rozbalení sekcí v okně
            s.update({k: values[k] for k in prefs.EDITED_KEYS if k in values})
            self.save_settings(s)
            self.agenda = None  # jiný projekt / dny – stará agenda neplatí
            self.error = None
            self._show_bar_initial()
            self.resolve_icon()  # jiný projekt nebo jiná ikona
            self.refresh()
        s = self.settings()
        auto_icon = self.icon_path if logic.icon_source(s)[0] == "auto" else None
        dlg = prefs.PrefsDialog(s, self.projects, save, vault=vault_root(), auto_icon=auto_icon)
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
