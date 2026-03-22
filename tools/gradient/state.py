from __future__ import annotations

from typing import Callable, TypedDict

from .color_utils import parse_color_text


class StopState(TypedDict):
    color: str
    position: float
    muted: bool


class LayerState(TypedDict):
    kind: str
    name: str
    deg: int
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
    return {
        "kind": kind,
        "name": str(layer.get("name", default_name)),
        "deg": int(layer.get("deg", 90)),
        "repeat": bool(layer.get("repeat", False)),
        "muted": bool(layer.get("muted", False)),
        "color": str(layer.get("color", "#00000000")),
        "stops": [
            {
                "color": str(stop.get("color", "#ffffff")),
                "position": float(stop.get("position", 0.0)),
                "muted": bool(stop.get("muted", False)),
            }
            for stop in layer.get("stops") or []
        ],
    }


def serialize_layers(layers: list[dict]) -> list[LayerState]:
    return [serialize_layer(layer) for layer in layers]


def normalize_layer_payload(item: dict, default_name_factory: Callable[[str], str]) -> LayerState | None:
    if not isinstance(item, dict):
        return None
    kind = str(item.get("kind", "linear"))
    default_name = "b" if kind == "background" else default_name_factory(kind)
    return {
        "kind": kind,
        "name": str(item.get("name", default_name)),
        "deg": int(item.get("deg", 90)),
        "repeat": bool(item.get("repeat", False)),
        "muted": bool(item.get("muted", False)),
        "color": parse_color_text(str(item.get("color", "#00000000"))) or "#00000000",
        "stops": [
            {
                "color": parse_color_text(str(stop.get("color", "#ffffff"))) or "#ffffff",
                "position": float(stop.get("position", 0.0)),
                "muted": bool(stop.get("muted", False)),
            }
            for stop in item.get("stops", [])
            if isinstance(stop, dict)
        ],
    }
