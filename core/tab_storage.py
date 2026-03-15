import json
from pathlib import Path
from core.paths import TABS_DIR


def create_unique_name(base):

    name = base
    i = 1

    while (TABS_DIR / name).exists():
        name = f"{base}{i}"
        i += 1

    return name


def create_tab_folder(tool_class):

    name = create_unique_name(tool_class.TOOL_DEFAULT_LABEL)

    folder = TABS_DIR / name
    folder.mkdir()

    # tool.json
    meta = {
        "tool": tool_class.TOOL_NAME,
        "order": 0
    }

    (folder / "tool.json").write_text(
        json.dumps(meta, indent=2)
    )

    # tool files
    for file in tool_class.TOOL_FILES:
        (folder / file).touch()

    return name, folder