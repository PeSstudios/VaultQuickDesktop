import datetime, unittest
import _path  # noqa
from vqapplet import logic


class LogicTest(unittest.TestCase):
    def test_parse_object_ids(self):
        out = "['menu-bar', 'object_8', 'object-0']\n"
        self.assertEqual(logic.parse_object_ids(out), ["menu-bar", "object_8", "object-0"])
        self.assertEqual(logic.parse_object_ids("@as []"), [])
        self.assertIsNone(logic.parse_object_ids(""))
        self.assertIsNone(logic.parse_object_ids("No such schema"))

    def test_live_keys(self):
        keys = {"/org/mate/panel/objects/object_8/prefs/", "/org/mate/panel/objects/object_9/prefs",
                "/org/mate/panel/objects/object_1/prefs/", "nesmysl"}
        live = logic.live_keys(keys, ["object_8", "object_9", "object_10"])
        self.assertEqual(live, {"/org/mate/panel/objects/object_8/prefs/",
                                "/org/mate/panel/objects/object_9/prefs"})
        self.assertEqual(logic.object_id_of("/org/mate/panel/objects/object-10/prefs/"), "object-10")

    def test_toggle_target(self):
        inst = [{"label": "pes", "project": "pesstudios"}, {"label": "Vše", "project": None},
                {"label": "Constelia", "project": "Constelia"}]
        self.assertEqual(logic.toggle_target(inst, ""), 1)
        self.assertEqual(logic.toggle_target(inst, "constelia"), 2)
        self.assertEqual(logic.toggle_target(inst, " PES "), 0)
        self.assertEqual(logic.toggle_target(inst, "neznámý"), 0)
        self.assertEqual(logic.toggle_target(inst[:1] + inst[2:], ""), 0)  # bez Vše → první
        self.assertIsNone(logic.toggle_target([], ""))
        self.assertIsNone(logic.toggle_target([], "x"))

    def test_midnight(self):
        now = datetime.datetime(2026, 11, 17, 23, 59, 0)
        self.assertEqual(logic.seconds_until_midnight(now), 65)
        now = datetime.datetime(2026, 12, 31, 0, 0, 0)
        self.assertEqual(logic.seconds_until_midnight(now, slack=0), 86400)

    def test_vqd_argv(self):
        self.assertEqual(logic.vqd_argv("/r/desktop/applet", env={"VQD_BIN": "/x/vqd"}), ["/x/vqd"])
        inst = "/h/.local/share/vaultquick-desktop/vqd/bin/vqd"
        self.assertEqual(logic.vqd_argv("/r/desktop/applet", env={}, home="/h",
                                        exists=lambda p: p == inst), [inst])
        self.assertEqual(logic.vqd_argv("/r/desktop/applet", env={}, home="/h",
                                        exists=lambda p: False),
                         ["/r/desktop/vqd/build/install/vqd/bin/vqd"])

    def test_obsidian_url(self):
        self.assertEqual(logic.obsidian_url("/home/p/MujVault/", "Pronájem Ořechov"),
                         "obsidian://open?vault=MujVault&file=Pron%C3%A1jem%20O%C5%99echov")
        self.assertEqual(logic.obsidian_url("/home/p/MujVault", None),
                         "obsidian://open?vault=MujVault&file=TaskNotes")

    def test_bar_markup(self):
        self.assertEqual(logic.bar_markup("A&B", {"today": 2, "overdue": 3}),
                         'A&amp;B 2 <span foreground="#e67e22">⚠3</span>')
        self.assertEqual(logic.bar_markup("Vše", {"today": 0, "overdue": 0}),
                         '<span alpha="50%">Vše 0</span>')
        self.assertEqual(logic.bar_markup("Vše", {"today": 1}), "Vše 1")

    def test_error_bar(self):
        self.assertEqual(logic.error_bar("vault")[0], "?")
        self.assertEqual(logic.error_bar("not_running"), ("…", "Pomocník neběží"))

    def test_popup_position(self):
        mon = (0, 0, 1920, 1080)
        # panel dole: okno nad appletem
        self.assertEqual(logic.popup_position("up", (100, 1050, 80, 30), (300, 400), mon), (100, 650))
        # panel nahoře
        self.assertEqual(logic.popup_position("down", (100, 0, 80, 30), (300, 400), mon), (100, 30))
        # u pravého okraje se okno posune doleva
        self.assertEqual(logic.popup_position("up", (1880, 1050, 40, 30), (300, 400), mon), (1620, 650))
        self.assertEqual(logic.popup_position("left", (1890, 500, 30, 80), (300, 400), mon), (1590, 500))
        self.assertEqual(logic.popup_position("right", (0, 900, 30, 80), (300, 400), mon), (30, 680))

    def test_defaults(self):
        self.assertEqual((logic.default_label(None), logic.default_no_date(None)), ("Vše", "inProgress"))
        self.assertEqual((logic.default_label("X"), logic.default_no_date("X")), ("X", "all"))


if __name__ == "__main__":
    unittest.main()
