from __future__ import annotations


def build_clamp(min_px: float, max_px: float, min_view: float, max_view: float) -> tuple[bool, str]:
    """Build CSS clamp expression from pixel and viewport ranges."""
    if min_view == max_view:
        return False, "min view と max view が同じです"

    if min_view > max_view:
        min_view, max_view = max_view, min_view
        min_px, max_px = max_px, min_px

    slope = (max_px - min_px) / (max_view - min_view) * 100
    intercept = min_px - (slope * min_view / 100)

    low = min(min_px, max_px)
    high = max(min_px, max_px)

    sign = "+" if slope >= 0 else "-"
    slope_abs = abs(slope)

    clamp = (
        f"clamp({low:g}px, calc({intercept:.4f}px {sign} {slope_abs:.4f}vw), {high:g}px)"
    )
    return True, clamp
