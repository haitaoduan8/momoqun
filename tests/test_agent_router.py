"""AgentRouter 工具方法测试。"""

import unittest

from agent_router import AgentRouter


class AgentRouterTests(unittest.TestCase):
    def test_normalize_serial(self) -> None:
        self.assertEqual(AgentRouter.normalize_serial("127.0.0.1:5555"), "127.0.0.1_5555")
        self.assertEqual(AgentRouter.normalize_serial("127.0.0.1_5555"), "127.0.0.1_5555")
        self.assertEqual(AgentRouter.normalize_serial(" emu-1 "), "emu-1")


if __name__ == "__main__":
    unittest.main()
