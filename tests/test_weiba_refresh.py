"""微霸换号后刷新界面检测与导航辅助。"""

import unittest
import xml.etree.ElementTree as ET
from unittest.mock import MagicMock, patch

from core.weiba_refresh import (
    _foreground_package,
    _screen_ready,
    ensure_weiba_phone_and_refresh,
)


class WeibaRefreshTests(unittest.TestCase):
    def test_screen_ready_from_fixture(self) -> None:
        path = "fixtures/weiba_boot/step_03_weiba_account_list.xml"
        with open(path, "r", encoding="utf-8") as f:
            root = ET.fromstring(f.read())
        self.assertTrue(_screen_ready(root))

    def test_foreground_package_momo(self) -> None:
        xml = (
            '<hierarchy><node package="com.immomo.momo" '
            'text="消息" /></hierarchy>'
        )
        root = ET.fromstring(xml)
        self.assertEqual(_foreground_package(root), "com.immomo.momo")

    def test_ensure_weiba_presses_home_when_on_momo(self) -> None:
        momo_xml = (
            '<hierarchy><node package="com.immomo.momo" '
            'text="聊天" /></hierarchy>'
        )
        weiba_path = "fixtures/weiba_boot/step_03_weiba_account_list.xml"
        with open(weiba_path, "r", encoding="utf-8") as f:
            weiba_xml = f.read()

        driver = MagicMock()
        driver.d = MagicMock()
        driver.d.dump_hierarchy.side_effect = [momo_xml, weiba_xml]
        driver.d.press = MagicMock()

        elements = {
            "account_boot": {
                "launcher": {"weiba_icon": {"x": 741, "y": 311}},
                "weiba": {
                    "fenshen_tab": {"x": 403, "y": 2280},
                    "refresh_button": {"contentDesc": "刷新", "x": 104, "y": 165},
                },
            }
        }
        settings = {"delay": {"min": 0.01, "max": 0.02}}

        with patch("core.weiba_refresh._click_xy"), patch(
            "core.weiba_refresh._click_spec", return_value=True
        ):
            ok = ensure_weiba_phone_and_refresh(
                driver, elements, settings, max_steps=5
            )

        self.assertTrue(ok)
        driver.d.press.assert_any_call("home")


if __name__ == "__main__":
    unittest.main()
