import datetime
import unittest

from lib.timer_display import format_countdown, format_session_elapsed


class TestFormatSessionElapsed(unittest.TestCase):
    def test_none_returns_dash(self):
        self.assertEqual(format_session_elapsed(None), "--")

    def test_empty_string_returns_dash(self):
        self.assertEqual(format_session_elapsed(""), "--")

    def test_invalid_string_returns_dash(self):
        self.assertEqual(format_session_elapsed("not-a-date"), "--")

    def test_known_elapsed(self):
        start = datetime.datetime.now() - datetime.timedelta(hours=2, minutes=15, seconds=30)
        result = format_session_elapsed(start.isoformat())
        self.assertEqual(result, "2h 15m")

    def test_known_elapsed_with_seconds(self):
        start = datetime.datetime.now() - datetime.timedelta(hours=2, minutes=15, seconds=30)
        result = format_session_elapsed(start.isoformat(), include_seconds=True)
        self.assertEqual(result, "2h 15m 30s")

    def test_zero_elapsed(self):
        start = datetime.datetime.now()
        result = format_session_elapsed(start.isoformat())
        self.assertEqual(result, "0h 0m")

    def test_large_elapsed(self):
        start = datetime.datetime.now() - datetime.timedelta(days=3, hours=5)
        result = format_session_elapsed(start.isoformat())
        self.assertEqual(result, "77h 0m")


class TestFormatCountdown(unittest.TestCase):
    def test_none_returns_unknown(self):
        self.assertEqual(format_countdown(None), "14d limit: unknown")

    def test_zero_returns_overdue(self):
        self.assertEqual(format_countdown(0), "! OVERDUE")

    def test_negative_returns_overdue(self):
        self.assertEqual(format_countdown(-3.5), "! OVERDUE")

    def test_normal_remaining(self):
        self.assertEqual(format_countdown(10.5), "~10d 12h left")

    def test_warning_threshold(self):
        result = format_countdown(1.5)
        self.assertEqual(result, "! ~1d 12h left")

    def test_exactly_two_days_triggers_warning(self):
        result = format_countdown(2.0)
        self.assertTrue(result.startswith("!"))

    def test_above_two_days_no_warning(self):
        result = format_countdown(2.1)
        self.assertFalse(result.startswith("!"))


if __name__ == "__main__":
    unittest.main()
