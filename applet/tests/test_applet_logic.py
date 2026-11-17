# Applet bez displeje: obnovení se stejnou agendou nepřestaví okno, chyby odškrtnutí ukážou hlášku.
# TaskApplet se nevytváří přes __init__ (žádné okno ani widget); pomocník je falešný.
import unittest
import _path  # noqa
from vqapplet import store
from vqapplet.client import VqdError

try:
    from vqapplet import applet
except (ImportError, ValueError) as e:  # bez gi / MatePanelApplet
    applet = None
    SKIP = f"applet nejde importovat: {e}"
else:
    SKIP = ""

AGENDA = {"overdue": [], "days": [{"date": "2026-11-17", "entries": []}], "noDate": [],
          "counts": {"today": 0, "overdue": 0}, "top": []}


class FakeClient:
    def __init__(self, answer):
        self.answer = answer
        self.calls = []

    def request(self, cmd, **params):
        self.calls.append((cmd, params))
        if isinstance(self.answer, Exception):
            raise self.answer
        return self.answer


@unittest.skipIf(applet is None, SKIP)
class AppletLogicTest(unittest.TestCase):
    def setUp(self):
        self._orig = (applet.run_async, applet.client, applet.refresh_all)
        applet.run_async = self._sync
        applet.refresh_all = lambda: None
        self.fake = FakeClient(dict(AGENDA))
        applet.client = lambda: self.fake
        t = applet.TaskApplet.__new__(applet.TaskApplet)
        t.applet = object()
        t.key = "test"
        t.agenda, t.agenda_today, t.error = None, None, None
        t._busy = t._again = False
        t.settings = lambda: store.with_defaults({})
        self.bar = self.render = 0
        self.messages = []
        t._update_bar = self._count_bar
        t._render_popup = self._count_render
        t._show_message = lambda text, detail="": self.messages.append((text, detail))
        t.open_task = lambda path: self.messages.append(("open", path))
        self.t = t

    def tearDown(self):
        applet.run_async, applet.client, applet.refresh_all = self._orig

    @staticmethod
    def _sync(fn, done):
        try:
            res, err = fn(), None
        except VqdError as e:
            res, err = None, e
        done(res, err)

    def _count_bar(self):
        self.bar += 1

    def _count_render(self):
        self.render += 1

    def _icon_setup(self, settings, answer):
        self.t.settings = lambda: store.with_defaults(settings)
        self.applied = []
        self.t._apply_icon = lambda: self.applied.append(self.t.icon_path)
        self.icon_answer = answer
        agenda_client = self.fake

        class Both:
            calls = agenda_client.calls

            def request(inner, cmd, **params):
                if cmd != "icon":
                    return agenda_client.request(cmd, **params)
                agenda_client.calls.append((cmd, params))
                if isinstance(self.icon_answer, Exception):
                    raise self.icon_answer
                return self.icon_answer
        applet.client = lambda: Both()

    def icon_calls(self):
        return [p for c, p in self.fake.calls if c == "icon"]

    def test_icon_auto_only_on_resolve_not_refresh(self):
        self._icon_setup({"project": "pesstudios"}, {"path": "g/i.png"})
        self.t.resolve_icon()
        self.assertEqual(self.icon_calls(), [{"project": "pesstudios"}])
        self.assertEqual(self.t.icon_path, "g/i.png")
        for _ in range(3):
            self.t.refresh()  # 60s obnovení – `icon` prochází celý vault, nevolat
        self.assertEqual(len(self.icon_calls()), 1)

    def test_icon_retry_after_helper_down(self):
        self._icon_setup({"project": "pesstudios"}, VqdError("not_running", "x"))
        self.t.resolve_icon()
        self.assertIsNone(self.t.icon_path)
        self.icon_answer = {"path": None}
        self.t.refresh()  # pomocník už běží → ikona se zjistí znovu (jen jednou)
        self.t.refresh()
        self.assertEqual(len(self.icon_calls()), 2)

    def test_icon_retry_at_most_once(self):
        self._icon_setup({"project": "pesstudios"}, VqdError("timeout", "x"))
        self.t.resolve_icon()
        for _ in range(3):
            self.t.refresh()  # pomocník pořád neodpovídá na `icon` → jen jedno opakování
        self.assertEqual(len(self.icon_calls()), 2)

    def test_icon_other_error_no_retry(self):
        self._icon_setup({"project": "pesstudios"}, VqdError("failed", "x"))
        self.t.resolve_icon()
        for _ in range(3):
            self.t.refresh()  # jiná chyba než výpadek → bez opakování
        self.assertEqual(len(self.icon_calls()), 1)

    def test_icon_none_path_and_all_without_request(self):
        self._icon_setup({"project": "pesstudios", "icon": "none"}, {"path": "x.png"})
        self.t.resolve_icon()
        self.assertIsNone(self.t.icon_path)
        self._icon_setup({"project": "pesstudios", "icon": "a/b.png"}, {"path": "x.png"})
        self.t.resolve_icon()
        self.assertEqual(self.t.icon_path, "a/b.png")
        self._icon_setup({}, {"path": "x.png"})  # Vše
        self.t.resolve_icon()
        self.assertIsNone(self.t.icon_path)
        self.assertEqual(self.icon_calls(), [])

    def test_identical_agenda_does_not_rerender(self):
        self.t.refresh()
        self.assertEqual((self.bar, self.render), (1, 1))
        self.t.refresh()  # 60s obnovení, stejná agenda
        self.t.refresh()
        self.assertEqual((self.bar, self.render), (1, 1))
        self.fake.answer = dict(AGENDA, counts={"today": 1, "overdue": 0})
        self.t.refresh()
        self.assertEqual((self.bar, self.render), (2, 2))

    def test_error_state_change_rerenders_once(self):
        self.t.refresh()
        self.fake.answer = VqdError("timeout")
        self.t.refresh()
        self.t.refresh()  # stejná chyba
        self.assertEqual(self.render, 2)
        self.fake.answer = dict(AGENDA)
        self.t.refresh()  # chyba zmizela, agenda stejná jako předtím → přestavět
        self.assertEqual(self.render, 3)

    def test_complete_errors_show_message(self):
        entry = {"path": "a.md", "date": "2026-11-17"}
        for code in ("not_running", "timeout", "bad_request", "missing", "vault"):
            self.messages.clear()
            self.fake.answer = VqdError(code)
            self.t.complete(entry)
            self.assertEqual(len(self.messages), 1, code)
            self.assertIn(code, self.messages[0][1])
        self.messages.clear()
        self.fake.answer = VqdError("stale")
        self.t.complete(entry)
        self.assertEqual(self.messages, [])
        self.fake.answer = VqdError("failed")
        self.t.complete(entry)
        self.assertEqual(self.messages, [("open", "a.md")])
        self.messages.clear()
        self.fake.answer = {}
        self.t.complete(entry)
        self.assertEqual(self.messages, [])


@unittest.skipIf(applet is None, SKIP)
class ClientSingletonTest(unittest.TestCase):
    def test_one_client_from_many_threads(self):
        import threading
        orig_client, orig_cls = applet._client, applet.Client
        made = []

        class Slow:
            def __init__(self, argv):
                import time
                time.sleep(0.05)  # bez zámku by si klienta vytvořila každá vlákna zvlášť
                made.append(self)
        applet._client, applet.Client = None, Slow
        try:
            got = []
            ths = [threading.Thread(target=lambda: got.append(applet.client())) for _ in range(5)]
            for th in ths:
                th.start()
            for th in ths:
                th.join()
            self.assertEqual(len(made), 1)
            self.assertTrue(all(g is made[0] for g in got))
        finally:
            applet._client, applet.Client = orig_client, orig_cls


if __name__ == "__main__":
    unittest.main()
