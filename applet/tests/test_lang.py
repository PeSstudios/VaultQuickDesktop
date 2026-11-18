import datetime, unittest
import _path  # noqa
from vqapplet import fmt, texts


class LangTest(unittest.TestCase):
    def test_detect_lang(self):
        d = texts.detect_lang
        self.assertEqual(d({"LANG": "cs_CZ.UTF-8"}), "cs")
        self.assertEqual(d({"LANG": "en_US.UTF-8"}), "en")
        self.assertEqual(d({"LANG": "de_DE.UTF-8"}), "en")
        self.assertEqual(d({}), "en")
        self.assertEqual(d({"LANG": "C"}), "en")
        self.assertEqual(d({"LANGUAGE": "cs:en", "LANG": "en_US.UTF-8"}), "cs")
        self.assertEqual(d({"LC_ALL": "en_GB.UTF-8", "LANG": "cs_CZ.UTF-8"}), "en")
        self.assertEqual(d({"VQ_LANG": "en", "LANG": "cs_CZ.UTF-8"}), "en")

    def test_tests_run_in_czech(self):
        self.assertEqual((texts.LANG, texts.TODAY), ("cs", "Dnes"))

    def test_english_dates(self):
        d = datetime.date(2026, 11, 18)
        self.assertEqual(fmt.short_date(d, "en"), "Nov 18")
        self.assertEqual(fmt.weekday_date(d, "en"), "Wed Nov 18")
        self.assertEqual(fmt.full_date(d, "en"), "Wed Nov 18, 2026")
        self.assertEqual(fmt.full_date(d, "cs"), "st 18. 11. 2026")


if __name__ == "__main__":
    unittest.main()
