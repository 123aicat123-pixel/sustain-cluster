"""Reproduce December initialization fix without shifting previously valid cohorts."""
import unittest
from datetime import date

from research.calendar_index_guard import correct_overflowed_init_day


class CalendarIndexGuardTests(unittest.TestCase):
    def test_preserves_legacy_scenarios(self):
        for month, day, legacy in ((1, 20, 50), (4, 15, 137),
                                   (5, 19, 171), (6, 15, 198),
                                   (11, 12, 347)):
            with self.subTest(month=month):
                self.assertEqual(
                    correct_overflowed_init_day(legacy, year=2023,
                                                month=month, day=day),
                    (legacy, False),
                )

    def test_december_overflow_uses_exact_day_of_year(self):
        day_index = date(2023, 12, 10).timetuple().tm_yday - 1
        self.assertEqual(
            correct_overflowed_init_day(376, year=2023, month=12, day=10),
            (day_index, True),
        )
        self.assertLessEqual(day_index, 364)

    def test_never_silently_wraps_nonrepresentable_leap_day(self):
        with self.assertRaisesRegex(ValueError, "not representable"):
            correct_overflowed_init_day(999, year=2024, month=12, day=31)

    def test_reject_invalid_calendar_or_noninteger_index(self):
        with self.assertRaises(ValueError):
            correct_overflowed_init_day(375, year=2023, month=2, day=30)
        with self.assertRaises(TypeError):
            correct_overflowed_init_day(True, year=2023, month=12, day=10)


if __name__ == "__main__":
    unittest.main()
