from __future__ import annotations

import re

SELECTOR_UNITS = {"", "px", "%", "rem"}
VIEW_SELECTOR_UNITS = {"", "vw", "vh"}


def parse_value_text(text: str) -> tuple[bool, tuple[float, str] | str]:
    match = re.fullmatch(r"\s*(-?(?:\d+|\d*\.\d+))\s*([a-zA-Z%]*)\s*", text)
    if not match:
        return False, "value を正しく入力してください"
    value = float(match.group(1))
    unit = match.group(2)
    return True, (value, unit)


def _format_number(value: float) -> str:
    rounded = round(value)
    if abs(value - rounded) < 1e-9:
        return str(int(rounded))
    rounded_2 = round(value, 2)
    if abs(rounded_2 - round(rounded_2)) < 1e-9:
        return str(int(round(rounded_2)))
    return f"{rounded_2:.2f}".rstrip("0").rstrip(".")


def _format_value(value: float, unit: str) -> str:
    return f"{_format_number(value)}{unit}"


def resolve_output_unit(min_unit: str, max_unit: str, selected_unit: str) -> tuple[bool, str]:
    if min_unit and max_unit and min_unit != max_unit:
        return False, "min value と max value の単位を揃えてください"
    if min_unit or max_unit:
        return True, min_unit or max_unit
    if selected_unit in SELECTOR_UNITS:
        return True, selected_unit
    return True, ""


def resolve_view_unit(min_unit: str, max_unit: str, selected_unit: str) -> tuple[bool, str]:
    if min_unit and max_unit and min_unit != max_unit:
        return False, "min view と max view の単位を揃えてください"
    if min_unit or max_unit:
        return True, min_unit or max_unit
    if selected_unit in VIEW_SELECTOR_UNITS:
        return True, selected_unit
    return True, "vw"


def build_clamp(
    min_value: tuple[float, str],
    max_value: tuple[float, str],
    min_view: float,
    max_view: float,
    selected_unit: str = "",
    view_unit: str = "vw",
) -> tuple[bool, str]:
    if min_view == max_view:
        return False, "min view と max view が同じです"

    min_number, min_unit = min_value
    max_number, max_unit = max_value
    ok, output_unit = resolve_output_unit(min_unit, max_unit, selected_unit)
    if not ok:
        return False, output_unit

    if min_view > max_view:
        min_view, max_view = max_view, min_view
        min_number, max_number = max_number, min_number

    slope = (max_number - min_number) / (max_view - min_view) * 100
    intercept = min_number - (slope * min_view / 100)
    low = min(min_number, max_number)
    high = max(min_number, max_number)
    sign = "+" if slope >= 0 else "-"

    clamp = (
        f"clamp({_format_value(low, output_unit)}, "
        f"calc({_format_value(intercept, output_unit)} {sign} {_format_number(abs(slope))}{view_unit}), "
        f"{_format_value(high, output_unit)})"
    )
    return True, clamp
