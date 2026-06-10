"""违规账号换号：清空模拟器目录 + 从本地池推送未使用文件。"""

from __future__ import annotations

import logging
from typing import Any, Dict

from data.file_pool import claim_next_file
from ops.adb_ops import clear_remote_dir, push_file_to_device, shell_mkdir_p

logger = logging.getLogger(__name__)


def swap_account_file_for_device(
    adb_serial: str,
    local_dir: str,
    remote_dir: str,
    *,
    agent_serial: str = "",
) -> Dict[str, Any]:
    """删除目标目录内文件，再推送一个未使用过的本地文件。"""
    serial_key = (agent_serial or adb_serial).strip()
    remote_dir = (remote_dir or "/sdcard/Download").strip()

    try:
        ok_clear, clear_err = clear_remote_dir(adb_serial, remote_dir)
        if not ok_clear:
            logger.warning(
                "清空远程目录失败 serial=%s dir=%s: %s",
                adb_serial,
                remote_dir,
                clear_err,
            )

        local_path, claim_err = claim_next_file(local_dir, serial_key)
        if not local_path:
            return {
                "ok": False,
                "adb_serial": adb_serial,
                "error": claim_err or "无可用文件",
            }

        filename = local_path.rsplit("/", 1)[-1].rstrip("\\")
        remote_file = f"{remote_dir.rstrip('/')}/{filename}"
        shell_mkdir_p(adb_serial, remote_dir)
        ok_push, push_err = push_file_to_device(adb_serial, local_path, remote_file)
        return {
            "ok": ok_push,
            "adb_serial": adb_serial,
            "file": filename,
            "local_path": local_path,
            "remote": remote_file,
            "error": push_err or None,
        }
    except Exception as exc:
        logger.exception("swap_account_file_for_device 异常 serial=%s", adb_serial)
        return {"ok": False, "adb_serial": adb_serial, "error": str(exc)}
