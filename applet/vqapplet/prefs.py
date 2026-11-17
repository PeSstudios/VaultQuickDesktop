# Dialog Předvolby jedné instance appletu.
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk  # noqa: E402

from . import logic, texts  # noqa: E402

NO_DATE_CHOICES = (("none", texts.NO_DATE_NONE),
                   ("inProgress", texts.NO_DATE_IN_PROGRESS),
                   ("all", texts.NO_DATE_ALL))
ALL_ID = ""  # id položky „Vše“ v seznamu projektů


class PrefsDialog:
    """Předvolby: projekt, popisek, dny, Bez termínu, velikost písma.
    on_save(dict) dostane kompletní nastavení instance (popisek vždy explicitně)."""

    def __init__(self, settings, projects, on_save, parent=None):
        self.settings = dict(settings)
        self.on_save = on_save
        self.closed = False
        d = Gtk.Dialog(title=texts.PREFS_TITLE, transient_for=parent, modal=False)
        d.add_button(texts.CANCEL, Gtk.ResponseType.CANCEL)
        d.add_button(texts.SAVE, Gtk.ResponseType.OK)
        d.set_default_response(Gtk.ResponseType.OK)
        d.set_keep_above(True)
        grid = Gtk.Grid(row_spacing=8, column_spacing=12, border_width=12)

        self.project = Gtk.ComboBoxText()
        self.set_projects(projects)
        self.label = Gtk.Entry()
        self.label.set_text(self.settings.get("label") or "")
        self.label.set_activates_default(True)
        self.days = Gtk.SpinButton.new_with_range(1, 14, 1)
        self.days.set_value(int(self.settings.get("days", 7)))
        self.no_date = Gtk.ComboBoxText()
        for key, text in NO_DATE_CHOICES:
            self.no_date.append(key, text)
        self.no_date.set_active_id(self.settings.get("noDate") or "inProgress")
        self.font = Gtk.SpinButton.new_with_range(6, 32, 1)
        self.font.set_value(float(self.settings.get("fontSize", 11)))
        self.project.connect("changed", self._project_changed)

        rows = ((texts.PREFS_PROJECT, self.project), (texts.PREFS_LABEL, self.label),
                (texts.PREFS_DAYS, self.days), (texts.PREFS_NO_DATE, self.no_date),
                (texts.PREFS_FONT, self.font))
        for i, (name, widget) in enumerate(rows):
            lab = Gtk.Label(label=name, xalign=0)
            grid.attach(lab, 0, i, 1, 1)
            widget.set_hexpand(True)
            grid.attach(widget, 1, i, 1, 1)
        d.get_content_area().add(grid)
        d.connect("response", self._response)
        self.dialog = d

    def set_projects(self, projects):
        """Naplní seznam projektů (Vše + projekty z `meta`); zachová vybraný projekt."""
        if self.closed:
            return
        # už vybraný projekt (uživatel mohl změnit dřív, než přišel seznam) má přednost
        active = self.project.get_active_id()
        current = (active or None) if active is not None else self.settings.get("project")
        self._filling = True
        self.project.remove_all()
        self.project.append(ALL_ID, texts.ALL)
        names = list(projects or [])
        if current and current not in names:
            names.insert(0, current)
        for p in names:
            self.project.append(p, p)
        self.project.set_active_id(current or ALL_ID)
        self._filling = False

    def _project_changed(self, combo):
        if getattr(self, "_filling", False):
            return
        project = combo.get_active_id() or None
        # popisek a výchozí Bez termínu podle nového projektu
        self.label.set_text(logic.default_label(project))
        self.no_date.set_active_id(logic.default_no_date(project))

    def values(self):
        v = dict(self.settings)
        project = self.project.get_active_id() or None
        v["project"] = project
        v["label"] = self.label.get_text().strip() or logic.default_label(project)
        v["days"] = int(self.days.get_value())
        v["noDate"] = self.no_date.get_active_id() or logic.default_no_date(project)
        v["fontSize"] = int(self.font.get_value())
        return v

    def _response(self, dialog, response):
        if response == Gtk.ResponseType.OK:
            self.on_save(self.values())
        self.closed = True
        dialog.destroy()

    def show(self):
        self.dialog.show_all()
        self.dialog.present()
