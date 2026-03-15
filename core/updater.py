import shutil
import sys
import time
import subprocess
from pathlib import Path


def apply_update(extract_dir, base_dir):

    new_dir = next(Path(extract_dir).glob("ToolBox*"))

    time.sleep(1)

    for item in new_dir.iterdir():

        if item.name == "tabs":
            continue

        dest = base_dir / item.name

        if dest.exists():
            if dest.is_dir():
                shutil.rmtree(dest)
            else:
                dest.unlink()

        if item.is_dir():
            shutil.copytree(item, dest)
        else:
            shutil.copy2(item, dest)


def restart(base_dir):

    exe = base_dir / "ToolBox.exe"

    subprocess.Popen([exe])


def main():

    extract_dir = Path(sys.argv[1])
    base_dir = Path(sys.argv[2])

    apply_update(extract_dir, base_dir)
    restart(base_dir)


if __name__ == "__main__":
    main()