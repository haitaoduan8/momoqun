"""配置 dict 深合并（PUT /api/config 局部更新用）。"""

from __future__ import annotations

from typing import Any, Dict


def deep_merge(base: Dict[str, Any], patch: Dict[str, Any]) -> Dict[str, Any]:
    """递归合并 patch 到 base 副本，patch 优先。"""
    out: Dict[str, Any] = dict(base or {})
    for key, value in (patch or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = deep_merge(out[key], value)
        else:
            out[key] = value
    return out
