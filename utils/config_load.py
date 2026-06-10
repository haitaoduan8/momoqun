"""配置加载：合并 elements.yaml 与 weiba_elements.yaml。"""

from __future__ import annotations

import os
from typing import Any

import yaml

_CONFIG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config")


def load_settings() -> dict:
    path = os.path.join(_CONFIG_DIR, "settings.yaml")
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
        return raw.get("config") or {}
    except FileNotFoundError:
        return {}


def load_elements() -> dict:
    elements: dict[str, Any] = {}
    main_path = os.path.join(_CONFIG_DIR, "elements.yaml")
    try:
        with open(main_path, "r", encoding="utf-8") as f:
            elements = yaml.safe_load(f) or {}
    except FileNotFoundError:
        elements = {}

    weiba_path = os.path.join(_CONFIG_DIR, "weiba_elements.yaml")
    if os.path.isfile(weiba_path):
        try:
            with open(weiba_path, "r", encoding="utf-8") as f:
                weiba = yaml.safe_load(f) or {}
            for key, value in weiba.items():
                elements[key] = value
        except Exception:
            import logging

            logging.getLogger("config_load").exception("加载 weiba_elements.yaml 失败")

    return elements
