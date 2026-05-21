"""Windows EXE 启动脚本。
启动 FastAPI 服务器（后台线程）并自动打开浏览器。
"""
from multiprocessing import freeze_support
import io
import os
import sys


# --- 确保 stdout/stderr 永不为 None（console=False 兼容）---
class _NullIO(io.RawIOBase):
    def write(self, b): return len(b) if b else 0
    def read(self, n=-1): return b""
    def isatty(self): return False

if sys.stdout is None:
    sys.stdout = io.TextIOWrapper(_NullIO())
if sys.stderr is None:
    sys.stderr = io.TextIOWrapper(_NullIO())
# 兜底：某些库直接访问 __stdout__ / __stderr__
if getattr(sys, "__stdout__", None) is None:
    sys.__stdout__ = sys.stdout
if getattr(sys, "__stderr__", None) is None:
    sys.__stderr__ = sys.stderr

import threading
import time
import webbrowser


# --- PyInstaller 路径兼容 ---
if getattr(sys, "frozen", False):
    BASE_DIR = sys._MEIPASS
    os.chdir(BASE_DIR)

    _adb_dir = os.path.join(BASE_DIR, "_internal", "adbutils", "binaries")
    _adb_exe = os.path.join(_adb_dir, "adb.exe")
    if os.path.isfile(_adb_exe):
        os.environ["ADBUTILS_ADB_PATH"] = _adb_exe
        os.environ["PATH"] = _adb_dir + os.pathsep + os.environ.get("PATH", "")
        # 直接把 adbutils._utils.adb_path 替换掉，不依赖环境变量
        import adbutils._utils
        adbutils._utils.adb_path = lambda: _adb_exe
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

import server

server.BASE = BASE_DIR
server.SETTINGS_PATH = os.path.join(BASE_DIR, "config", "settings.yaml")
server.ELEMENTS_PATH = os.path.join(BASE_DIR, "config", "elements.yaml")


def main():
    freeze_support()

    # 预初始化 logging，防止 uvicorn 配日志时崩溃
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
    webbrowser.open(f"http://localhost:{port}")

    try:
        stop_event.wait()
    except KeyboardInterrupt:
        srv.should_exit = True
        t.join(timeout=5)


if __name__ == "__main__":
    main()
