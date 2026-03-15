import requests
from core.version import VERSION

REPO = "atachan14/ToolBox"


def get_latest_release():

    url = f"https://api.github.com/repos/{REPO}/releases/latest"

    try:
        r = requests.get(url, timeout=5)
        r.raise_for_status()
        return r.json()

    except Exception as e:
        print("update check failed:", e)
        return None


def check_update():

    release = get_latest_release()
    if not release:
        return None

    latest = release["tag_name"].lstrip("v")

    if latest != VERSION:

        for asset in release["assets"]:
            if asset["name"].endswith(".exe"):
                return {
                    "version": latest,
                    "url": asset["browser_download_url"]
                }

    return None