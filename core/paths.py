import sys
from pathlib import Path


def get_base_dir():

    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent

    return Path(__file__).resolve().parent.parent


BASE_DIR = get_base_dir()

TABS_DIR = BASE_DIR / "tabs"

TABS_DIR.mkdir(exist_ok=True)