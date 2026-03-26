from __future__ import annotations

from .color_utils import combine_color_and_alpha, display_color_text, parse_color_text, split_color_and_alpha


def visible_stops(layer: dict) -> list[dict]:
    return [stop for stop in (layer.get("stops") or []) if not stop.get("muted", False)]


def linear_stops_css(layer: dict, format_stop_value) -> str:
    stops = visible_stops(layer)
    if not stops:
        return "rgba(0, 0, 0, 0) 0%, rgba(0, 0, 0, 0) 100%"
    parts: list[str] = []
    run_color = str(stops[0].get("color", "#ffffff"))
    run_start = float(stops[0].get("position", 0.0))
    run_end = run_start
    for stop in stops[1:]:
        color = str(stop.get("color", "#ffffff"))
        position = float(stop.get("position", 0.0))
        if color == run_color:
            run_end = position
            continue
        color_text = display_color_text(run_color)
        if abs(run_end - run_start) <= 1e-9:
            parts.append(f"{color_text} {format_stop_value(layer, run_start)}")
        else:
            parts.append(f"{color_text} {format_stop_value(layer, run_start)} {format_stop_value(layer, run_end)}")
        run_color = color
        run_start = position
        run_end = position
    color_text = display_color_text(run_color)
    if abs(run_end - run_start) <= 1e-9:
        parts.append(f"{color_text} {format_stop_value(layer, run_start)}")
    else:
        parts.append(f"{color_text} {format_stop_value(layer, run_start)} {format_stop_value(layer, run_end)}")
    return ", ".join(parts)


def update_stop_from_table(layer: dict, row: int, column: int, color_text: str, alpha_text: str, value_text: str, parse_stop_value) -> bool:
    stops = list(layer.get("stops") or [])
    if not (0 <= row < len(stops)):
        return False
    if column == 2:
        parsed = parse_stop_value(layer, value_text)
        if parsed is None:
            return False
        stops[row]["position"] = parsed
    elif column in (0, 1):
        combined = combine_color_and_alpha(color_text, alpha_text)
        if combined is None:
            return False
        stops[row]["color"] = combined
    else:
        return False
    layer["stops"] = stops
    return True


def step_stop(layer: dict, row: int, column: int, delta: int, unit_name: str, gradient_span: float) -> bool:
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
        if unit_name == "px":
            current = current + (delta / gradient_span)
        else:
            current = current + (delta / 100.0)
        stops[row]["position"] = current
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


def append_stop(layer: dict, color: str, position: float) -> None:
    layer.setdefault("stops", []).append({"color": color, "position": float(position), "muted": False})


def append_stop_after_last(layer: dict, selected_color: str, unit_name: str, gradient_span: float) -> None:
    stops = list(layer.get("stops") or [])
    if stops:
        last_position = float(stops[-1].get("position", 0.0))
        position = last_position
    else:
        position = 0.0
    stops.append({"color": selected_color, "position": position, "muted": False})
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
