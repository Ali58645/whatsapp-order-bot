"""Menu config loader. Edit menu.json per client — no code changes needed."""

import json
import os

MENU_PATH = os.environ.get("MENU_PATH", "menu.json")


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
