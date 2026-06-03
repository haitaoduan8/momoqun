"""配置深合并测试。"""

import unittest

from utils.config_merge import deep_merge


class ConfigMergeTests(unittest.TestCase):
    def test_shallow_merge(self) -> None:
        base = {"a": 1, "b": 2}
        merged = deep_merge(base, {"b": 3, "c": 4})
        self.assertEqual(merged, {"a": 1, "b": 3, "c": 4})
        self.assertEqual(base["b"], 2)

    def test_nested_merge(self) -> None:
        base = {"security": {"api_token": "old", "allow_shell_exec": False}}
        merged = deep_merge(base, {"security": {"api_token": "new"}})
        self.assertEqual(merged["security"]["api_token"], "new")
        self.assertFalse(merged["security"]["allow_shell_exec"])


if __name__ == "__main__":
    unittest.main()
