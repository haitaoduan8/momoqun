"""微霸换号后刷新界面检测。"""

import unittest
import xml.etree.ElementTree as ET

from core.weiba_refresh import _screen_ready


class WeibaRefreshTests(unittest.TestCase):
    def test_screen_ready_from_fixture(self) -> None:
        path = "fixtures/weiba_boot/step_03_weiba_account_list.xml"
        with open(path, "r", encoding="utf-8") as f:
            root = ET.fromstring(f.read())
        self.assertTrue(_screen_ready(root))


if __name__ == "__main__":
    unittest.main()
