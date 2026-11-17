# Testy GTK částí (strom okna agendy, předvolby, applet s falešným pomocníkem).
# Bez displeje se přeskočí.
import datetime, os, sys, tempfile, textwrap, time, unittest
import _path  # noqa

try:
    import gi
    gi.require_version("Gtk", "3.0")
    gi.require_version("Gdk", "3.0")
    from gi.repository import Gdk, GLib, Gtk
    HAVE_DISPLAY = Gdk.Display.get_default() is not None
except (ImportError, ValueError):
    HAVE_DISPLAY = False

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


@unittest.skipUnless(HAVE_DISPLAY, "bez displeje")
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

            def add(self, date, box):
                test.calls.append(("add", date, box.get_name()))

            def open_task(self, e):
                test.calls.append(("open", e["path"]))
        return popup.build_agenda_box(AGENDA, s, TODAY, Cb())

    def test_layout_collapsed(self):
        box = self.build(project="pesstudios", label="pesstudios")
        self.assertEqual(texts_of(box, "vq-header"), ["pesstudios"])
        self.assertEqual(texts_of(box, "vq-day-heading"),
                         ["Dnes · út 17. 11.", "Zítra · st 18. 11.", "čt 19. 11."])
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
        self.assertEqual(len(named(box, "vq-check")), 2)
        self.assertEqual(len(named(box, "vq-add")), 3)

    def test_expanded_all_instance(self):
        box = self.build(overdueExpanded=True, noDateExpanded=False)
        all_text = texts_of(box)
        self.assertIn("Stará věc", all_text)
        self.assertEqual(texts_of(box, "vq-date"), ["12. 11.", "1. 10."])
        self.assertNotIn("Snímek do README", all_text)
        self.assertEqual(texts_of(box, "vq-project"), ["pesstudios"])
        self.assertEqual(texts_of(box, "vq-header"), ["Vše"])

    def test_callbacks(self):
        box = self.build()
        named(box, "vq-overdue")[0].clicked()
        named(box, "vq-nodate")[0].clicked()
        named(box, "vq-add")[1].clicked()
        named(box, "vq-title-button")[0].clicked()
        check = named(box, "vq-check")[0]
        check.set_active(True)
        self.assertFalse(check.get_sensitive())
        self.assertEqual(self.calls, [("overdue",), ("nodate",), ("add", "2026-11-18", "vq-day"),
                                      ("open", "0 vyřídit/Zavolat do banky.md"),
                                      ("complete", "Zavolat do banky")])

    def test_empty_and_message(self):
        from vqapplet import popup, store
        s = store.with_defaults({})
        box = popup.build_agenda_box({"overdue": [], "days": [], "noDate": []}, s, TODAY, None)
        self.assertEqual(texts_of(box), ["Vše", "⟳"])
        box = popup.build_message_box(s, "Pomocník neběží", None, retry=True)
        self.assertEqual(texts_of(box, "vq-message"), ["Pomocník neběží"])
        self.assertEqual(len(named(box, "vq-retry")), 1)

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


FAKE_VQD = textwrap.dedent('''
    import sys, json, os
    log = os.environ["FAKE_LOG"]
    agenda = json.loads(os.environ["FAKE_AGENDA"])
    for line in sys.stdin:
        req = json.loads(line)
        with open(log, "a") as f:
            f.write(json.dumps(req, ensure_ascii=False) + "\\n")
        if req["cmd"] == "agenda":
            out = {"id": req["id"], "ok": True, "result": agenda}
        elif req["cmd"] == "complete":
            out = {"id": req["id"], "ok": False, "error": "stale", "message": ""}
        else:
            out = {"id": req["id"], "ok": True, "result": {"projects": ["pesstudios"]}}
        sys.stdout.write(json.dumps(out, ensure_ascii=False) + "\\n"); sys.stdout.flush()
''')


@unittest.skipUnless(HAVE_DISPLAY, "bez displeje")
class AppletTest(unittest.TestCase):
    """TaskApplet nad falešným appletem a falešným pomocníkem (nic se nezapisuje do ~/.config)."""

    def setUp(self):
        import json
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
        self.fake = FakeApplet()

    def tearDown(self):
        self.mod._client.close()
        self.mod._client = None
        self.mod._instances = None
        self.mod.APPLETS.clear()
        self.d.cleanup()

    def pump(self, until, timeout=5):
        end = time.monotonic() + timeout
        ctx = GLib.MainContext.default()
        while time.monotonic() < end and not until():
            ctx.iteration(False)
            time.sleep(0.01)
        self.assertTrue(until())

    def test_refresh_bar_and_popup(self):
        a = self.mod.TaskApplet(self.fake)
        self.assertIn(a, self.mod.APPLETS)
        self.assertIn('action="VqPrefs"', self.fake.menu[0])
        self.pump(lambda: a.agenda is not None)
        self.assertEqual(a.label.get_label(), 'Vše 1 <span foreground="#e67e22">⚠2</span>')
        self.assertEqual(self.fake.get_tooltip_text(), "Zavolat do banky")
        a.toggle_popup()
        self.assertTrue(a._popup.is_visible())
        self.assertIn("Dnes · út 17. 11.", texts_of(a._popup.scrolled))
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
