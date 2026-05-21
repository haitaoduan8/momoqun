"""Windows EXE 启动脚本。
启动 FastAPI 服务器（后台线程）并自动打开浏览器。
"""
from multiprocessing import freeze_support
import os
import sys

# --- console=False 兼容：重定向 stdout/stderr，避免 uvicorn logging 崩溃 ---
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")

import threading
import time
import webbrowser


# --- PyInstaller 路径兼容 ---
if getattr(sys, "frozen", False):
    BASE_DIR = sys._MEIPASS
    os.chdir(BASE_DIR)  # 把 CWD 切到打包目录，保证 config/ data/ 等相对路径可用
    # 告诉 adbutils 去哪里找内置的 adb.exe
    os.environ["ADBUTILS_ADB_PATH"] = os.path.join(
        BASE_DIR, "_internal", "adbutils", "binaries", "adb.exe"
    )
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

import server

server.BASE = BASE_DIR
server.SETTINGS_PATH = os.path.join(BASE_DIR, "config", "settings.yaml")
server.ELEMENTS_PATH = os.path.join(BASE_DIR, "config", "elements.yaml")


def main():
    freeze_support()

    import uvicorn

    port = 5100
    config = uvicorn.Config(server.app, host="0.0.0.0", port=port, log_level="info")
    srv = uvicorn.Server(config)

    stop_event = threading.Event()

    def run_server():
        try:
            srv.run()
        finally:
            stop_event.set()

    t = threading.Thread(target=run_server, daemon=True)
    t.start()

    # 等待服务器就绪
    time.sleep(2)
    webbrowser.open(f"http://localhost:{port}")

    print(f"momoqun 已启动: http://localhost:{port}")
    print("按 Ctrl+C 退出。")

    try:
        stop_event.wait()
    except KeyboardInterrupt:
        print("\n正在退出...")
        srv.should_exit = True
        t.join(timeout=5)


if __name__ == "__main__":
    main()
