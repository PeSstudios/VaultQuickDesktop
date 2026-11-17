# Testy GTK: řádek rychlého zapsání a formulář úkolu s falešným klientem (okna se neukazují).
# Jen na vyžádání (VQ_GUI_TESTS=1).
import time, unittest
import _path  # noqa
from _gui import HAVE_DISPLAY, GUI_SKIP

if HAVE_DISPLAY:
    from gi.repository import Gdk, GLib, Gtk

from vqapplet.client import VqdError

TASK = {"path": "0 vyřídit/Zavolat.md", "title": "Zavolat", "date": "2026-11-18", "time": "09:00",
        "checkable": True, "occurrence": False, "completable": True, "status": "open",
        "priority": "normal", "projects": ["pesstudios", "Littera"], "scheduled": "2026-11-18T09:00",
        "due": None, "recurrence": None, "contexts": ["telefon"]}
META = {"projects": ["Constelia", "pesstudios"], "statuses": ["open", "in-progress", "done"],
        "priorities": ["high", "normal", "low"]}


class FakeClient:
    """Odpovědi podle příkazu; hodnota může být seznam (postupně) nebo VqdError."""

    def __init__(self, **answers):
        self.answers = answers
        self.calls = []

    def request(self, cmd, **params):
        self.calls.append((cmd, params))
        a = self.answers.get(cmd, {})
        if isinstance(a, list):
            a = a.pop(0) if len(a) > 1 else a[0]
        if isinstance(a, VqdError):
            raise a
        return a


def pump(until, timeout=5):
    end = time.monotonic() + timeout
    ctx = GLib.MainContext.default()
    while time.monotonic() < end and not until():
        ctx.iteration(False)
        time.sleep(0.005)
    return until()


@unittest.skipUnless(HAVE_DISPLAY, GUI_SKIP)
class QuickRowTest(unittest.TestCase):
    def test_row_submit_cancel_and_esc(self):
        from vqapplet import popup

        class FakeApplet:
            pass
        p = popup.AgendaPopup(FakeApplet())
        day = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        day.pack_start(Gtk.Label(label="Dnes"), False, False, 0)
        day.pack_start(Gtk.Label(label="úkol"), False, False, 0)
        root = Gtk.Box()
        root.add(day)
        p.set_content(root)
        got = []
        e = p.start_quick(day, got.append, lambda: got.append("cancel"))
        self.assertTrue(p.keep_open)
        self.assertIs(day.get_children()[1], e)  # hned pod nadpisem
        e.set_text("  Koupit mléko ")
        e.activate()
        self.assertEqual(got, ["  Koupit mléko "])
        # prázdný Enter = zrušit
        e.set_text("  ")
        e.activate()
        self.assertEqual(got[-1], "cancel")
        self.assertIsNone(p.quick)
        self.assertFalse(p.keep_open)
        # Esc zruší řádek, okno nezavírá (hide se nevolá)
        p.start_quick(day, got.append, lambda: got.append("esc"))
        ev = Gdk.Event.new(Gdk.EventType.KEY_PRESS)
        ev.keyval = Gdk.KEY_Escape
        self.assertTrue(p._on_key(None, ev))
        self.assertEqual(got[-1], "esc")
        self.assertIsNone(p.quick)
        self.assertEqual(len(day.get_children()), 2)
        p.window.destroy()

    def test_font_class_reaches_later_widgets(self):
        from vqapplet import popup
        box = Gtk.Box()
        popup.apply_font(box, 11)
        popup.apply_font(box, 14)
        self.assertEqual([c for c in box.get_style_context().list_classes()
                          if c.startswith("vq-font-")], ["vq-font-14"])


@unittest.skipUnless(HAVE_DISPLAY, GUI_SKIP)
class FormTest(unittest.TestCase):
    def make(self, **answers):
        from vqapplet import form
        answers.setdefault("get", {"task": dict(TASK), "body": "tělo\n", "mtime": 100})
        answers.setdefault("meta", META)
        self.client = FakeClient(**answers)
        self.done = []
        f = form.TaskForm(self.client, TASK["path"], lambda: self.done.append(1), font_size=12,
                          vault="/v/MujVault")
        self.asked = []
        self.answer = None
        self.messages = []

        def ask(text, detail, buttons, on_answer):
            self.asked.append(text)
            on_answer(self.answer)
        f.ask = ask
        f.message = lambda text, detail="": self.messages.append(text)
        f.load()
        self.assertTrue(pump(lambda: f.task is not None))
        return f

    def cmds(self):
        return [c for c, _p in self.client.calls]

    def test_fill(self):
        f = self.make()
        self.assertEqual(f.title.get_text(), "Zavolat")
        self.assertEqual(f.date_button.get_label(), "st 18. 11. 2026")
        self.assertEqual(f.time.get_text(), "09:00")
        self.assertEqual(f.status.get_active_id(), "open")
        self.assertEqual(f.priority.get_active_id(), "normal")
        self.assertEqual(f.project.get_active_id(), "pesstudios")
        self.assertFalse(f.recurrence.get_visible())
        self.assertFalse(f.dirty())
        self.assertTrue(f.done.get_sensitive())
        f.close()

    def test_save_merges_projects_and_closes(self):
        f = self.make(save={"mtime": 200})
        f.title.set_text("Zavolat bance")
        f.project.set_active_id("Constelia")
        f._set_date(None)
        self.assertTrue(f.dirty())
        f.save()
        self.assertTrue(pump(lambda: f.closed))
        cmd, params = self.client.calls[-1]
        self.assertEqual(cmd, "save")
        self.assertEqual(params["mtime"], 100)
        self.assertEqual(params["changes"], {
            "title": "Zavolat bance", "date": None, "time": None, "status": "open",
            "priority": "normal", "projects": ["Constelia", "Littera"], "contexts": ["telefon"],
            "body": "tělo\n"})
        self.assertEqual(self.done, [1])

    def test_bad_time(self):
        f = self.make()
        f.time.set_text("25:00")
        f.save()
        self.assertEqual(len(self.messages), 1)
        self.assertNotIn("save", self.cmds())
        f.close()

    def test_conflict_overwrite(self):
        got2 = {"task": dict(TASK, projects=["pesstudios", "Nový"]), "body": "x", "mtime": 150}
        f = self.make(save=[VqdError("conflict"), {"mtime": 300}])
        self.client.answers["get"] = [{"task": dict(TASK), "body": "tělo\n", "mtime": 100}, got2]
        self.client.answers["get"].pop(0)  # první get už proběhl
        f.title.set_text("Nový název")
        self.answer = "overwrite"
        f.save()
        self.assertTrue(pump(lambda: f.closed))
        self.assertEqual(self.asked, ["Soubor se mezitím změnil"])
        self.assertEqual(self.cmds(), ["get", "meta", "save", "get", "save"])
        params = self.client.calls[-1][1]
        self.assertEqual(params["mtime"], 150)
        self.assertEqual(params["changes"]["title"], "Nový název")
        self.assertEqual(params["changes"]["projects"], ["pesstudios", "Nový"])
        self.assertEqual(params["changes"]["body"], "tělo\n")  # formulář vyhrává

    def test_conflict_reload(self):
        f = self.make(save=VqdError("conflict"))
        f.title.set_text("Nový název")
        self.answer = "reload"
        f.save()
        self.assertTrue(pump(lambda: self.cmds().count("get") == 2 and not f.dirty()))
        self.assertEqual(f.title.get_text(), "Zavolat")
        f.close()

    def test_complete_dirty_saves_first(self):
        f = self.make(save={"mtime": 200}, complete={})
        f._set_date("2026-11-20")
        f.complete()
        self.assertTrue(pump(lambda: f.closed))
        self.assertEqual(self.cmds()[2:], ["save", "complete"])
        self.assertEqual(self.client.calls[-1][1]["expected"], "2026-11-20")

    def test_complete_clean(self):
        f = self.make(complete={})
        f.complete()
        self.assertTrue(pump(lambda: f.closed))
        self.assertEqual(self.client.calls[-1][1]["expected"], "2026-11-18")

    def test_delete_and_close_dirty(self):
        f = self.make(archive={})
        self.answer = "cancel"
        f.ask_delete()
        self.assertNotIn("archive", self.cmds())
        self.answer = "delete"
        f.ask_delete()
        self.assertTrue(pump(lambda: f.closed))
        self.assertEqual(self.client.calls[-1], ("archive", {"path": TASK["path"]}))
        g = self.make()
        g.body.get_buffer().set_text("změna")
        self.answer = "cancel"
        g.request_close()
        self.assertFalse(g.closed)
        self.answer = "discard"
        g.request_close()
        self.assertTrue(g.closed)

    def test_missing_on_load(self):
        from vqapplet import form
        c = FakeClient(get=VqdError("missing"), meta=META)
        f = form.TaskForm(c, "x.md", lambda: None)
        msgs = []
        f.message = lambda text, detail="": msgs.append(text)
        f.load()
        self.assertTrue(pump(lambda: f.closed))
        self.assertEqual(msgs, ["Úkol už neexistuje."])


if __name__ == "__main__":
    unittest.main()
