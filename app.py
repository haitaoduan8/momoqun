"""Windows EXE 启动脚本。
启动 FastAPI 服务器（后台线程）并自动打开浏览器。
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
    def isatty(self): return False

if sys.stdout is None:
    sys.stdout = io.TextIOWrapper(_NullIO())
if sys.stderr is None:
    sys.stderr = io.TextIOWrapper(_NullIO())

import threading
import time
import webbrowser


# --- PyInstaller 路径兼容 ---
if getattr(sys, "frozen", False):
    BASE_DIR = sys._MEIPASS
    os.chdir(BASE_DIR)

    # adb.exe 现在放在 exe 同级目录（spec 里指定了 '.' 作为目标）
    _adb_exe = os.path.join(BASE_DIR, "adb.exe")
    if os.path.isfile(_adb_exe):
        os.environ["ADBUTILS_ADB_PATH"] = _adb_exe
        os.environ["PATH"] = BASE_DIR + os.pathsep + os.environ.get("PATH", "")
        # 主动启动 ADB server
        _flags = 0x08000000 if sys.platform == "win32" else 0
        try:
            subprocess.run([_adb_exe, "start-server"], timeout=15,
                           creationflags=_flags,
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
    webbrowser.open(f"http://localhost:{port}")

    try:
        stop_event.wait()
    except KeyboardInterrupt:
        srv.should_exit = True
        t.join(timeout=5)


if __name__ == "__main__":
    main()
