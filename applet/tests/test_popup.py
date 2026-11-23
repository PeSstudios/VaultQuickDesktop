# Testy GTK částí (strom okna agendy, předvolby, applet s falešným pomocníkem).
# Jen na vyžádání (VQ_GUI_TESTS=1) – okna by blikala na skutečném displeji; bez displeje se přeskočí.
import datetime, os, sys, tempfile, textwrap, time, unittest
import _path  # noqa
from _gui import HAVE_DISPLAY, GUI_SKIP

if HAVE_DISPLAY:
    from gi.repository import GLib, Gtk

TODAY = datetime.date(2026, 11, 17)


def entry(title, date=None, time=None, checkable=True, projects=()):
    return {"path": f"0 vyřídit/{title}.md", "title": title, "date": date, "time": time,
            "checkable": checkable, "occurrence": not checkable, "completable": True,
            "status": "open", "priority": "normal", "projects": list(projects)}


AGENDA = {
    "overdue": [entry("Stará věc", "2026-11-12"), entry("Ještě starší", "2026-10-01")],
    "days": [
        {"date": "2026-11-17", "entries": [entry("Zavolat do banky", "2026-11-17", "09:00",
                                                 projects=["pesstudios"])]},
        {"date": "2026-11-18", "entries": [entry("Vynést koš", "2026-11-18", checkable=False)]},
        {"date": "2026-11-19", "entries": []},
    ],
    "later": [entry("Zaplatit fakturu", "2026-11-27"), entry("Pojistka", "2027-01-08")],
    "noDate": [entry("Snímek do README", projects=["pesstudios"])],
    "counts": {"today": 1, "overdue": 2},
    "top": ["Zavolat do banky"],
}


def texts_of(widget, name=None):
    from vqapplet import popup
    out = []
    for w in popup.iter_widgets(widget):
        if isinstance(w, Gtk.Label) and (name is None or w.get_name() == name):
            out.append(w.get_text())
    return out


def named(widget, name):
    from vqapplet import popup
    return [w for w in popup.iter_widgets(widget) if w.get_name() == name]


@unittest.skipUnless(HAVE_DISPLAY, GUI_SKIP)
class PopupTest(unittest.TestCase):
    def build(self, **settings):
        from vqapplet import popup, store
        s = store.with_defaults(settings)
        self.calls = []
        test = self

        class Cb(popup.Callbacks):
            def complete(self, e, c):
                test.calls.append(("complete", e["title"]))

            def toggle_overdue(self):
                test.calls.append(("overdue",))

            def toggle_no_date(self):
                test.calls.append(("nodate",))

            def toggle_later(self):
                test.calls.append(("later",))

            def open_folder(self):
                test.calls.append(("folder",))

            def open_obsidian(self):
                test.calls.append(("obsidian",))

            def add(self, date, box):
                test.calls.append(("add", date, box.get_name()))

            def open_task(self, e):
                test.calls.append(("open", e["path"]))
        return popup.build_agenda_box(AGENDA, s, TODAY, Cb())

    def test_layout_collapsed(self):
        box = self.build(project="pesstudios", label="pesstudios")
        self.assertEqual(texts_of(box, "vq-header"), ["pesstudios"])
        # všechny dny podle předvoleb, pozdější termíny v sekci Další dny (rozbalené, s datem)
        self.assertEqual(texts_of(box, "vq-day-heading"),
                         ["Dnes · út 17. 11.", "Zítra · st 18. 11.", "čt 19. 11."])
        self.assertIn("Další dny (2)", texts_of(box))
        self.assertEqual(texts_of(box, "vq-date"), ["pá 27. 11.", "pá 8. 1. 2027"])
        # pod záhlavím řádky Otevřít v průzkumníku / v Obsidianu, tooltip = cíl
        self.assertEqual(named(box, "vq-open-obsidian")[0].get_tooltip_text(),
                         "Otevřít v Obsidianu: stránka projektu pesstudios")
        self.assertEqual(named(box, "vq-open-folder")[0].get_tooltip_text(),
                         "Otevřít složku: složka projektu pesstudios")
        self.assertIn("Otevřít v průzkumníku", texts_of(box))
        self.assertIn("Otevřít v Obsidianu", texts_of(box))
        from vqapplet import logic
        icons = [i.get_icon_name()[0] for i in named(box, "vq-open-icon")]
        self.assertIn(icons[0], logic.open_icons("folder"))
        self.assertIn(icons[1], logic.open_icons("file"))
        all_text = texts_of(box)
        self.assertIn("⚠ 2 zpožděné", all_text)
        self.assertIn("▸", all_text)  # zpožděné sbalené
        self.assertNotIn("Stará věc", all_text)
        self.assertEqual(texts_of(box, "vq-empty"), ["Žádné úkoly"])
        self.assertEqual(texts_of(box, "vq-time"), ["09:00"])
        self.assertEqual(texts_of(box, "vq-recurring"), ["🔁"])
        self.assertIn("Bez termínu", all_text)
        self.assertIn("Snímek do README", all_text)  # Bez termínu rozbalené (výchozí)
        self.assertEqual(texts_of(box, "vq-project"), [])  # projekt jen v instanci Vše
        self.assertEqual(len(named(box, "vq-check")), 4)
        self.assertEqual(len(named(box, "vq-add")), 3)  # ＋ u každého dne, ne u Dalších dnů

    def test_expanded_all_instance(self):
        box = self.build(overdueExpanded=True, noDateExpanded=False, laterExpanded=False)
        all_text = texts_of(box)
        self.assertIn("Stará věc", all_text)
        self.assertEqual(texts_of(box, "vq-date"), ["12. 11.", "1. 10."])
        self.assertIn("Další dny (2)", all_text)
        self.assertNotIn("Zaplatit fakturu", all_text)
        self.assertNotIn("Snímek do README", all_text)
        self.assertEqual(texts_of(box, "vq-project"), ["pesstudios"])
        self.assertEqual(texts_of(box, "vq-header"), ["Vše"])

    def test_callbacks(self):
        box = self.build()
        named(box, "vq-overdue")[0].clicked()
        named(box, "vq-nodate")[0].clicked()
        named(box, "vq-later")[0].clicked()
        named(box, "vq-open-folder")[0].clicked()
        named(box, "vq-open-obsidian")[0].clicked()
        named(box, "vq-add")[1].clicked()
        named(box, "vq-title-button")[0].clicked()
        check = named(box, "vq-check")[0]
        check.set_active(True)
        self.assertFalse(check.get_sensitive())
        self.assertEqual(self.calls, [("overdue",), ("nodate",), ("later",), ("folder",), ("obsidian",),
                                      ("add", "2026-11-18", "vq-day"),
                                      ("open", "0 vyřídit/Zavolat do banky.md"),
                                      ("complete", "Zavolat do banky")])

    def test_empty_and_message(self):
        from vqapplet import popup, store
        s = store.with_defaults({"noDate": "none"})
        box = popup.build_agenda_box({"overdue": [], "days": [], "noDate": []}, s, TODAY, None)
        OPEN = ["Otevřít v průzkumníku", "Otevřít v Obsidianu"]
        self.assertEqual(texts_of(box), ["Vše", "⟳"] + OPEN)
        # Bez termínu se ukazuje i prázdná (kvůli ＋), pokud není vypnutá
        s = store.with_defaults({})
        box = popup.build_agenda_box({"overdue": [], "days": [], "noDate": []}, s, TODAY, None)
        self.assertEqual(texts_of(box), ["Vše", "⟳"] + OPEN + ["Bez termínu", "▾", "＋"])
        self.assertEqual(texts_of(build := popup.build_message_box(s, "x", None), "vq-header"),
                         ["Vše"])
        build.destroy()
        box = popup.build_message_box(s, "Pomocník neběží", None, retry=True)
        self.assertEqual(texts_of(box, "vq-message"), ["Pomocník neběží"])
        self.assertEqual(len(named(box, "vq-retry")), 1)
        self.assertEqual(named(box, "vq-choose-vault"), [])
        calls = []

        class Cb(popup.Callbacks):
            def choose_vault(self):
                calls.append("vault")
        box = popup.build_message_box(s, "Vault nenalezen", Cb(), choose_vault=True)
        [b] = named(box, "vq-choose-vault")
        self.assertEqual(named(box, "vq-open-folder"), [])  # bez vaultu není co otevřít
        self.assertEqual(b.get_label(), "Vybrat vault…")
        b.clicked()
        self.assertEqual(calls, ["vault"])

    def test_nodate_add_empty_collapsed(self):
        from vqapplet import popup, store
        s = store.with_defaults({"project": "pesstudios", "noDateExpanded": False})
        calls = []

        class Cb(popup.Callbacks):
            def add(self, date, box):
                calls.append((date, box.get_name(), box.get_children()[0] is not None))
        agenda = {"overdue": [], "days": [{"date": "2026-11-17", "entries": []}], "noDate": []}
        box = popup.build_agenda_box(agenda, s, TODAY, Cb())
        self.assertIn("▸", texts_of(box))
        adds = named(box, "vq-nodate-add")
        self.assertEqual(len(adds), 1)
        self.assertEqual(len(named(box, "vq-add")), 1)  # ＋ u dne zvlášť
        adds[0].clicked()
        self.assertEqual(calls, [(None, popup.NO_DATE_BOX, True)])
        nd = popup.find_named(box, popup.NO_DATE_BOX)
        # řádek zapsání jde vložit pod nadpis sekce (pozice 1), jako u dne
        e = popup.add_quick_row(nd, lambda t: None, lambda: None)
        self.assertIs(nd.get_children()[1], e)

    def test_prefs_icon(self):
        from vqapplet import prefs, store
        with tempfile.TemporaryDirectory() as d:
            vault = os.path.join(d, "vault")
            os.makedirs(os.path.join(vault, "g"))
            img = os.path.join(vault, "g", "Ikona.PNG")
            make_png(img, 40, 20)
            saved, warned = [], []
            dlg = prefs.PrefsDialog(store.with_defaults({"project": "pesstudios"}), [],
                                    saved.append, vault=vault, auto_icon="g/Ikona.PNG")
            dlg._warn = lambda text, detail: warned.append(text)
            self.assertEqual(dlg.icon, "auto")
            self.assertIsNotNone(dlg.icon_preview.get_pixbuf())  # náhled ikony ze stránky
            self.assertFalse(dlg.show_label.get_active())
            # mimo vault → hláška, ikona beze změny
            outside = os.path.join(d, "jinde.png")
            make_png(outside, 10, 10)
            self.assertFalse(dlg.choose_file(outside))
            self.assertEqual(warned, ["Obrázek musí být ve vaultu."])
            # ne-obrázek ve vaultu → hláška
            note = os.path.join(vault, "a.md")
            open(note, "w").close()
            self.assertFalse(dlg.choose_file(note))
            self.assertEqual(dlg.icon, "auto")
            self.assertTrue(dlg.choose_file(img))
            self.assertEqual(dlg.icon, "g/Ikona.PNG")
            pb = dlg.icon_preview.get_pixbuf()
            self.assertEqual((pb.get_width(), pb.get_height()), (64, 32))  # bez ořezu
            dlg.icon_none.clicked()
            self.assertEqual(dlg.icon, "none")
            self.assertIsNone(dlg.icon_preview.get_pixbuf())
            dlg.icon_auto.clicked()
            dlg.show_label.set_active(True)
            self.assertTrue(dlg.show_counts.get_active())  # výchozí: počty na liště
            dlg.show_counts.set_active(False)
            dlg.dialog.response(Gtk.ResponseType.OK)
            self.assertEqual((saved[0]["icon"], saved[0]["showLabel"], saved[0]["showCounts"]),
                             ("auto", True, False))
            self.assertEqual(set(prefs.EDITED_KEYS) - set(saved[0]), set())

    def test_later_empty(self):
        from vqapplet import popup, store
        s = store.with_defaults({})
        days = [{"date": f"2026-11-{d}", "entries": []} for d in (17, 18, 19)]
        # bez pozdějších termínů (nebo starý pomocník bez `later`) → žádná sekce Další dny
        for agenda in ({"days": days, "later": []}, {"days": days}):
            box = popup.build_agenda_box(agenda, s, TODAY, None)
            self.assertNotIn("Další dny", " ".join(texts_of(box)))
            self.assertEqual(len(named(box, "vq-empty")), 3)

    def test_prefs_open_rows(self):
        from vqapplet import prefs, store
        saved = []
        dlg = prefs.PrefsDialog(store.with_defaults({"project": "pesstudios", "openFile": "a.md"}),
                                [], saved.append)
        self.assertFalse(hasattr(dlg, "file_desc"))  # cíl se nevybírá – je dán projektem
        self.assertTrue(dlg.show_folder.get_active() and dlg.show_obsidian.get_active())
        self.assertEqual(dlg.show_folder.get_label(), "Otevřít v průzkumníku")
        dlg.show_obsidian.set_active(False)
        dlg.dialog.response(Gtk.ResponseType.OK)
        self.assertEqual((saved[0]["showOpenFolder"], saved[0]["showOpenObsidian"]), (True, False))
        for k in ("openKind", "openFile", "openFolder"):
            self.assertNotIn(k, saved[0])

    def test_zero_days(self):
        # počet dní 0: jen záhlaví a řádky Otevřít…, žádné úkoly ani sekce (ani Bez termínu)
        from vqapplet import logic, popup
        box = self.build(days=0, noDate="all")
        self.assertEqual(named(box, "vq-day-heading"), [])
        self.assertEqual(named(box, "vq-overdue") + named(box, "vq-nodate")
                         + named(box, "vq-later") + named(box, "vq-title-button"), [])
        self.assertEqual(len(named(box, "vq-open-folder")), 1)
        box = popup.build_agenda_box(logic.empty_agenda(), {"days": 0, "label": "X"}, TODAY, None)
        self.assertEqual(texts_of(box, "vq-header"), ["X"])

    def test_open_rows_checked_only(self):
        box = self.build(showOpenFolder=False)
        self.assertEqual(named(box, "vq-open-folder"), [])
        self.assertEqual(len(named(box, "vq-open-obsidian")), 1)
        box = self.build(showOpenObsidian=False)
        self.assertEqual(len(named(box, "vq-open-folder")), 1)
        self.assertEqual(named(box, "vq-open-obsidian"), [])
        box = self.build(showOpenFolder=False, showOpenObsidian=False, label="X")
        self.assertEqual(named(box, "vq-open-rows"), [])
        self.assertEqual(texts_of(box, "vq-header"), ["X"])
        self.assertEqual(texts_of(box, "vq-header"), ["X"])

    def test_prefs_other_page(self):
        from vqapplet import form, prefs, store
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "1 projekty"))
            page = os.path.join(d, "1 projekty", "Nový web.md")
            open(page, "w").close()
            saved, warned = [], []
            dlg = prefs.PrefsDialog(store.with_defaults({"project": "pesstudios"}),
                                    ["Constelia", "pesstudios"], saved.append, vault=d)
            dlg._warn = lambda text, detail: warned.append(text)
            self.assertEqual(dlg.header.get_text(), "Předvolby – pesstudios")
            ids = [r[1] for r in dlg.project.get_model()]
            self.assertEqual(ids[-1], form.OTHER_ID)
            dlg._run_page_chooser = lambda: None  # zrušeno → výběr se vrátí
            dlg.project.set_active_id(form.OTHER_ID)
            self.assertEqual(dlg.project.get_active_id(), "pesstudios")
            self.assertFalse(dlg.choose_project_file(os.path.join(d, "a.png")))
            self.assertEqual(warned, ["Projekt musí být stránka (.md)."])
            dlg._run_page_chooser = lambda: page
            dlg.project.set_active_id(form.OTHER_ID)
            self.assertEqual(dlg.project.get_active_id(), "Nový web")
            self.assertEqual(dlg.label.get_text(), "Nový web")  # výchozí popisek nového projektu
            self.assertEqual(dlg.header.get_text(), "Předvolby – Nový web")
            # seznam z `meta` dorazí později – vybraná stránka zůstane, Jiná stránka… poslední
            dlg.set_projects(["Constelia", "pesstudios"])
            self.assertEqual(dlg.project.get_active_id(), "Nový web")
            self.assertEqual([r[1] for r in dlg.project.get_model()][-1], form.OTHER_ID)
            dlg.dialog.response(Gtk.ResponseType.OK)
            self.assertEqual(saved[0]["project"], "Nový web")

    def test_prefs_project_change(self):
        from vqapplet import prefs, store
        saved = []
        d = prefs.PrefsDialog(store.with_defaults({}), ["Constelia", "pesstudios"], saved.append)
        self.assertEqual(d.project.get_active_id(), "")
        d.project.set_active_id("pesstudios")
        self.assertEqual(d.label.get_text(), "pesstudios")
        self.assertEqual(d.no_date.get_active_id(), "all")
        d.days.set_value(3)
        # seznam projektů dorazí později – výběr zůstane
        d.set_projects(["Constelia", "Littera", "pesstudios"])
        self.assertEqual(d.project.get_active_id(), "pesstudios")
        d.dialog.response(Gtk.ResponseType.OK)
        self.assertEqual(saved[0]["project"], "pesstudios")
        self.assertEqual((saved[0]["label"], saved[0]["noDate"], saved[0]["days"]),
                         ("pesstudios", "all", 3))
        d2 = prefs.PrefsDialog(store.with_defaults({"project": "pesstudios"}), [], saved.append)
        d2.project.set_active_id("")
        self.assertEqual((d2.label.get_text(), d2.no_date.get_active_id()), ("Vše", "inProgress"))
        d2.dialog.destroy()


def make_png(path, w, h):
    from gi.repository import GdkPixbuf
    pb = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, True, 8, w, h)
    pb.fill(0x3366ccff)
    pb.savev(path, "png", [], [])


FAKE_VQD = textwrap.dedent('''
    import sys, json, os
    log = os.environ["FAKE_LOG"]
    agenda = json.loads(os.environ["FAKE_AGENDA"])
    for line in sys.stdin:
        req = json.loads(line)
        with open(log, "a") as f:
            f.write(json.dumps(req, ensure_ascii=False) + "\\n")
        if req["cmd"] == "agenda" and os.path.exists(log + ".novault"):
            out = {"id": req["id"], "ok": False, "error": "vault", "message": ""}
        elif req["cmd"] == "agenda":
            out = {"id": req["id"], "ok": True, "result": agenda}
        elif req["cmd"] == "complete":
            out = {"id": req["id"], "ok": False, "error": "stale", "message": ""}
        elif req["cmd"] == "icon":
            out = {"id": req["id"], "ok": True, "result": {"path": os.environ.get("FAKE_ICON") or None}}
        elif req["cmd"] == "create":
            out = {"id": req["id"], "ok": True, "result": {"path": "x.md", "project": req["project"]}}
        else:
            out = {"id": req["id"], "ok": True, "result": {"projects": ["pesstudios"]}}
        sys.stdout.write(json.dumps(out, ensure_ascii=False) + "\\n"); sys.stdout.flush()
''')


@unittest.skipUnless(HAVE_DISPLAY, GUI_SKIP)
class AppletTest(unittest.TestCase):
    """TaskApplet nad falešným appletem a falešným pomocníkem (nic se nezapisuje do ~/.config)."""

    def setUp(self):
        import json
        import gi
        gi.require_version("MatePanelApplet", "4.0")
        from vqapplet import applet, client, store
        self.d = tempfile.TemporaryDirectory()
        script = os.path.join(self.d.name, "fake.py")
        with open(script, "w", encoding="utf-8") as f:
            f.write(FAKE_VQD)
        self.log = os.path.join(self.d.name, "log.jsonl")
        os.environ["FAKE_LOG"] = self.log
        os.environ["FAKE_AGENDA"] = json.dumps(AGENDA)
        applet._client = client.Client([sys.executable, script], timeout=5)
        applet._instances = store.Instances(os.path.join(self.d.name, "instances.json"))
        applet._timers_started = True  # žádné časovače v testu
        self.vault = os.path.join(self.d.name, "vault")
        os.makedirs(self.vault)
        self._vault_root = applet.vault_root
        applet.vault_root = lambda: self.vault  # ne skutečný config.json
        os.environ.pop("FAKE_ICON", None)
        self.mod = applet

        class FakeApplet(Gtk.EventBox):
            def get_preferences_path(self):
                return "/org/mate/panel/objects/object_8/prefs/"

            def set_flags(self, _f):
                pass

            def set_background_widget(self, _w):
                pass

            def setup_menu(self, xml, group):
                self.menu = (xml, group)

            def get_orient(self):
                from gi.repository import MatePanelApplet
                return MatePanelApplet.AppletOrient.UP

            def get_size(self):
                return 24
        self.fake = FakeApplet()

    def tearDown(self):
        self.mod._client.close()
        self.mod._client = None
        self.mod._instances = None
        self.mod.APPLETS.clear()
        self.mod.vault_root = self._vault_root
        os.environ.pop("FAKE_ICON", None)
        self.d.cleanup()

    def pump(self, until, timeout=5):
        end = time.monotonic() + timeout
        ctx = GLib.MainContext.default()
        while time.monotonic() < end and not until():
            ctx.iteration(False)
            time.sleep(0.01)
        self.assertTrue(until())

    def test_vault_missing_and_chosen(self):
        open(self.log + ".novault", "w").close()
        saved = []
        orig = self.mod.store.save_vault
        self.mod.store.save_vault = saved.append
        try:
            a = self.mod.TaskApplet(self.fake)
            self.assertIn('action="VqVault"', self.fake.menu[0])
            self.pump(lambda: a.error is not None)
            self.assertEqual(a.error.code, "vault")
            a.toggle_popup()
            self.assertEqual(len(named(a._popup.scrolled, "vq-choose-vault")), 1)
            self.assertEqual(texts_of(a._popup.scrolled, "vq-message"),
                             ["Vault nenalezen:\n" + self.vault])
            a.toggle_popup()
            os.remove(self.log + ".novault")
            old_proc = self.mod._client._proc
            self.mod.apply_vault("/novy/vault")
            self.assertEqual(saved, ["/novy/vault"])
            self.assertIsNone(self.mod._client._proc)  # pomocník se spustí znovu
            self.pump(lambda: a.agenda is not None and a.error is None)
            self.assertIsNot(self.mod._client._proc, old_proc)
        finally:
            self.mod.store.save_vault = orig

    def test_refresh_bar_and_popup(self):
        a = self.mod.TaskApplet(self.fake)
        self.assertIn(a, self.mod.APPLETS)
        self.assertIn('action="VqPrefs"', self.fake.menu[0])
        self.pump(lambda: a.agenda is not None)
        self.assertEqual(a.label.get_label(), 'Vše 1 <span foreground="#e67e22">⚠2</span>')
        self.assertEqual(self.fake.get_tooltip_text(), "Vše\nZavolat do banky")
        self.assertFalse(a.has_icon)  # instance Vše: bez ikony, popisek na liště
        a.toggle_popup()
        self.assertTrue(a._popup.is_visible())
        self.assertIn("Zavolat do banky", texts_of(a._popup.scrolled))  # nezávisle na dnešku
        a._callbacks.toggle_overdue()
        self.assertTrue(self.mod.instances().get(a.key)["overdueExpanded"])
        self.assertIn("Stará věc", texts_of(a._popup.scrolled))
        # odškrtnutí → complete (stale) → nové načtení agendy
        def lines():
            import json
            with open(self.log, encoding="utf-8") as f:
                return [json.loads(l) for l in f]
        n = len(lines())
        a.complete(AGENDA["days"][0]["entries"][0])

        def reqs():
            return lines()[n:]
        self.pump(lambda: len(reqs()) >= 2)
        r = reqs()
        self.assertEqual(r[0]["cmd"], "complete")
        self.assertEqual((r[0]["path"], r[0]["expected"]),
                         ("0 vyřídit/Zavolat do banky.md", "2026-11-17"))
        self.assertEqual(r[1]["cmd"], "agenda")
        a.toggle_popup()
        self.assertFalse(a._popup.is_visible())
        self.fake.destroy()
        self.assertNotIn(a, self.mod.APPLETS)

    def lines(self):
        import json
        with open(self.log, encoding="utf-8") as f:
            return [json.loads(l) for l in f]

    def test_icon_from_project(self):
        os.makedirs(os.path.join(self.vault, "g"))
        make_png(os.path.join(self.vault, "g", "i.png"), 30, 10)
        os.environ["FAKE_ICON"] = "g/i.png"
        self.mod.instances().set(self.fake.get_preferences_path(), {"project": "pesstudios"})
        a = self.mod.TaskApplet(self.fake)
        self.pump(lambda: a.agenda is not None and a.has_icon)
        self.assertEqual(a.icon_path, "g/i.png")
        pb = a.image.get_pixbuf()
        self.assertEqual((pb.get_width(), pb.get_height()), (60, 20))  # výška lišty − 4, bez ořezu
        self.assertTrue(a.image.get_visible())
        # vedle ikony jen počty, popisek v tooltipu
        self.assertEqual(a.label.get_label(), '1 <span foreground="#e67e22">⚠2</span>')
        self.assertTrue(self.fake.get_tooltip_text().startswith("pesstudios\n"))
        icons = [r for r in self.lines() if r["cmd"] == "icon"]
        self.assertEqual([r["project"] for r in icons], ["pesstudios"])
        # obnovení agendy ikonu znovu nezjišťuje
        a.refresh()
        n = len(self.lines())
        self.pump(lambda: len(self.lines()) > n)
        self.assertEqual(len([r for r in self.lines() if r["cmd"] == "icon"]), 1)
        # Zobrazit i popisek
        s = self.mod.instances().get(a.key)
        s["showLabel"] = True
        self.mod.instances().set(a.key, s)
        a._update_bar()
        self.assertEqual(a.label.get_label(), 'pesstudios 1 <span foreground="#e67e22">⚠2</span>')
        # Bez ikony → popisek vždy
        s["icon"], s["showLabel"] = "none", False
        self.mod.instances().set(a.key, s)
        a.resolve_icon()
        self.assertFalse(a.has_icon)
        self.assertFalse(a.image.get_visible())
        self.assertTrue(a.label.get_label().startswith("pesstudios 1"))
        # vybraný obrázek, který neexistuje → bez obrázku
        s["icon"] = "neni.png"
        self.mod.instances().set(a.key, s)
        a.resolve_icon()
        self.assertFalse(a.has_icon)
        self.fake.destroy()

    def test_helper_down(self):
        from vqapplet import client
        self.mod._client.close()
        self.mod._client = client.Client(["/neexistuje/vqd"], timeout=2)
        a = self.mod.TaskApplet(self.fake)
        self.pump(lambda: a.error is not None)
        self.assertEqual(a.label.get_text(), "…")
        self.assertEqual(self.fake.get_tooltip_text(), "Pomocník neběží")
        self.fake.destroy()


if __name__ == "__main__":
    unittest.main()
