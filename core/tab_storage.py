import json
from datetime import datetime
from pathlib import Path
import shutil

from core.paths import TABS_DIR, TOOL_DATA_DIR, TRASH_TABS_DIR


DEFAULT_SCHEMA_VERSION = 2


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
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def create_unique_name(base, parent_dir=TABS_DIR):
    name = base
    i = 1

    while (parent_dir / name).exists():
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
    _write_json(folder / "meta.json", data)


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


def _trash_entries_path():
    return TRASH_TABS_DIR / "entries.json"


def load_trash_entries():
    entries = _read_json(_trash_entries_path(), [])
    return entries if isinstance(entries, list) else []


def save_trash_entries(entries):
    _write_json(_trash_entries_path(), entries)


def iter_trashed_tabs():
    items = []
    for entry in load_trash_entries():
        if not isinstance(entry, dict):
            continue
        folder_name = entry.get("folder_name")
        if not folder_name:
            continue
        folder = TRASH_TABS_DIR / folder_name
        if not folder.is_dir():
            continue
        items.append(
            {
                "folder_name": folder_name,
                "folder": folder,
                "deleted_at": entry.get("deleted_at", ""),
                "meta": load_tab_meta(folder),
            }
        )
    return items


def move_tab_to_trash(tab_name):
    source = TABS_DIR / tab_name
    if not source.is_dir():
        return None

    trash_name = create_unique_name(tab_name, TRASH_TABS_DIR)
    target = TRASH_TABS_DIR / trash_name
    shutil.move(str(source), str(target))

    entries = load_trash_entries()
    entries.append(
        {
            "folder_name": trash_name,
            "deleted_at": datetime.now().isoformat(timespec="seconds"),
        }
    )
    save_trash_entries(entries)
    return target


def restore_tab_from_trash(trash_name):
    source = TRASH_TABS_DIR / trash_name
    if not source.is_dir():
        return None

    restored_name = create_unique_name(trash_name, TABS_DIR)
    target = TABS_DIR / restored_name
    shutil.move(str(source), str(target))

    meta = load_tab_meta(target)
    if meta:
        meta["label"] = restored_name
        save_tab_meta(target, meta)

    entries = [
        entry
        for entry in load_trash_entries()
        if not isinstance(entry, dict) or entry.get("folder_name") != trash_name
    ]
    save_trash_entries(entries)
    return target
