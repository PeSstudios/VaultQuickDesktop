import unittest
from datetime import date
import _path  # noqa
from vqapplet import fmt


class FmtTest(unittest.TestCase):
    T = date(2026, 11, 17)

    def test_day_heading(self):
        self.assertEqual(fmt.day_heading(date(2026, 11, 17), self.T), "Dnes · út 17. 11.")
        self.assertEqual(fmt.day_heading(date(2026, 11, 18), self.T), "Zítra · st 18. 11.")
        self.assertEqual(fmt.day_heading(date(2026, 11, 19), self.T), "čt 19. 11.")

    def test_weekday_date(self):
        self.assertEqual(fmt.weekday_date(date(2026, 11, 20)), "pá 20. 11.")

    def test_later_date(self):
        self.assertEqual(fmt.later_date(date(2026, 12, 4), self.T), "pá 4. 12.")
        self.assertEqual(fmt.later_date(date(2027, 1, 8), self.T), "pá 8. 1. 2027")

    def test_short_date(self):
        self.assertEqual(fmt.short_date(date(2026, 11, 15)), "15. 11.")

    def test_bar_label(self):
        self.assertEqual(fmt.bar_label("pesstudios", {"today": 3, "overdue": 2}),
                         ("pesstudios 3", "⚠2", False))
        self.assertEqual(fmt.bar_label("Vše", {"today": 0, "overdue": 0}), ("Vše 0", None, True))


if __name__ == "__main__":
    unittest.main()
