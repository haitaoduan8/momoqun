"""SessionRound 三段式流水线测试。"""

import unittest
from unittest.mock import MagicMock, patch

from core.pipeline import Phase, SessionRound


class SessionRoundTests(unittest.TestCase):
    def _make_round(self) -> SessionRound:
        driver = MagicMock()
        storage = MagicMock()
        storage.get_all_friends.return_value = {}
        storage.get_device_state_flag.return_value = False
        settings = {
            "group_name": "测试群",
            "round_end_wait_s": 0,
            "approve_greeting": {"first_batch_min_count": 3},
        }
        return SessionRound(
            driver=driver,
            elements={},
            settings=settings,
            storage=storage,
            serial="test_serial",
        )

    def test_execute_one_round_calls_three_steps(self) -> None:
        sr = self._make_round()
        with patch.object(sr, "_step_approve_greetings") as approve, patch.object(
            sr, "_step_invite_to_group"
        ) as invite, patch.object(sr, "_phase4_wait") as wait:
            sr.execute_one_round()
        approve.assert_called_once()
        invite.assert_called_once()
        wait.assert_called_once()
        self.assertEqual(sr.round_number, 1)

    def test_step_approve_skips_when_first_batch_below_threshold(self) -> None:
        sr = self._make_round()
        sr.greeter.scan_badge = MagicMock(return_value=2)
        sr.greeter.enter_sayhi_list = MagicMock(return_value=True)
        with patch(
            "core.pipeline.ensure_on_chat_list",
            return_value=True,
        ):
            sr._step_approve_greetings()
        sr.greeter.enter_sayhi_list.assert_not_called()

    def test_step_approve_enters_when_first_batch_meets_threshold(self) -> None:
        sr = self._make_round()
        sr.greeter.scan_badge = MagicMock(return_value=3)
        sr.greeter.enter_sayhi_list = MagicMock(return_value=True)
        sr.greeter.approve_one = MagicMock(return_value=None)
        sr.greeter.go_back_to_chat_list = MagicMock(return_value=True)
        with patch(
            "core.pipeline.ensure_on_chat_list",
            return_value=True,
        ):
            sr._step_approve_greetings()
        sr.greeter.enter_sayhi_list.assert_called_once()

    def test_step_invite_to_group_without_block(self) -> None:
        sr = self._make_round()
        sr._approved_this_round = [("alice", "Alice")]
        with patch.object(sr, "_batch_invite_friends", return_value=1) as batch_invite:
            sr._step_invite_to_group()
        batch_invite.assert_called_once_with(["Alice"])
        sr.storage.mark_status.assert_called_once_with("alice", "done", name="Alice")
        sr.storage.set_device_state_flag.assert_any_call(
            "first_greet_batch_done", True
        )
        sr.storage.set_device_state_flag.assert_any_call("has_ever_invited", True)
        self.assertEqual(sr.friends_processed_this_round, 1)

    def test_phase_labels_simplified(self) -> None:
        self.assertEqual(Phase.APPROVING, "APPROVING")
        self.assertEqual(Phase.INVITING_TO_GROUP, "INVITING_TO_GROUP")
        self.assertFalse(hasattr(Phase, "CHATTING"))


if __name__ == "__main__":
    unittest.main()
