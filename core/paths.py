import sys
from pathlib import Path


def get_base_dir():

    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent

    return Path(__file__).resolve().parent.parent


BASE_DIR = get_base_dir()

USERS_DIR = BASE_DIR / "Users"
TABS_DIR = USERS_DIR / "Tabs"
TOOL_DATA_DIR = USERS_DIR / "ToolData"
TRASH_TABS_DIR = USERS_DIR / "TrashTabs"
LEGACY_TABS_DIR = BASE_DIR / "tabs"

USERS_DIR.mkdir(exist_ok=True)
TABS_DIR.mkdir(parents=True, exist_ok=True)
TOOL_DATA_DIR.mkdir(parents=True, exist_ok=True)
TRASH_TABS_DIR.mkdir(parents=True, exist_ok=True)
