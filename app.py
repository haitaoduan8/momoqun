"""Windows EXE 启动脚本。
启动 FastAPI 服务器，自动打开浏览器访问 Web UI。
"""

from multiprocessing import freeze_support
import io
import os
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

import threading
import time
import webbrowser


# --- PyInstaller 路径兼容 ---
if getattr(sys, "frozen", False):
    BASE_DIR = sys._MEIPASS
    os.chdir(BASE_DIR)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

import server

server.BASE = BASE_DIR
server.SETTINGS_PATH = os.path.join(BASE_DIR, "config", "settings.yaml")
server.ELEMENTS_PATH = os.path.join(BASE_DIR, "config", "elements.yaml")


def main():
    freeze_support()

    import logging

    # 日志初始化
    _log_file = os.path.join(BASE_DIR, "momoqun.log")
    from utils.helpers import setup_logging as _setup_log
    _setup_log(level=logging.DEBUG, log_file=_log_file, file_mode="w")
    _root_logger = logging.getLogger("momoqun")

    _root_logger.info("momoqun starting...")
    _root_logger.info("BASE_DIR: %s", BASE_DIR)
    _root_logger.info("sys._MEIPASS: %s", getattr(sys, "_MEIPASS", "N/A"))
    _root_logger.info("sys.executable: %s", sys.executable)
    _root_logger.info("frozen: %s", getattr(sys, "frozen", False))
    _root_logger.info("Log file: %s", _log_file)

    import uvicorn

    port = 5100
    server.MASTER_PORT = port  # 让 /api/master-address 拼出正确端口
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

    # 等服务器启动
    time.sleep(2)

    # 自动打开浏览器
    url = f"http://localhost:{port}"
    _root_logger.info("Opening browser: %s", url)
    webbrowser.open(url)
    print(f"momoqun 已启动: {url}")

    # 阻塞主线程直到服务器退出
    try:
        stop_event.wait()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
