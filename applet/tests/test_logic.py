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

    def test_obsidian_file_url(self):
        self.assertEqual(logic.obsidian_file_url("/home/p/MujVault", "1 projekty/Plán č. 1.md"),
                         "obsidian://open?vault=MujVault&file=1%20projekty%2FPl%C3%A1n%20%C4%8D.%201.md")

    def test_open_target(self):
        v = "/home/p/MujVault"
        # výchozí: stránka projektu (Vše → TaskNotes) v Obsidianu
        self.assertEqual(logic.open_target({"project": "pesstudios"}, v),
                         ("file", logic.obsidian_url(v, "pesstudios")))
        self.assertEqual(logic.open_target({"project": None, "openKind": "file", "openFile": ""}, v),
                         ("file", logic.obsidian_url(v, None)))
        self.assertEqual(logic.open_target({"project": "X", "openFile": "a/b.md"}, v),
                         ("file", logic.obsidian_file_url(v, "a/b.md")))
        # složka: vybraná (i s ~), jinak kořen vaultu
        self.assertEqual(logic.open_target({"openKind": "folder", "openFolder": "/srv/x"}, v),
                         ("folder", "/srv/x"))
        self.assertEqual(logic.open_target({"openKind": "folder", "openFolder": ""}, v),
                         ("folder", v))
        self.assertEqual(logic.open_target({"openKind": "folder", "openFolder": "~/Doc"}, v,
                                           home="/home/p"), ("folder", "/home/p/Doc"))
        # neznámý druh → soubor
        self.assertEqual(logic.open_target({"project": "X", "openKind": "?"}, v)[0], "file")

    def test_open_icons(self):
        # první ikona, kterou téma má, se použije (Obsidian / složka), poslední je záloha
        self.assertEqual(logic.open_icons({"project": "X"})[0], "obsidian")
        self.assertEqual(logic.open_icons({"openKind": "folder"})[0], "folder")

    def test_open_description(self):
        self.assertEqual(logic.open_description({"project": "pesstudios"}),
                         "Otevřít v Obsidianu: stránka projektu pesstudios")
        self.assertEqual(logic.open_description({"project": None}),
                         "Otevřít v Obsidianu: stránka TaskNotes")
        self.assertEqual(logic.open_description({"openFile": "a/b.md"}),
                         "Otevřít v Obsidianu: a/b.md")
        self.assertEqual(logic.open_description({"openKind": "folder", "openFolder": "/srv/x"}),
                         "Otevřít složku: /srv/x")
        self.assertEqual(logic.open_description({"openKind": "folder"}),
                         "Otevřít složku: kořen vaultu")

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


class IconTest(unittest.TestCase):
    def test_icon_source(self):
        self.assertEqual(logic.icon_source({"icon": "auto"}), ("auto", None))
        self.assertEqual(logic.icon_source({}), ("auto", None))
        self.assertEqual(logic.icon_source({"icon": "none"}), ("none", None))
        self.assertEqual(logic.icon_source({"icon": "a/b.png"}), ("path", "a/b.png"))
        self.assertEqual(logic.icon_source({"icon": ""}), ("auto", None))
        self.assertEqual(logic.icon_source({"icon": None}), ("auto", None))

    def test_vault_relative(self):
        self.assertEqual(logic.vault_relative("/v", "/v/a/b.png"), "a/b.png")
        self.assertEqual(logic.vault_relative("/v/", "/v/b.png"), "b.png")
        self.assertIsNone(logic.vault_relative("/v", "/jinde/x.png"))
        self.assertIsNone(logic.vault_relative("/v", "/v2/x.png"))
        self.assertIsNone(logic.vault_relative("/v", "/v"))
        self.assertIsNone(logic.vault_relative("/v", "/v/../x.png"))

    def test_vault_relative_symlink(self):
        import os, tempfile
        with tempfile.TemporaryDirectory() as d:
            real = os.path.join(d, "real")
            os.makedirs(os.path.join(real, "g"))
            open(os.path.join(real, "g", "i.png"), "w").close()
            link = os.path.join(d, "odkaz")
            os.symlink(real, link)
            # vault přes symlink, soubor vybraný skutečnou cestou (a naopak)
            self.assertEqual(logic.vault_relative(link, os.path.join(real, "g", "i.png")), "g/i.png")
            self.assertEqual(logic.vault_relative(real, os.path.join(link, "g", "i.png")), "g/i.png")

    def test_icon_abs(self):
        self.assertEqual(logic.icon_abs("/v", "a/b.png"), "/v/a/b.png")
        self.assertIsNone(logic.icon_abs("/v", None))
        self.assertIsNone(logic.icon_abs("/v", ""))

    def test_is_image(self):
        for name in ("a.png", "B.JPG", "c.jpeg", "d.gif", "e.webp", "f.SVG", "g.bmp"):
            self.assertTrue(logic.is_image(name), name)
        for name in ("a.md", "png", "b.png.txt", ""):
            self.assertFalse(logic.is_image(name), name)

    def test_icon_box(self):
        # vodorovná lišta: výška = velikost lišty − 4 (šířka podle poměru stran), aspoň 12
        self.assertEqual(logic.icon_box(24, vertical=False), (-1, 20))
        self.assertEqual(logic.icon_box(10, vertical=False), (-1, 12))
        # svislá lišta: omezuje šířka
        self.assertEqual(logic.icon_box(48, vertical=True), (44, -1))

    def test_show_label(self):
        self.assertTrue(logic.show_label({"showLabel": False}, False))
        self.assertTrue(logic.show_label({"showLabel": True}, False))
        self.assertFalse(logic.show_label({"showLabel": False}, True))
        self.assertTrue(logic.show_label({"showLabel": True}, True))
        self.assertFalse(logic.show_label({}, True))

    def test_bar_markup_without_label(self):
        m = logic.bar_markup("pes", {"today": 3, "overdue": 2}, with_label=False)
        self.assertEqual(m, '3 <span foreground="#e67e22">⚠2</span>')
        self.assertNotIn("pes", m)
        self.assertEqual(logic.bar_markup("pes", {"today": 0, "overdue": 0}, with_label=False),
                         '<span alpha="50%">0</span>')
        self.assertEqual(logic.bar_markup("pes", {"today": 1}, with_label=True), "pes 1")

    def test_bar_markup_without_counts(self):
        # bez počtů: jen popisek, ani ⚠ u zpožděných
        self.assertEqual(logic.bar_markup("pes", {"today": 3, "overdue": 2}, with_counts=False),
                         "pes")
        self.assertEqual(logic.bar_markup("pes", {"today": 3}, with_counts=False), "pes")
        self.assertEqual(logic.bar_markup("pes", {"today": 0, "overdue": 0}, with_counts=False),
                         '<span alpha="50%">pes</span>')
        # vedle ikony bez popisku i bez počtů → prázdné (jen ikona)
        for counts in ({"today": 3}, {"overdue": 1}, {}):
            self.assertEqual(logic.bar_markup("pes", counts, with_label=False,
                                              with_counts=False), "")

    def test_bar_tooltip_starts_with_label(self):
        self.assertEqual(logic.bar_tooltip("pes", ["A", "B"]), "pes\nA\nB")
        self.assertEqual(logic.bar_tooltip("pes", []), "pes")
        self.assertEqual(logic.bar_tooltip("pes", None), "pes")


class RefreshAndCompleteTest(unittest.TestCase):
    def test_refresh_changed(self):
        from vqapplet.client import VqdError
        a = {"counts": {"today": 1}, "days": []}
        self.assertFalse(logic.refresh_changed(a, None, dict(a), None))
        self.assertTrue(logic.refresh_changed(None, None, a, None))
        self.assertTrue(logic.refresh_changed(a, None, {"counts": {"today": 2}, "days": []}, None))
        self.assertTrue(logic.refresh_changed(a, None, a, VqdError("timeout")))
        self.assertFalse(logic.refresh_changed(a, VqdError("timeout"), a, VqdError("timeout")))
        self.assertTrue(logic.refresh_changed(a, VqdError("timeout"), a, VqdError("vault")))

    def test_complete_error_message(self):
        from vqapplet import texts
        for code in (None, "stale", "failed"):
            self.assertIsNone(logic.complete_error_message(code))
        self.assertEqual(logic.complete_error_message("timeout"), texts.COMPLETE_TIMEOUT)
        self.assertEqual(logic.complete_error_message("not_running"), texts.COMPLETE_HELPER_DOWN)
        self.assertEqual(logic.complete_error_message("vault"), texts.COMPLETE_VAULT)
        self.assertEqual(logic.complete_error_message("missing"), texts.COMPLETE_MISSING)
        self.assertEqual(logic.complete_error_message("bad_request"), texts.COMPLETE_FAILED)

if __name__ == "__main__":
    unittest.main()
