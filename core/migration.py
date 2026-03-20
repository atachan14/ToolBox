import json
import shutil
from pathlib import Path

from core.paths import LEGACY_TABS_DIR, TABS_DIR, TOOL_DATA_DIR
from core.tab_storage import DEFAULT_SCHEMA_VERSION


def _read_json(path: Path, default):
    if not path.exists():
        return default
    try:
        loaded = json.loads(path.read_text(encoding="utf-8") or "null")
    except json.JSONDecodeError:
        return default
    return loaded


def _write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _normalize_meta(tab_dir: Path):
    old_meta = tab_dir / "tool.json"
    meta_path = tab_dir / "meta.json"

    if meta_path.exists():
        meta = _read_json(meta_path, {})
    else:
        meta = _read_json(old_meta, {})

    if not isinstance(meta, dict):
        meta = {}

    meta["label"] = tab_dir.name
    meta.setdefault("order", 0)
    meta.setdefault("schema_version", DEFAULT_SCHEMA_VERSION)
    _write_json(meta_path, meta)

    if old_meta.exists() and old_meta != meta_path:
        old_meta.unlink()

    state_path = tab_dir / "state.json"
    if not state_path.exists():
        _write_json(state_path, {})

    return meta


def _merge_history(source_path: Path, target_path: Path):
    if not source_path.exists():
        return

    source = _read_json(source_path, [])
    target = _read_json(target_path, [])

    if not isinstance(source, list):
        source = []
    if not isinstance(target, list):
        target = []

    merged = []
    seen = set()
    for entry in [*source, *target]:
        key = json.dumps(entry, ensure_ascii=False, sort_keys=True)
        if key in seen:
            continue
        seen.add(key)
        merged.append(entry)

    _write_json(target_path, merged)
    source_path.unlink()


def migrate_user_data():
    if LEGACY_TABS_DIR.exists():
        TABS_DIR.mkdir(parents=True, exist_ok=True)
        for old_tab in LEGACY_TABS_DIR.iterdir():
            if not old_tab.is_dir():
                continue
            new_tab = TABS_DIR / old_tab.name
            if new_tab.exists():
                continue
            shutil.move(str(old_tab), str(new_tab))

        if not any(LEGACY_TABS_DIR.iterdir()):
            LEGACY_TABS_DIR.rmdir()

    for tab_dir in TABS_DIR.iterdir():
        if not tab_dir.is_dir():
            continue

        meta = _normalize_meta(tab_dir)
        tool_name = meta.get("tool")

        if tool_name == "clamp":
            target = TOOL_DATA_DIR / "clamp" / "history.json"
            target.parent.mkdir(parents=True, exist_ok=True)
            _merge_history(tab_dir / "history.json", target)
        elif tool_name == "clip-path":
            target = TOOL_DATA_DIR / "clip-path" / "history.json"
            target.parent.mkdir(parents=True, exist_ok=True)
            _merge_history(tab_dir / "history.json", target)
