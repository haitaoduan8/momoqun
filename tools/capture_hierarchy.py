#!/usr/bin/env python3
"""ADB 采集界面 dump + 截图，用于 weiba_boot fixture 采集（Phase A）。"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from ops.adb_ops import get_adb_path, run_adb  # noqa: E402


def _agent_apk(serial: str) -> str:
    out, err, rc = run_adb(["-s", serial, "shell", "su", "-c", "pm path com.momoqun.agent"])
    if rc != 0 or not out.strip():
        raise RuntimeError(f"获取 agent apk 失败: {err or out}")
    line = out.strip().splitlines()[0]
    return line.replace("package:", "").strip()


def capture(serial: str, out_dir: str, basename: str) -> tuple[str, str]:
    os.makedirs(out_dir, exist_ok=True)
    xml_path = os.path.join(out_dir, f"{basename}.xml")
    png_path = os.path.join(out_dir, f"{basename}.png")
    apk = _agent_apk(serial)
    dump_cmd = (
        f"CLASSPATH='{apk}' app_process /system/bin com.momoqun.agent.dumper.Main"
    )
    adb = get_adb_path()
    with open(xml_path, "w", encoding="utf-8") as f:
        proc = subprocess.run(
            [adb, "-s", serial, "shell", "su", "-c", dump_cmd],
            stdout=f,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr or "dump 失败")
    adb = get_adb_path()
    proc = subprocess.run(
        [adb, "-s", serial, "exec-out", "screencap", "-p"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.decode("utf-8", errors="replace") or "screencap 失败")
    with open(png_path, "wb") as f:
        f.write(proc.stdout)
    return xml_path, png_path


def main() -> None:
    parser = argparse.ArgumentParser(description="ADB dump + screencap")
    parser.add_argument("-s", "--serial", required=True, help="设备序列号")
    parser.add_argument("-o", "--out-dir", default=os.path.join(ROOT, "fixtures", "weiba_boot"))
    parser.add_argument("-n", "--name", required=True, help="输出文件名（不含扩展名）")
    args = parser.parse_args()
    xml_path, png_path = capture(args.serial, args.out_dir, args.name)
    print(xml_path)
    print(png_path)


if __name__ == "__main__":
    main()
