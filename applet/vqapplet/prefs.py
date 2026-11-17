# Dialog Předvolby jedné instance appletu.
import os

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import GdkPixbuf, GLib, Gtk  # noqa: E402

from . import logic, texts  # noqa: E402

NO_DATE_CHOICES = (("none", texts.NO_DATE_NONE),
                   ("inProgress", texts.NO_DATE_IN_PROGRESS),
                   ("all", texts.NO_DATE_ALL))
ALL_ID = ""  # id položky „Vše“ v seznamu projektů
# pole, která Předvolby upravují (applet je při uložení přenese do aktuálního nastavení,
# ostatní – třeba rozbalení sekcí – zůstanou, jak jsou)
EDITED_KEYS = ("project", "label", "days", "noDate", "fontSize", "icon", "showLabel")
PREVIEW_HEIGHT = 32  # náhled ikony v Předvolbách
CHOOSER_PREVIEW = 128  # náhled vybraného souboru ve výběru


def _pixbuf(path, width, height):
    """Obrázek zmenšený do width×height se zachováním poměru stran (bez ořezu); chyba → None."""
    if not path:
        return None
    try:
        return GdkPixbuf.Pixbuf.new_from_file_at_scale(path, width, height, True)
    except (GLib.Error, TypeError):
        return None


def _ci_pattern(ext):
    """Vzor přípony bez ohledu na velikost písmen: png → *.[pP][nN][gG]."""
    return "*." + "".join(f"[{c.lower()}{c.upper()}]" for c in ext)


class PrefsDialog:
    """Předvolby: projekt, popisek, dny, Bez termínu, velikost písma, ikona, popisek u ikony.
    on_save(dict) dostane kompletní nastavení instance (popisek vždy explicitně).
    vault = kořen vaultu (výběr obrázku), auto_icon = ikona zjištěná ze stránky projektu
    (relativně k vaultu) pro náhled volby „Podle projektu“."""

    def __init__(self, settings, projects, on_save, parent=None, vault=None, auto_icon=None):
        self.settings = dict(settings)
        self.on_save = on_save
        self.closed = False
        self.vault = vault
        self.auto_icon = auto_icon
        self.icon = self.settings.get("icon") or "auto"
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
        icon_row = self._build_icon_row()
        self.show_label = Gtk.CheckButton(label=texts.PREFS_SHOW_LABEL)
        self.show_label.set_active(bool(self.settings.get("showLabel")))

        rows = ((texts.PREFS_PROJECT, self.project), (texts.PREFS_LABEL, self.label),
                (texts.PREFS_DAYS, self.days), (texts.PREFS_NO_DATE, self.no_date),
                (texts.PREFS_FONT, self.font), (texts.PREFS_ICON, icon_row),
                ("", self.show_label))
        for i, (name, widget) in enumerate(rows):
            lab = Gtk.Label(label=name, xalign=0)
            grid.attach(lab, 0, i, 1, 1)
            widget.set_hexpand(True)
            grid.attach(widget, 1, i, 1, 1)
        d.get_content_area().add(grid)
        d.connect("response", self._response)
        self.dialog = d
        self._update_icon_preview()

    # --- ikona ---
    def _build_icon_row(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        top = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.icon_preview = Gtk.Image()
        self.icon_preview.set_size_request(PREVIEW_HEIGHT, PREVIEW_HEIGHT)
        self.icon_desc = Gtk.Label(xalign=0)
        self.icon_desc.set_line_wrap(True)
        self.icon_desc.set_max_width_chars(40)
        top.pack_start(self.icon_preview, False, False, 0)
        top.pack_start(self.icon_desc, True, True, 0)
        buttons = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self.icon_choose = Gtk.Button(label=texts.ICON_CHOOSE)
        self.icon_choose.connect("clicked", lambda _b: self._run_chooser())
        self.icon_auto = Gtk.Button(label=texts.ICON_AUTO)
        self.icon_auto.connect("clicked", lambda _b: self.set_icon("auto"))
        self.icon_none = Gtk.Button(label=texts.ICON_NONE)
        self.icon_none.connect("clicked", lambda _b: self.set_icon("none"))
        for b in (self.icon_choose, self.icon_auto, self.icon_none):
            buttons.pack_start(b, False, False, 0)
        box.pack_start(top, False, False, 0)
        box.pack_start(buttons, False, False, 0)
        return box

    def set_icon(self, value):
        """value = "auto" | "none" | cesta relativně k vaultu."""
        self.icon = value
        self._update_icon_preview()

    def _abs(self, relative):
        if not relative or not self.vault:
            return None
        return logic.icon_abs(self.vault, relative)

    def _update_icon_preview(self):
        kind, value = logic.icon_source({"icon": self.icon})
        project = self.project.get_active_id() or None
        if kind == "path":
            rel, desc = value, value
        elif kind == "none":
            rel, desc = None, texts.ICON_NONE_DESC
        else:
            # náhled ikony ze stránky jen pro projekt, pro který byla zjištěná
            same = project == self.settings.get("project")
            rel = self.auto_icon if same else None
            desc = texts.ICON_AUTO_DESC + (f": {rel}" if rel else "")
        pb = _pixbuf(self._abs(rel), -1, PREVIEW_HEIGHT)
        if pb is not None:
            self.icon_preview.set_from_pixbuf(pb)
        else:
            self.icon_preview.clear()
        self.icon_desc.set_text(desc)

    def choose_file(self, filename):
        """Soubor vybraný ve výběru → ikona, je-li to obrázek ve vaultu; jinak hláška
        a ikona se nemění. Vrátí True, když se ikona změnila."""
        rel = logic.vault_relative(self.vault, filename) if self.vault else None
        if rel is None:
            self._warn(texts.ICON_OUTSIDE_VAULT,
                       texts.ICON_OUTSIDE_VAULT_DETAIL.format(path=filename, vault=self.vault))
            return False
        if not logic.is_image(rel):
            self._warn(texts.ICON_NOT_IMAGE, texts.ICON_NOT_IMAGE_DETAIL)
            return False
        self.set_icon(rel)
        return True

    def _warn(self, text, detail):
        d = Gtk.MessageDialog(transient_for=self.dialog, modal=True,
                              message_type=Gtk.MessageType.WARNING,
                              buttons=Gtk.ButtonsType.OK, text=text)
        d.format_secondary_text(detail)
        d.set_keep_above(True)
        d.run()
        d.destroy()

    def _run_chooser(self):
        c = Gtk.FileChooserDialog(title=texts.ICON_CHOOSER_TITLE, transient_for=self.dialog,
                                  action=Gtk.FileChooserAction.OPEN, modal=True)
        c.add_button(texts.CANCEL, Gtk.ResponseType.CANCEL)
        c.add_button(texts.ICON_CHOOSER_OPEN, Gtk.ResponseType.ACCEPT)
        c.set_default_response(Gtk.ResponseType.ACCEPT)
        c.set_keep_above(True)
        flt = Gtk.FileFilter()
        flt.set_name(texts.ICON_FILTER)
        for ext in logic.IMAGE_EXTENSIONS:
            flt.add_pattern(_ci_pattern(ext))
        c.add_filter(flt)
        current = self._abs(logic.icon_source({"icon": self.icon})[1])
        if current and os.path.exists(current):
            c.set_filename(current)
        elif self.vault and os.path.isdir(self.vault):
            c.set_current_folder(self.vault)
        preview = Gtk.Image()
        c.set_preview_widget(preview)
        c.set_use_preview_label(False)

        def update_preview(chooser):
            pb = _pixbuf(chooser.get_preview_filename(), CHOOSER_PREVIEW, CHOOSER_PREVIEW)
            if pb is not None:
                preview.set_from_pixbuf(pb)
            chooser.set_preview_widget_active(pb is not None)
        c.connect("update-preview", update_preview)
        while True:
            response = c.run()
            filename = c.get_filename() if response == Gtk.ResponseType.ACCEPT else None
            if filename is None or self.choose_file(filename):
                break  # zrušeno nebo vybráno; po hlášce lze vybrat znovu
        c.destroy()

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
        if hasattr(self, "icon_preview"):
            self._update_icon_preview()

    def values(self):
        v = dict(self.settings)
        project = self.project.get_active_id() or None
        v["project"] = project
        v["label"] = self.label.get_text().strip() or logic.default_label(project)
        v["days"] = int(self.days.get_value())
        v["noDate"] = self.no_date.get_active_id() or logic.default_no_date(project)
        v["fontSize"] = int(self.font.get_value())
        v["icon"] = self.icon
        v["showLabel"] = bool(self.show_label.get_active())
        return v

    def _response(self, dialog, response):
        if response == Gtk.ResponseType.OK:
            self.on_save(self.values())
        self.closed = True
        dialog.destroy()

    def show(self):
        self.dialog.show_all()
        self.dialog.present()
