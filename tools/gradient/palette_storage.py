from __future__ import annotations

import json
import re
from pathlib import Path


PALETTE_SCHEMA_VERSION = 1


def palette_dir(tool_data_dir: Path | None) -> Path | None:
    if tool_data_dir is None:
        return None
    folder = Path(tool_data_dir) / "palettes"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def normalize_palette_name(name: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", name.strip())
    cleaned = cleaned.strip(" .")
    return cleaned or "palette"


def _palette_path(folder: Path, name: str) -> Path:
    return folder / f"{normalize_palette_name(name)}.json"


def _unique_palette_path(folder: Path, name: str, current_path: Path | None = None) -> Path:
    candidate = _palette_path(folder, name)
    if current_path is not None and candidate == current_path:
        return candidate
    if not candidate.exists():
        return candidate
    stem = candidate.stem
    suffix = candidate.suffix
    index = 1
    while True:
        path = folder / f"{stem}{index}{suffix}"
        if current_path is not None and path == current_path:
            return path
        if not path.exists():
            return path
        index += 1


def next_palette_name(folder: Path | None, base_name: str = "Palette") -> str:
    if folder is None:
        return base_name
    candidate = base_name
    if not _palette_path(folder, candidate).exists():
        return candidate
    index = 1
    while _palette_path(folder, f"{base_name}{index}").exists():
        index += 1
    return f"{base_name}{index}"


def save_palette(folder: Path | None, colors: list[str], name: str | None = None) -> Path | None:
    if folder is None:
        return None
    display_name = (name or "").strip() or next_palette_name(folder)
    path = _unique_palette_path(folder, display_name)
    payload = {
        "schema_version": PALETTE_SCHEMA_VERSION,
        "name": display_name,
        "colors": list(colors),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_palettes(folder: Path | None) -> list[dict]:
    if folder is None or not folder.exists():
        return []
    entries: list[dict] = []
    for path in sorted(folder.glob("*.json"), key=lambda item: item.stem.lower()):
        try:
            loaded = json.loads(path.read_text(encoding="utf-8") or "{}")
        except json.JSONDecodeError:
            continue
        if not isinstance(loaded, dict):
            continue
        colors = loaded.get("colors")
        if not isinstance(colors, list):
            continue
        entries.append(
            {
                "path": path,
                "name": str(loaded.get("name", path.stem)),
                "colors": [str(color) for color in colors],
            }
        )
    return entries


def rename_palette(path: Path, new_name: str) -> Path:
    folder = path.parent
    try:
        loaded = json.loads(path.read_text(encoding="utf-8") or "{}")
    except json.JSONDecodeError:
        loaded = {}
    if not isinstance(loaded, dict):
        loaded = {}
    target = _unique_palette_path(folder, new_name, current_path=path)
    loaded["name"] = new_name.strip() or "palette"
    target.write_text(json.dumps(loaded, ensure_ascii=False, indent=2), encoding="utf-8")
    if target != path and path.exists():
        path.unlink()
    return target


def delete_palette(path: Path):
    if path.exists():
        path.unlink()
