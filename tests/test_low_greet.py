"""低招呼登记与检测逻辑。"""

import os
import tempfile
import time
import unittest
from unittest.mock import MagicMock, patch

import data.low_greet_registry as registry
import core.low_greet_watch as watch


class LowGreetRegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.mkdtemp()
        self._path = os.path.join(self._tmpdir, "low_greet_accounts.json")
        self._orig = registry._REGISTRY_PATH
        registry._REGISTRY_PATH = self._path

    def tearDown(self) -> None:
        registry._REGISTRY_PATH = self._orig

    def test_add_and_clear(self) -> None:
        self.assertTrue(registry.add_entry("a.zip", serial="s1", device_name="d1"))
        self.assertFalse(registry.add_entry("a.zip"))
        entries = registry.list_entries()
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["filename"], "a.zip")
        removed = registry.clear_all()
        self.assertEqual(removed, 1)
        self.assertEqual(registry.list_entries(), [])


class LowGreetWatchTests(unittest.TestCase):
    def test_reports_when_timeout_and_low_badge(self) -> None:
        storage = MagicMock()
        storage.get_device_state_flag.side_effect = lambda k, d=False: {
            "first_greet_batch_done": False,
            "low_greet_reported": False,
        }.get(k, d)
        storage.get_device_state_field.side_effect = lambda k, d=None: {
            "post_dynamic_at": time.time() - 400,
            "current_account_filename": "bad.acc",
        }.get(k, d)

        greeter = MagicMock()
        greeter.scan_badge.return_value = 1

        with patch.object(watch, "add_entry", return_value=True) as add_mock:
            ok = watch.maybe_report_low_greet(
                greeter=greeter,
                storage=storage,
                settings={"approve_greeting": {"first_batch_min_count": 3}},
                serial="dev1",
                device_name="phone",
            )
        self.assertTrue(ok)
        add_mock.assert_called_once()
        storage.set_device_state_flag.assert_called_with("low_greet_reported", True)

    def test_skips_when_badge_meets_threshold(self) -> None:
        storage = MagicMock()
        storage.get_device_state_flag.return_value = False
        storage.get_device_state_field.side_effect = lambda k, d=None: {
            "post_dynamic_at": time.time() - 400,
            "current_account_filename": "ok.acc",
        }.get(k, d)
        greeter = MagicMock()
        greeter.scan_badge.return_value = 5

        with patch.object(registry, "add_entry") as add_mock:
            ok = watch.maybe_report_low_greet(
                greeter=greeter,
                storage=storage,
                settings={"approve_greeting": {"first_batch_min_count": 3}},
                serial="dev1",
            )
        self.assertFalse(ok)
        add_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
