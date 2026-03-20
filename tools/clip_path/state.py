from dataclasses import dataclass


MODE_INPUT = "入力"
MODE_VIEW = "画面"
MODE_CIRCLE = "円"

SIZE_TYPE_PERCENT = "%"
SIZE_TYPE_PIXEL = "px"


@dataclass
class ClipPoint:
    x: float
    y: float


@dataclass
class ClipSize:
    width: float = 100.0
    height: float = 100.0
    unit: str = SIZE_TYPE_PERCENT


@dataclass
class GridState:
    value: int = 10
    active: bool = False


@dataclass
class CircleGuide:
    center: ClipPoint
    radius: float
    divisions: int
    snap_points: list[ClipPoint]
