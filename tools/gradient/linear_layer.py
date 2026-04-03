from __future__ import annotations

from .color_utils import combine_color_and_alpha, css_color_text, display_color_text, parse_color_text, split_color_and_alpha


def visible_stops(layer: dict) -> list[dict]:
    return [stop for stop in (layer.get("stops") or []) if not stop.get("muted", False)]


def linear_stops_css(layer: dict, format_stop_value) -> str:
    stops = visible_stops(layer)
    if not stops:
        return "rgba(0, 0, 0, 0) 0%, rgba(0, 0, 0, 0) 100%"
    parts: list[str] = []
    run_color = str(stops[0].get("color", "#ffffff"))
    run_start = stops[0]
    run_end = run_start
    for stop in stops[1:]:
        color = str(stop.get("color", "#ffffff"))
        if color == run_color:
            run_end = stop
            continue
        color_text = css_color_text(run_color)
        if abs(float(run_end.get("position", 0.0)) - float(run_start.get("position", 0.0))) <= 1e-9 and str(run_end.get("unit", "%")) == str(run_start.get("unit", "%")):
            parts.append(f"{color_text} {format_stop_value(layer, run_start)}")
        else:
            parts.append(f"{color_text} {format_stop_value(layer, run_start)} {format_stop_value(layer, run_end)}")
        run_color = color
        run_start = stop
        run_end = stop
    color_text = css_color_text(run_color)
    if abs(float(run_end.get("position", 0.0)) - float(run_start.get("position", 0.0))) <= 1e-9 and str(run_end.get("unit", "%")) == str(run_start.get("unit", "%")):
        parts.append(f"{color_text} {format_stop_value(layer, run_start)}")
    else:
        parts.append(f"{color_text} {format_stop_value(layer, run_start)} {format_stop_value(layer, run_end)}")
    return ", ".join(parts)


def update_stop_from_table(layer: dict, row: int, column: int, color_text: str, alpha_text: str, value_text: str, unit_text: str, parse_stop_value) -> bool:
    stops = list(layer.get("stops") or [])
    if not (0 <= row < len(stops)):
        return False
    if column == 2:
        parsed = parse_stop_value(layer, value_text, unit_text)
        if parsed is None:
            return False
        stops[row]["position"] = parsed
    elif column == 3:
        unit = unit_text.strip().lower()
        if unit not in {"px", "%"}:
            return False
        stops[row]["unit"] = unit
    elif column in (0, 1):
        combined = combine_color_and_alpha(color_text, alpha_text)
        if combined is None:
            return False
        stops[row]["color"] = combined
    else:
        return False
    layer["stops"] = stops
    return True


def step_stop(layer: dict, row: int, column: int, delta: int) -> bool:
    stops = list(layer.get("stops") or [])
    if not (0 <= row < len(stops)):
        return False
    if column == 1:
        color_text, alpha_text = split_color_and_alpha(str(stops[row].get("color", "#ffffff")))
        current_alpha = alpha_text[:-1] if alpha_text.endswith("%") else alpha_text
        try:
            alpha = float(current_alpha)
        except ValueError:
            alpha = 100.0
        combined = combine_color_and_alpha(color_text, f"{max(0.0, min(100.0, alpha + delta))}%")
        if combined is None:
            return False
        stops[row]["color"] = combined
    elif column == 2:
        current = float(stops[row].get("position", 0.0))
        stops[row]["position"] = current + delta
    else:
        return False
    layer["stops"] = stops
    return True


def reorder_stop(layer: dict, source_row: int, target_row: int) -> bool:
    stops = list(layer.get("stops") or [])
    if not (0 <= source_row < len(stops) and 0 <= target_row < len(stops)):
        return False
    stop = stops.pop(source_row)
    stops.insert(target_row, stop)
    layer["stops"] = stops
    return True


def append_stop(layer: dict, color: str, position: float, unit: str) -> None:
    layer.setdefault("stops", []).append({"color": color, "position": float(position), "unit": unit, "muted": False})


def append_stop_after_last(layer: dict, selected_color: str, default_unit: str) -> None:
    stops = list(layer.get("stops") or [])
    if stops:
        last_position = float(stops[-1].get("position", 0.0))
        last_unit = str(stops[-1].get("unit", default_unit))
        position = last_position
    else:
        position = 0.0
        last_unit = default_unit
    stops.append({"color": selected_color, "position": position, "unit": last_unit, "muted": False})
    layer["stops"] = stops


def set_stop_color(layer: dict, row: int, color: str) -> bool:
    stops = list(layer.get("stops") or [])
    if not (0 <= row < len(stops)):
        return False
    parsed = parse_color_text(color)
    if parsed is None:
        return False
    stops[row]["color"] = parsed
    layer["stops"] = stops
    return True


def move_stop(layer: dict, index: int, position: float) -> bool:
    stops = list(layer.get("stops") or [])
    if not (0 <= index < len(stops)):
        return False
    stops[index]["position"] = float(position)
    layer["stops"] = stops
    return True


def delete_stop(layer: dict, index: int) -> bool:
    stops = list(layer.get("stops") or [])
    if not (0 <= index < len(stops)):
        return False
    stops.pop(index)
    layer["stops"] = stops
    return True


def duplicate_stop(layer: dict, index: int) -> bool:
    stops = list(layer.get("stops") or [])
    if not (0 <= index < len(stops)):
        return False
    duplicate = {
        "color": str(stops[index].get("color", "#ffffff")),
        "position": float(stops[index].get("position", 0.0)),
        "unit": str(stops[index].get("unit", "%")),
        "muted": bool(stops[index].get("muted", False)),
    }
    stops.insert(index + 1, duplicate)
    layer["stops"] = stops
    return True


def toggle_stop_muted(layer: dict, index: int) -> bool:
    stops = list(layer.get("stops") or [])
    if not (0 <= index < len(stops)):
        return False
    stops[index]["muted"] = not bool(stops[index].get("muted", False))
    layer["stops"] = stops
    return True
