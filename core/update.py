import requests
import zipfile
import tempfile
import subprocess
import sys
from pathlib import Path
from core.version import VERSION

REPO = "atachan14/ToolBox"
API = f"https://api.github.com/repos/{REPO}/releases/latest"




def check_update():

    try:

        local = VERSION

        r = requests.get(API, timeout=3)
        r.raise_for_status()

        release = r.json()
        latest = release["tag_name"].lstrip("v")

        if latest == local:
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


def launch_updater(extract_dir):

    base = Path(sys.executable).parent

    subprocess.Popen([
        sys.executable,
        "-m",
        "core.updater",
        str(extract_dir),
        str(base)
    ])

    sys.exit()