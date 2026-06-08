"""Agent 初始化：serial 映射与 SET_CONFIG 命令拼装。"""

import unittest
from unittest.mock import patch

from ops.agent_init import (
    CONFIG_ACTION,
    CONFIG_RECEIVER,
    adb_serial_to_agent_serial,
    build_set_config_command,
    deploy_agent_config,
    deploy_many,
)


class AdbSerialMappingTests(unittest.TestCase):
    def test_colon_to_underscore(self) -> None:
        self.assertEqual(adb_serial_to_agent_serial("127.0.0.1:5555"), "127.0.0.1_5555")

    def test_emulator_unchanged(self) -> None:
        self.assertEqual(adb_serial_to_agent_serial("emulator-5556"), "emulator-5556")

    def test_already_normalized(self) -> None:
        self.assertEqual(adb_serial_to_agent_serial("127.0.0.1_5555"), "127.0.0.1_5555")


class BuildSetConfigCommandTests(unittest.TestCase):
    def test_broadcast_args(self) -> None:
        args = build_set_config_command(
            "emulator-5554",
            "ws://192.168.1.10:5100",
            "emulator-5554",
            autostart=True,
        )
        self.assertEqual(args[0:2], ["-s", "emulator-5554"])
        self.assertIn("broadcast", args)
        self.assertIn(CONFIG_ACTION, args)
        idx = args.index("--es")
        self.assertEqual(args[idx + 1], "master_url")
        self.assertEqual(args[idx + 2], "ws://192.168.1.10:5100")
        self.assertIn(CONFIG_RECEIVER, args)
        self.assertIn("true", args)

    def test_autostart_false(self) -> None:
        args = build_set_config_command(
            "127.0.0.1:5555",
            "ws://127.0.0.1:5100",
            "127.0.0.1_5555",
            autostart=False,
        )
        self.assertIn("false", args)


class DeployAgentConfigTests(unittest.TestCase):
    @patch("ops.agent_init.run_adb")
    def test_deploy_success(self, mock_run) -> None:
        mock_run.return_value = ("Broadcast completed", "", 0)
        result = deploy_agent_config(
            "127.0.0.1:5555",
            "ws://10.0.0.1:5100",
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["agent_serial"], "127.0.0.1_5555")
        mock_run.assert_called_once()
        called_args = mock_run.call_args[0][0]
        self.assertEqual(called_args[1], "127.0.0.1:5555")

    @patch("ops.agent_init.run_adb")
    def test_deploy_failure(self, mock_run) -> None:
        mock_run.return_value = ("", "error", 1)
        result = deploy_agent_config("emulator-5556", "ws://x:5100")
        self.assertFalse(result["ok"])
        self.assertIn("error", result)


class DeployManyTests(unittest.TestCase):
    @patch("ops.agent_init.deploy_agent_config")
    @patch("ops.agent_init.install_agent_apk")
    def test_deploy_many_without_apk(self, mock_install, mock_deploy) -> None:
        mock_deploy.side_effect = lambda adb, url, **kw: {
            "adb_serial": adb,
            "ok": True,
            "step": "config",
        }
        result = deploy_many(["a", "b"], "ws://1:5100", install_apk=False)
        self.assertEqual(result["success"], 2)
        mock_install.assert_not_called()
        self.assertEqual(mock_deploy.call_count, 2)


if __name__ == "__main__":
    unittest.main()
