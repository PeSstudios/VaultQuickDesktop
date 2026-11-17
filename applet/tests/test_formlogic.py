import unittest
import _path  # noqa
from vqapplet import formlogic as fl, logic

TASK = {"path": "0 vyřídit/Zavolat.md", "title": "Zavolat", "date": "2026-11-18", "time": "09:00",
        "status": "open", "priority": "normal", "projects": ["pesstudios", "Littera"],
        "contexts": ["telefon"], "recurrence": None}


class FormLogicTest(unittest.TestCase):
    def test_parse_time(self):
        self.assertIsNone(fl.parse_time(""))
        self.assertIsNone(fl.parse_time("  "))
        self.assertIsNone(fl.parse_time(None))
        self.assertEqual(fl.parse_time("9:05"), "09:05")
        self.assertEqual(fl.parse_time(" 14:30 "), "14:30")
        self.assertEqual(fl.parse_time("7.15"), "07:15")
        for bad in ("24:00", "12:60", "12", "ab:cd", "12:3", "1:2:3"):
            with self.assertRaises(ValueError, msg=bad):
                fl.parse_time(bad)

    def test_merge_projects(self):
        self.assertEqual(fl.merge_projects(["a", "b", "c"], "x"), ["x", "b", "c"])
        self.assertEqual(fl.merge_projects(["a", "b"], None), ["b"])
        self.assertEqual(fl.merge_projects(["a", "b"], ""), ["b"])
        self.assertEqual(fl.merge_projects([], "x"), ["x"])
        self.assertEqual(fl.merge_projects([], None), [])
        # vybraný projekt, který už je mezi ostatními, se nezdvojí
        self.assertEqual(fl.merge_projects(["a", "B", "c"], "b"), ["b", "c"])
        self.assertEqual(fl.merge_projects(["a", "b"], "a"), ["a", "b"])

    def test_with_current(self):
        self.assertEqual(fl.with_current(["open", "done"], "open"), ["open", "done"])
        self.assertEqual(fl.with_current(["open", "done"], "waiting"), ["waiting", "open", "done"])
        self.assertEqual(fl.with_current(None, ""), [])

    def test_initial_and_dirty(self):
        init = fl.initial_values(TASK, "tělo\n")
        self.assertEqual(init, {"title": "Zavolat", "date": "2026-11-18", "time": "09:00",
                                "status": "open", "priority": "normal", "project": "pesstudios",
                                "body": "tělo\n"})
        self.assertFalse(fl.is_dirty(init, dict(init)))
        self.assertFalse(fl.is_dirty(init, dict(init, title=" Zavolat ")))
        self.assertTrue(fl.is_dirty(init, dict(init, title="Jinak")))
        self.assertTrue(fl.is_dirty(init, dict(init, date=None)))
        self.assertTrue(fl.is_dirty(init, dict(init, project=None)))
        self.assertTrue(fl.is_dirty(init, dict(init, body="jiné")))
        # bez termínu se čas nepočítá
        nodate = fl.initial_values(dict(TASK, date=None, time=None, projects=[]), "")
        self.assertEqual((nodate["time"], nodate["project"]), ("", None))
        self.assertFalse(fl.is_dirty(nodate, dict(nodate, time="10:00", project="")))

    def test_build_changes(self):
        values = dict(fl.initial_values(TASK, "b"), title="  Nový  ", time="7:05",
                      project="Constelia", status="in-progress")
        c = fl.build_changes(TASK, values)
        self.assertEqual(c, {"title": "Nový", "date": "2026-11-18", "time": "07:05",
                             "status": "in-progress", "priority": "normal",
                             "projects": ["Constelia", "Littera"], "contexts": ["telefon"],
                             "body": "b"})
        # bez termínu → bez času (i když pole Čas něco obsahuje), prázdný název → původní
        c = fl.build_changes(TASK, dict(values, date=None, time="xx", title=" ", project=None))
        self.assertEqual((c["date"], c["time"], c["title"], c["projects"]),
                         (None, None, "Zavolat", ["Littera"]))
        c = fl.build_changes(TASK, dict(values, time=""))
        self.assertIsNone(c["time"])
        with self.assertRaises(ValueError):
            fl.build_changes(TASK, dict(values, time="25:00"))
        self.assertEqual(fl.build_changes(dict(TASK, contexts=None), values)["contexts"], [])

    def test_labels(self):
        self.assertEqual(fl.date_label("2026-11-18"), "st 18. 11. 2026")
        self.assertEqual(fl.date_label(None), "Bez termínu")
        self.assertEqual(fl.recurrence_label("FREQ=WEEKLY"), "🔁 FREQ=WEEKLY")
        self.assertIsNone(fl.recurrence_label(None))

    def test_quick_create(self):
        self.assertIsNone(fl.quick_create_params("   ", "2026-11-18", "x"))
        self.assertEqual(fl.quick_create_params(" Koupit mléko ", "2026-11-18", "pesstudios"),
                         {"text": "Koupit mléko", "date": "2026-11-18", "project": "pesstudios"})
        self.assertEqual(fl.quick_create_params("a", "2026-11-18", None)["project"], None)
        # ＋ u Bez termínu: úkol bez data
        self.assertEqual(fl.quick_create_params("Úkol", None, "pesstudios"),
                         {"text": "Úkol", "date": None, "project": "pesstudios"})

    def test_obsidian_file_url(self):
        self.assertEqual(fl.obsidian_file_url("/home/p/MujVault/", "0 vyřídit/Zavolat & co.md"),
                         "obsidian://open?vault=MujVault&file=0%20vy%C5%99%C3%ADdit%2FZavolat%20%26%20co")
        self.assertEqual(fl.obsidian_file_url("/v/Moje Vault", "a.MD"),
                         "obsidian://open?vault=Moje%20Vault&file=a")

    def test_font_css(self):
        self.assertEqual(logic.font_css(11),
                         ("vq-font-11", ".vq-font-11, .vq-font-11 * { font-size: 11pt; }"))
        self.assertEqual(logic.font_css(10.5)[0], "vq-font-10_5")


class CreateWarningTest(unittest.TestCase):
    def test_create_warning(self):
        from vqapplet import texts
        params = fl.quick_create_params("Úkol", "2026-11-18", "smazaný")
        self.assertEqual(fl.create_warning(params, {"path": "x.md", "project": None}),
                         texts.CREATE_NO_PROJECT.format(name="smazaný"))
        self.assertIn("„smazaný“", fl.create_warning(params, {"path": "x.md"}))
        self.assertIsNone(fl.create_warning(params, {"path": "x.md", "project": "Smazaný"}))
        self.assertIsNone(fl.create_warning(fl.quick_create_params("Úkol", None, None),
                                            {"path": "x.md", "project": None}))

if __name__ == "__main__":
    unittest.main()
