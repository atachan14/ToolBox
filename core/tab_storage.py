import json
from pathlib import Path

from core.paths import TABS_DIR, TOOL_DATA_DIR


DEFAULT_SCHEMA_VERSION = 2


def _read_json(path: Path, default):
    if not path.exists():
        return default
    try:
        loaded = json.loads(path.read_text(encoding="utf-8") or "null")
    except json.JSONDecodeError:
        return default
    return loaded


def create_unique_name(base):
    name = base
    i = 1

    while (TABS_DIR / name).exists():
        name = f"{base}{i}"
        i += 1

    return name


def ensure_tool_data_dir(tool_name):
    folder = TOOL_DATA_DIR / tool_name
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def create_tab_folder(tool_class):
    name = create_unique_name(tool_class.TOOL_DEFAULT_LABEL)
    folder = TABS_DIR / name
    folder.mkdir(parents=True, exist_ok=False)

    meta = {
        "tool": tool_class.TOOL_NAME,
        "order": 0,
        "label": name,
        "schema_version": DEFAULT_SCHEMA_VERSION,
    }
    (folder / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (folder / "state.json").write_text("{}", encoding="utf-8")

    for file_name in getattr(tool_class, "TAB_FILES", []):
        (folder / file_name).touch()

    tool_data_dir = ensure_tool_data_dir(tool_class.TOOL_NAME)
    return name, folder, tool_data_dir


def load_tab_meta(folder: Path):
    meta = _read_json(folder / "meta.json", {})
    return meta if isinstance(meta, dict) else {}


def save_tab_meta(folder: Path, data: dict):
    (folder / "meta.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def iter_saved_tabs():
    tabs = []
    for folder in TABS_DIR.iterdir():
        if not folder.is_dir():
            continue
        meta = load_tab_meta(folder)
        if not meta:
            continue
        tabs.append((meta.get("order", 0), folder, meta))
    return sorted(tabs, key=lambda item: item[0])
