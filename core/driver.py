import base64
import hashlib
import logging
import os
import random
import re
import time
from typing import Optional, Tuple

import cv2
import numpy as np
import uiautomator2 as u2
import yaml
from uiautomator2.exceptions import AdbBroadcastError

# uiautomator2 内置 IME（与 ``InputMethodMixIn.__ime_id`` 一致）
_ADB_KEYBOARD_IME_ID = "com.github.uiautomator/.AdbKeyboard"
_BROADCAST_OK = -1

# 系统设置里 default_input_method 出现以下子串之一即视为当前为 u2 的 ADB Keyboard
_ADB_IME_ID_MARKERS = (
    "AdbKeyboard",
    "adbkeyboard",
    "github.uiautomator",
    "uiautomator",
)


class DeviceHandler:
    def __init__(self, config_path="config/settings.yaml"):
        # 加载配置
        with open(config_path, 'r', encoding='utf-8') as f:
            self.settings = yaml.safe_load(f)['config']

        # 连接设备
        self.d = u2.connect()
        logging.info("手机连接成功")
        self._ime_ready: Optional[bool] = None

    def invalidate_input_ime_cache(self) -> None:
        """清除 IME 就绪缓存，强制下次 ``ensure_input_ime_ready`` 重新检测并 ``set_input_ime``。

        在用户改回系统键盘、或 ``human_type`` / 广播注入异常后调用。
        """
        self._ime_ready = None

    def _default_input_method_line(self) -> str:
        try:
            r = self.d.shell(
                "settings get secure default_input_method", timeout=5
            )
            out = getattr(r, "output", None) or ""
            if isinstance(out, bytes):
                out = out.decode("utf-8", errors="replace")
            return str(out).strip()
        except Exception:
            logging.debug("读取 default_input_method 失败", exc_info=True)
            return ""

    def _line_looks_like_adb_keyboard(self, line: str) -> bool:
        if not line or line == "null":
            return False
        low = line.lower()
        return any(m.lower() in low for m in _ADB_IME_ID_MARKERS)

    def _current_ime_looks_like_adb_keyboard(self) -> bool:
        return self._line_looks_like_adb_keyboard(self._default_input_method_line())

    def _shell_text(self, r: object) -> str:
        out = getattr(r, "output", None) or ""
        if isinstance(out, bytes):
            out = out.decode("utf-8", errors="replace")
        return str(out).strip()

    def _adb_keyboard_package_installed(self) -> bool:
        """部分 OEM（如 ColorOS）禁止 ``ime list``，``is_input_ime_installed`` 恒假；用 ``pm path`` 兜底。"""
        try:
            r = self.d.shell("pm path com.github.uiautomator", timeout=5)
            return "package:" in self._shell_text(r)
        except Exception:
            logging.debug("pm path com.github.uiautomator 失败", exc_info=True)
            return False

    def _fallback_set_default_adb_keyboard(self) -> bool:
        """多策略切换 ADB Keyboard，适配雷电等限制 settings put 的模拟器。"""
        ime_id = _ADB_KEYBOARD_IME_ID
        # 策略 1：ime enable + ime set（雷电需要先 enable）
        try:
            self.d.shell(["ime", "enable", ime_id], timeout=5)
            time.sleep(0.3)
            self.d.shell(["ime", "set", ime_id], timeout=5)
            time.sleep(0.2 + random.uniform(0.0, 0.15))
            if self._line_looks_like_adb_keyboard(self._default_input_method_line()):
                return True
        except Exception:
            logging.debug("ime enable/set 失败，尝试 settings put 回退")

        # 策略 2：settings put secure default_input_method
        try:
            self.d.shell(
                ["settings", "put", "secure", "default_input_method", ime_id],
                timeout=5,
            )
            time.sleep(0.2 + random.uniform(0.0, 0.15))
            return self._line_looks_like_adb_keyboard(self._default_input_method_line())
        except Exception:
            logging.exception("fallback_set_default_adb_keyboard: 所有策略均失败")
            return False

    def _wait_default_input_is_adb_keyboard(self, timeout: float) -> bool:
        deadline = time.time() + max(0.5, float(timeout))
        while time.time() < deadline:
            if self._current_ime_looks_like_adb_keyboard():
                return True
            time.sleep(0.1 + random.uniform(0.0, 0.08))
        return False

    def _parse_broadcast_result(self, output: str) -> Tuple[Optional[int], Optional[str]]:
        m_r = re.search(r"result=(-?\d+)", output or "")
        m_d = re.search(r'data="([^"]*)"', output or "")
        code = int(m_r.group(1)) if m_r else None
        data = m_d.group(1) if m_d else None
        return code, data

    def _adb_keyboard_broadcast_input_text(self, text: str) -> None:
        """经 ``ADB_KEYBOARD_INPUT_TEXT`` 注入文本，绕过 ``d.send_keys``（其内会反复 ``set_input_ime`` / ``HIDE``）。"""
        if not text:
            return
        b64 = base64.b64encode(text.encode("utf-8")).decode("ascii")
        last_err: Optional[Exception] = None
        for attempt in range(3):
            try:
                time.sleep(random.uniform(0.05, 0.18))
                r = self.d.shell(
                    [
                        "am",
                        "broadcast",
                        "-a",
                        "ADB_KEYBOARD_INPUT_TEXT",
                        "--es",
                        "text",
                        b64,
                    ],
                    timeout=15,
                )
                out = self._shell_text(r)
                code, data = self._parse_broadcast_result(out)
                if code == _BROADCAST_OK:
                    return
                last_err = AdbBroadcastError(
                    f"ADB_KEYBOARD_INPUT_TEXT code={code} data={data!r} raw={out[:200]!r}"
                )
            except Exception as exc:
                last_err = exc
                logging.warning(
                    "adb_keyboard_broadcast_input_text 第 %d 次失败",
                    attempt + 1,
                    exc_info=True,
                )
            time.sleep(0.35 + random.uniform(0.0, 0.25))
        if last_err is not None:
            raise last_err
        raise AdbBroadcastError("ADB_KEYBOARD_INPUT_TEXT 失败且无异常信息")

    def ensure_input_ime_ready(self, timeout: float = 8.0) -> bool:
        """确保 ADB Keyboard（uiautomator2 IME）已被选为默认输入法。

        - 在 **ColorOS 等** 上 ``adb shell ime list`` 无权限时，u2 的 ``is_input_ime_installed`` /
          ``set_input_ime`` 会误判或断言失败；此时用 ``pm path`` 判断是否已安装，并用
          ``settings put secure default_input_method`` 回切。
        - 文本注入走广播 ``ADB_KEYBOARD_INPUT_TEXT``，不再调用 ``d.send_keys``，避免 OEM
          上 ``send_keys`` 内嵌的 ``set_input_ime`` 与每段输入后的 ``ADB_KEYBOARD_HIDE``。
        - 成功后会缓存；若缓存为真但系统默认 IME 已非 ADB Keyboard，会自动失效并重试。
        """
        if self._ime_ready is True:
            cur_line = self._default_input_method_line()
            if self._line_looks_like_adb_keyboard(cur_line):
                return True
            logging.warning(
                "ensure_input_ime_ready: 缓存已就绪但系统默认 IME 已变更 (%r)，将重新 set_input_ime",
                cur_line,
            )
            self.invalidate_input_ime_cache()
        try:
            if not (
                bool(self.d.is_input_ime_installed())
                or self._adb_keyboard_package_installed()
            ):
                logging.error(
                    "ensure_input_ime_ready: ADB Keyboard 未安装，请在手机里启用并选为默认输入法"
                )
                self._ime_ready = False
                return False
            if not self._current_ime_looks_like_adb_keyboard():
                try:
                    self.d.set_input_ime()
                except Exception:
                    logging.warning(
                        "ensure_input_ime_ready: set_input_ime 异常（常见于 OEM 禁止 ime list），"
                        "尝试 settings 回切 ADB Keyboard",
                        exc_info=True,
                    )
                    if not self._fallback_set_default_adb_keyboard():
                        self._ime_ready = False
                        return False
            ok = self._wait_default_input_is_adb_keyboard(float(timeout))
            if ok:
                self._ime_ready = True
                logging.info("ensure_input_ime_ready: ADB Keyboard 已就绪")
                return True
            logging.warning(
                "ensure_input_ime_ready: 等待 IME 就绪超时 timeout=%ss，可能尚未在系统设置选用 ADB Keyboard",
                timeout,
            )
            self._ime_ready = False
            return False
        except Exception:
            logging.exception("ensure_input_ime_ready 异常")
            self._ime_ready = False
            return False

    def _click_point_with_offset(self, x, y, skip_delay=False):
        offset_x = random.randint(
            -self.settings['click_offset']['x'],
            self.settings['click_offset']['x'],
        )
        offset_y = random.randint(
            -self.settings['click_offset']['y'],
            self.settings['click_offset']['y'],
        )
        self.d.click(x + offset_x, y + offset_y)
        if not skip_delay:
            time.sleep(
                random.uniform(
                    self.settings['delay']['min'],
                    self.settings['delay']['max'],
                )
            )

    def random_click_xy(self, x, y, skip_delay=False):
        """对屏幕坐标 (x, y) 做带随机偏移的点击与延迟。"""
        self._click_point_with_offset(x, y, skip_delay=skip_delay)

    def random_click(self, selector, skip_delay=False):
        """带随机偏移的点击"""
        el = self.d(resourceId=selector) if "id/" in selector else self.d(text=selector)
        if el.exists:
            x, y = el.center()
            self._click_point_with_offset(x, y, skip_delay=skip_delay)
            return True
        return False

    def click_uielement(self, el, skip_delay=False) -> bool:
        """对已存在的选择器结果做带随机偏移点击；el 为 uia2 的 UiObject。"""
        try:
            if not el.exists:
                return False
            x, y = el.center()
            self._click_point_with_offset(x, y, skip_delay=skip_delay)
            return True
        except Exception:
            logging.exception("click_uielement 异常")
            return False

    def is_keyboard_shown(self, input_box_rid: Optional[str] = None) -> bool:
        """检测软键盘是否可见。优先 dumpsys input_method；失败时用输入框 focused 降级。"""
        try:
            r = self.d.shell("dumpsys input_method", timeout=8)
            out = getattr(r, "output", None) or ""
            if isinstance(out, bytes):
                out = out.decode("utf-8", errors="replace")
            text = str(out)
            if "mInputShown=true" in text:
                return True
        except Exception:
            logging.debug("is_keyboard_shown: dumpsys 失败，尝试 focused 降级", exc_info=True)
        if input_box_rid:
            try:
                info = self.d(resourceId=input_box_rid).info
                if isinstance(info, dict) and info.get("focused"):
                    return True
            except Exception:
                logging.debug("is_keyboard_shown: focused 检查失败", exc_info=True)
        return False

    def swipe_scroll_down(self, duration=0.35):
        """手指自下向上滑，列表内容向下滑动，露出下方区域。"""
        w, h = self.d.window_size()
        x = int(w * 0.5) + random.randint(-self.settings['click_offset']['x'], self.settings['click_offset']['x'])
        y1 = int(h * 0.72)
        y2 = int(h * 0.32)
        self.d.swipe(x, y1, x, y2, duration)
        time.sleep(
            random.uniform(
                self.settings['delay']['min'],
                self.settings['delay']['max'],
            )
        )

    def wait_ui_stable(self, max_wait=1.2, poll=0.12):
        """等待 UI 静止：连续两次 dump_hierarchy 的 hash 一致即视为稳定。

        比固定 sleep 更精准：滑动/动画结束早就早返回；惯性长就多等一会，
        最多不超过 max_wait。返回 True 表示稳定；False 表示超时仍在变化。
        """
        deadline = time.time() + max_wait
        last = None
        while time.time() < deadline:
            try:
                xml = self.d.dump_hierarchy()
            except Exception:
                logging.debug("wait_ui_stable: dump_hierarchy 异常", exc_info=True)
                time.sleep(poll)
                continue
            h = hashlib.md5(xml.encode("utf-8")).hexdigest()
            if h == last:
                return True
            last = h
            time.sleep(poll)
        return False

    def capture_screen_bgr(self):
        """截取当前屏幕，返回 BGR 格式的 ndarray（供 OpenCV 使用）。"""
        pil_im = self.d.screenshot()
        return cv2.cvtColor(np.asarray(pil_im), cv2.COLOR_RGB2BGR)

    def find_image(self, template_path, threshold=0.8):
        """
        在当前屏幕中查找模板图，返回匹配中心点 (x, y)；未找到返回 None。
        template_path 可为绝对路径，或与当前工作目录相对的模板文件路径。
        """
        try:
            if not os.path.isfile(template_path):
                logging.error("模板文件不存在: %s", template_path)
                return None

            screen = self.capture_screen_bgr()
            template = cv2.imread(template_path)
            if template is None:
                logging.error("模板图无法读取: %s", template_path)
                return None

            return self._match_template_on_screen(screen, template_path, template, threshold)
        except Exception:
            logging.exception("find_image 执行异常: %s", template_path)
            return None

    def _match_template_on_screen(self, screen_bgr, template_path, template, threshold):
        th, tw = template.shape[:2]
        sh, sw = screen_bgr.shape[:2]
        if th > sh or tw > sw:
            logging.warning("模板尺寸大于屏幕: %s", template_path)
            return None

        res = cv2.matchTemplate(screen_bgr, template, cv2.TM_CCOEFF_NORMED)
        _min_val, max_val, _min_loc, max_loc = cv2.minMaxLoc(res)
        if max_val < threshold:
            logging.info(
                "未找到匹配模板(阈值 %.2f, 最高得分 %.3f): %s",
                threshold,
                max_val,
                template_path,
            )
            return None

        top_x, top_y = max_loc
        cx = top_x + tw // 2
        cy = top_y + th // 2
        logging.info(
            "模板匹配成功: %s 中心(%d,%d) 得分 %.3f",
            template_path,
            cx,
            cy,
            max_val,
        )
        return (cx, cy)

    def find_image_on_screen(self, screen_bgr, template_path, threshold=0.8):
        """在已有截屏 ndarray 上查找模板，避免重复截图。"""
        try:
            if not os.path.isfile(template_path):
                logging.error("模板文件不存在: %s", template_path)
                return None
            template = cv2.imread(template_path)
            if template is None:
                logging.error("模板图无法读取: %s", template_path)
                return None
            return self._match_template_on_screen(screen_bgr, template_path, template, threshold)
        except Exception:
            logging.exception("find_image_on_screen 执行异常: %s", template_path)
            return None

    def click_image(self, template_path, threshold=0.8):
        """在屏幕中查找模板并带随机偏移点击；成功返回 True。"""
        pos = self.find_image(template_path, threshold=threshold)
        if pos is None:
            return False
        self._click_point_with_offset(pos[0], pos[1])
        return True

    def human_type(self, text, chunk_size=3):
        """模拟真人输入：每批 chunk_size 个字符，批次间随机间隔。

        经 ``ADB_KEYBOARD_INPUT_TEXT`` 广播写入，避免 u2 ``send_keys`` 在部分 OEM 上
        因 ``ime list`` 无权限而反复 ``set_input_ime`` 失败，并避免每段后的
        ``ADB_KEYBOARD_HIDE`` 打断连续输入。未就绪时抛 ``RuntimeError``，不回落到
        ``d(focused=True).set_text`` 以免误触软键盘。
        """
        if not text:
            return
        if not self.ensure_input_ime_ready():
            raise RuntimeError(
                "ADB Keyboard 未就绪，已拒绝 send_keys 以避免软键盘点击回退"
            )
        for i in range(0, len(text), chunk_size):
            chunk = text[i : i + chunk_size]
            if not chunk:
                continue
            try:
                if not self._current_ime_looks_like_adb_keyboard():
                    if not self.ensure_input_ime_ready():
                        raise RuntimeError(
                            "ADB Keyboard 已非默认输入法且无法切回，已拒绝注入以避免误触软键盘"
                        )
                self._adb_keyboard_broadcast_input_text(chunk)
            except Exception:
                logging.exception(
                    "human_type: ADB_KEYBOARD_INPUT_TEXT 失败 chunk=%r，已清除 IME 缓存",
                    chunk,
                )
                self.invalidate_input_ime_cache()
                raise
            time.sleep(random.uniform(0.1, 0.3))
