"""Windows EXE 启动脚本。
启动 FastAPI 服务器（后台线程）+ Flet 桌面窗口。
"""

from multiprocessing import freeze_support
import io
import os
import subprocess
import sys


# --- 确保 stdout/stderr 永不为 None（console=False 兼容）---
class _NullIO(io.RawIOBase):
    def write(self, b): return len(b) if b else 0
    def read(self, n=-1): return b""
    def readable(self): return True
    def writable(self): return True
    def seekable(self): return True
    def seek(self, offset, whence=0): return 0
    def truncate(self, size=None): return 0
    def tell(self): return 0
    def isatty(self): return False

if sys.stdout is None:
    sys.stdout = io.TextIOWrapper(_NullIO())
if sys.stderr is None:
    sys.stderr = io.TextIOWrapper(_NullIO())

import atexit
import threading
import time

_FLAGS = 0x08000000 if sys.platform == "win32" else 0
_adb_exe = None


# --- PyInstaller 路径兼容 ---
if getattr(sys, "frozen", False):
    # COLLECT 模式：exe 同级目录才是真正的根（config/、data/、flet_web/web/ 都在这）
    BASE_DIR = os.path.dirname(sys.executable)
    os.chdir(BASE_DIR)

    # adb.exe 在 exe 同级目录
    _adb_exe = os.path.join(BASE_DIR, "adb.exe")
    if not os.path.isfile(_adb_exe):
        # 回退到 _MEIPASS
        _adb_exe = os.path.join(sys._MEIPASS, "adb.exe")
    if os.path.isfile(_adb_exe):
        os.environ["ADBUTILS_ADB_PATH"] = _adb_exe
        os.environ["PATH"] = os.path.dirname(_adb_exe) + os.pathsep + os.environ.get("PATH", "")
        # 主动启动 ADB server
        try:
            subprocess.run([_adb_exe, "start-server"], timeout=15,
                           creationflags=_FLAGS,
                           stdin=subprocess.DEVNULL,
                           stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL)
        except Exception:
            pass
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

import server

server.BASE = BASE_DIR
server.SETTINGS_PATH = os.path.join(BASE_DIR, "config", "settings.yaml")
server.ELEMENTS_PATH = os.path.join(BASE_DIR, "config", "elements.yaml")


def _cleanup_adb():
    """退出时杀 adb server，防止文件被占用。"""
    global _adb_exe
    if _adb_exe is None:
        # 开发模式：找 adb
        import shutil
        _adb_exe = shutil.which("adb") or "adb"
    if _adb_exe:
        try:
            subprocess.run([_adb_exe, "kill-server"], timeout=10,
                           creationflags=_FLAGS,
                           stdin=subprocess.DEVNULL,
                           stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL)
        except Exception:
            pass


atexit.register(_cleanup_adb)


def main():
    freeze_support()

    import logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        force=True,
    )

    import uvicorn

    port = 5100
    config = uvicorn.Config(server.app, host="0.0.0.0", port=port,
                            log_level="info", log_config=None)
    srv = uvicorn.Server(config)

    stop_event = threading.Event()

    def run_server():
        try:
            srv.run()
        finally:
            stop_event.set()

    t = threading.Thread(target=run_server, daemon=True)
    t.start()

    time.sleep(2)

    # --- 启动 Flet 浏览器模式 ---
    # Flet Web 静态资源路径：COLLECT 模式下在 exe 同级目录，不在 _internal
    if getattr(sys, "frozen", False):
        web_path = os.path.join(BASE_DIR, "flet_web", "web")
        if os.path.isdir(web_path):
            os.environ["FLET_WEB_PATH"] = web_path

    import flet as ft
    from ui.app import main as ui_main

    ft.app(target=ui_main, view=ft.AppView.WEB_BROWSER, port=8550)

    # Flet 退出后关闭 server
    srv.should_exit = True
    _cleanup_adb()
    t.join(timeout=5)


if __name__ == "__main__":
    main()
