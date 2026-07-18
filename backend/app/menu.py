"""Menu config loader. Edit menu.json per client — no code changes needed."""

import json
import os
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parent.parent


def _resolve_menu_path() -> str:
    """
    Resolve menu.json relative to the backend package root, not process CWD.
    Absolute MENU_PATH env values are kept as-is; relative values are anchored
    to backend/ so `MENU_PATH=menu.json` works from any working directory.
    """
    raw = os.environ.get("MENU_PATH")
    if raw:
        p = Path(raw)
        return str(p if p.is_absolute() else _BACKEND_ROOT / p)
    return str(_BACKEND_ROOT / "menu.json")


MENU_PATH = _resolve_menu_path()


def load_menu() -> dict:
    with open(MENU_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def menu_as_text(menu: dict) -> str:
    lines = []
    for category in menu["categories"]:
        lines.append(f"\n{category['name'].upper()}")
        for item in category["items"]:
            lines.append(f"- {item['name']}: Rs. {item['price']}")
    if menu.get("delivery_fee") is not None:
        lines.append(f"\nDelivery fee: Rs. {menu['delivery_fee']}")
    if menu.get("delivery_area"):
        lines.append(f"Delivery area: {menu['delivery_area']}")
    return "\n".join(lines)
