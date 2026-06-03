"""auth 模块单元测试。"""

import os
import unittest

from auth import (
    auth_enabled,
    auth_status_payload,
    load_security_config,
    verify_token,
)


class AuthTests(unittest.TestCase):
    def setUp(self) -> None:
        os.environ.pop("MOMOQUN_API_TOKEN", None)
        load_security_config({})

    def test_disabled_when_empty(self) -> None:
        self.assertFalse(auth_enabled())
        self.assertTrue(verify_token(None))
        self.assertTrue(verify_token("anything"))

    def test_enabled_from_settings(self) -> None:
        load_security_config({"security": {"api_token": "secret-token"}})
        self.assertTrue(auth_enabled())
        self.assertTrue(verify_token("secret-token"))
        self.assertFalse(verify_token("wrong"))
        self.assertFalse(verify_token(None))

    def test_env_overrides_settings(self) -> None:
        os.environ["MOMOQUN_API_TOKEN"] = "env-token"
        load_security_config({"security": {"api_token": "yaml-token"}})
        self.assertTrue(verify_token("env-token"))
        self.assertFalse(verify_token("yaml-token"))
        os.environ.pop("MOMOQUN_API_TOKEN", None)

    def test_status_payload(self) -> None:
        load_security_config({"security": {"allow_shell_exec": True, "heartbeat_timeout_sec": 45}})
        payload = auth_status_payload()
        self.assertIn("auth_required", payload)
        self.assertTrue(payload["shell_exec_allowed"])
        self.assertEqual(payload["heartbeat_timeout_sec"], 45.0)


if __name__ == "__main__":
    unittest.main()
