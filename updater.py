import shutil
import sys
import time
import subprocess
from pathlib import Path

def wait_for_unlock(path, timeout=10):
    start = time.time()

    while True:
        try:
            path.rename(path)  # ← ロック中はこれが失敗する
            return
        except PermissionError:
            if time.time() - start > timeout:
                raise Exception("ToolBox.exe still locked")
            time.sleep(0.5)
            
def apply_update(extract_dir, base_dir):

    dirs = list(Path(extract_dir).iterdir())

    if not dirs:
        raise Exception("extract_dir is empty")

    new_dir = dirs[0]

    time.sleep(2)

    current_exe = Path(sys.argv[0]).name

    for item in new_dir.iterdir():

        if item.name in ["tabs", current_exe]:
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

    if not exe.exists():
        raise Exception("ToolBox.exe not found")

    time.sleep(1)

    subprocess.Popen([str(exe)])


def main():
    try:
        print("=== updater start ===")

        extract_dir = Path(sys.argv[1])
        base_dir = Path(sys.argv[2])

        print("extract_dir:", extract_dir)
        print("base_dir:", base_dir)

        exe_path = base_dir / "ToolBox.exe"

        print("waiting for ToolBox.exe to unlock...")
        wait_for_unlock(exe_path)

        apply_update(extract_dir, base_dir)

        print("update done")

        restart(base_dir)

        print("restart done")

    except Exception as e:
        print("ERROR:", e)

    input("press enter to exit...")

if __name__ == "__main__":
    main()