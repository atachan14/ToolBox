from __future__ import annotations

import re

from PySide6.QtGui import QColor


def parse_color_text(text: str) -> str | None:
    value = text.strip().lower()
    if not value:
        return None
    if value == "transparent":
        return "#00000000"
    if re.fullmatch(r"[0-9a-f]{3,4}|[0-9a-f]{6}|[0-9a-f]{8}", value):
        value = f"#{value}"
    parsed = QColor(value)
    if parsed.isValid():
        return parsed.name(QColor.HexArgb).lower() if parsed.alpha() < 255 else parsed.name().lower()
    if value.startswith("rgb(") and value.endswith(")"):
        body = value[4:-1]
        parts = [part.strip() for part in body.split(",")]
        if len(parts) != 3:
            return None
        try:
            r, g, b = [max(0, min(255, int(part))) for part in parts]
        except ValueError:
            return None
        return QColor(r, g, b).name().lower()
    return None


def qcolor_from_text(text: str) -> QColor:
    parsed = parse_color_text(text)
    return QColor(parsed) if parsed else QColor("#000000")


def color_text_from_qcolor(color: QColor) -> str:
    if color.alpha() < 255:
        return color.name(QColor.HexArgb).lower()
    return color.name().lower()


def display_color_text(text: str) -> str:
    parsed = parse_color_text(text)
    if parsed == "#00000000":
        return "transparent"
    return parsed if parsed is not None else text.strip().lower()


def split_color_and_alpha(text: str) -> tuple[str, str]:
    color = qcolor_from_text(text)
    return display_color_text(text), f"{round(color.alphaF() * 100):d}%"


def combine_color_and_alpha(color_text: str, alpha_text: str) -> str | None:
    parsed = parse_color_text(color_text)
    if parsed is None:
        return None
    color = qcolor_from_text(parsed)
    value = alpha_text.strip().lower()
    if not value:
        return None
    try:
        numeric = value[:-1] if value.endswith("%") else value
        alpha = max(0.0, min(1.0, float(numeric) / 100.0))
    except ValueError:
        return None
    color.setAlphaF(alpha)
    return color_text_from_qcolor(color)
