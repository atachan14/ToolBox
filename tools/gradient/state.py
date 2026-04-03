from __future__ import annotations

from typing import Callable, TypedDict

from .color_utils import parse_color_text


class StopState(TypedDict):
    color: str
    position: float
    unit: str
    muted: bool


class LayerState(TypedDict):
    kind: str
    name: str
    deg: int
    deg_mode: str
    center_x: float
    center_x_unit: str
    center_y: float
    center_y_unit: str
    shape: str
    repeat: bool
    muted: bool
    color: str
    stops: list[StopState]


def normalize_palette_colors(palette_state) -> list[str] | None:
    if not isinstance(palette_state, list) or not palette_state:
        return None
    return [parse_color_text(str(color)) or "#00000000" for color in palette_state]


def serialize_layer(layer: dict) -> LayerState:
    kind = str(layer.get("kind", "linear"))
    default_name = "b" if kind == "background" else "L"
    legacy_unit = str(layer.get("unit", "%"))
    return {
        "kind": kind,
        "name": str(layer.get("name", default_name)),
        "deg": int(layer.get("deg", 90)),
        "deg_mode": str(layer.get("deg_mode", "input")),
        "center_x": float(layer.get("center_x", 0.5)),
        "center_x_unit": str(layer.get("center_x_unit", legacy_unit)),
        "center_y": float(layer.get("center_y", 0.5)),
        "center_y_unit": str(layer.get("center_y_unit", legacy_unit)),
        "shape": str(layer.get("shape", "circle")),
        "repeat": bool(layer.get("repeat", False)),
        "muted": bool(layer.get("muted", False)),
        "color": str(layer.get("color", "#00000000")),
        "stops": [
            {
                "color": str(stop.get("color", "#ffffff")),
                "position": float(stop.get("position", 0.0)),
                "unit": str(stop.get("unit", legacy_unit if kind == "radial" else "%")),
                "muted": bool(stop.get("muted", False)),
            }
            for stop in layer.get("stops") or []
        ],
    }


def serialize_layers(layers: list[dict]) -> list[LayerState]:
    return [serialize_layer(layer) for layer in layers]


def normalize_layer_payload(item: dict, default_name_factory: Callable[[str], str], default_linear_stop_unit: str = "%") -> LayerState | None:
    if not isinstance(item, dict):
        return None
    kind = str(item.get("kind", "linear"))
    default_name = "b" if kind == "background" else default_name_factory(kind)
    legacy_unit = str(item.get("unit", "%"))
    stop_default_unit = legacy_unit if kind == "radial" else default_linear_stop_unit
    return {
        "kind": kind,
        "name": str(item.get("name", default_name)),
        "deg": int(item.get("deg", 90)),
        "deg_mode": str(item.get("deg_mode", "input")),
        "center_x": float(item.get("center_x", 0.5)),
        "center_x_unit": str(item.get("center_x_unit", legacy_unit)),
        "center_y": float(item.get("center_y", 0.5)),
        "center_y_unit": str(item.get("center_y_unit", legacy_unit)),
        "shape": str(item.get("shape", "circle")),
        "repeat": bool(item.get("repeat", False)),
        "muted": bool(item.get("muted", False)),
        "color": parse_color_text(str(item.get("color", "#00000000"))) or "#00000000",
        "stops": [
            {
                "color": parse_color_text(str(stop.get("color", "#ffffff"))) or "#ffffff",
                "position": float(stop.get("position", 0.0)),
                "unit": str(stop.get("unit", stop_default_unit)),
                "muted": bool(stop.get("muted", False)),
            }
            for stop in item.get("stops", [])
            if isinstance(stop, dict)
        ],
    }
