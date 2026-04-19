import requests
import zipfile
import tempfile
import subprocess
import sys
from pathlib import Path
from core.version import VERSION

REPO = "atachan14/ToolBox"
API = f"https://api.github.com/repos/{REPO}/releases/latest"


def is_frozen_build():
    return bool(getattr(sys, "frozen", False))


def get_updater_path():
    if not is_frozen_build():
        return None
    return Path(sys.executable).parent / "updater.exe"


def can_self_update():
    updater = get_updater_path()
    return updater is not None and updater.exists()

def parse_version(v):
    return tuple(map(int, v.split(".")))

def check_update():
    if not can_self_update():
        return None

    try:
        local = VERSION.strip()

        r = requests.get(API, timeout=5)
        r.raise_for_status()

        release = r.json()
        latest = release["tag_name"].lstrip("v").strip()

        if parse_version(latest) <= parse_version(local):
            return None

        for asset in release["assets"]:
            if asset["name"].endswith(".zip"):
                return {
                    "version": latest,
                    "url": asset["browser_download_url"]
                }

    except Exception:
        return None

    return None


def download_update(url):

    temp_dir = tempfile.mkdtemp()
    zip_path = Path(temp_dir) / "update.zip"

    r = requests.get(url, stream=True, timeout=3)
    r.raise_for_status()

    with open(zip_path, "wb") as f:
        for chunk in r.iter_content(8192):
            f.write(chunk)

    return zip_path


def extract_update(zip_path):

    extract_dir = zip_path.parent / "extract"

    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(extract_dir)

    return extract_dir


def launch_updater(extract_dir, parent_pid=None):
    updater = get_updater_path()

    if updater is None or not updater.exists():
        return False

    base = updater.parent

    args = [
        updater,
        str(extract_dir),
        str(base)
    ]

    if parent_pid is not None:
        args.append(str(parent_pid))

    subprocess.Popen(args)
    return True
