"""发动态后无招呼直接换号等待逻辑。"""

import time
import unittest
from unittest.mock import MagicMock

from core.post_dynamic_idle import _post_dynamic_swap_minutes, wait_after_post_dynamic_no_greet


class PostDynamicIdleTests(unittest.TestCase):
    def test_swap_minutes_zero_disables(self) -> None:
        settings = {"account_check": {"post_dynamic_no_greet_swap_minutes": 0}}
        self.assertEqual(_post_dynamic_swap_minutes(settings), 0.0)

        greeter = MagicMock()
        storage = MagicMock()
        storage.get_device_state_field.return_value = time.time()
        on_swap = MagicMock()

        wait_after_post_dynamic_no_greet(
            greeter=greeter,
            storage=storage,
            settings=settings,
            should_stop=lambda: False,
            should_pause=lambda: False,
            on_swap_account=on_swap,
        )
        on_swap.assert_not_called()
        greeter.scan_badge.assert_not_called()

    def test_triggers_swap_after_deadline(self) -> None:
        settings = {
            "account_check": {"post_dynamic_no_greet_swap_minutes": 0.001},
            "greet_scan_interval_s": 0.01,
        }
        greeter = MagicMock()
        greeter.scan_badge.return_value = 0
        storage = MagicMock()
        storage.get_device_state_field.return_value = time.time() - 120
        on_swap = MagicMock(return_value=True)

        wait_after_post_dynamic_no_greet(
            greeter=greeter,
            storage=storage,
            settings=settings,
            should_stop=lambda: False,
            should_pause=lambda: False,
            on_swap_account=on_swap,
        )
        on_swap.assert_called_once_with("发动态后无招呼")


if __name__ == "__main__":
    unittest.main()
