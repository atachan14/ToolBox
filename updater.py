import ctypes
import shutil
import subprocess
import sys
import time
from pathlib import Path


def wait_for_process_exit(pid, timeout=30):
    if pid is None or sys.platform != "win32":
        return

    synchronize = 0x00100000
    process = ctypes.windll.kernel32.OpenProcess(synchronize, False, pid)

    if not process:
        return

    try:
        result = ctypes.windll.kernel32.WaitForSingleObject(process, int(timeout * 1000))
        if result == 0x00000102:
            raise Exception(f"ToolBox.exe process {pid} did not exit within {timeout} seconds")
    finally:
        ctypes.windll.kernel32.CloseHandle(process)


def wait_for_unlock(path, timeout=30):
    start = time.time()

    while True:
        try:
            with open(path, "ab"):
                return
        except OSError:
            if time.time() - start > timeout:
                raise Exception("ToolBox.exe still locked")
            time.sleep(0.5)


def apply_update(extract_dir, base_dir):
    dirs = list(Path(extract_dir).iterdir())

    if not dirs:
        raise Exception("extract_dir is empty")

    new_dir = dirs[0]

    time.sleep(2)

    for item in new_dir.iterdir():
        if item.name == "updater.exe":
            continue
        if item.name == "Users":
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
    success = False

    try:
        print("=== updater start ===")

        extract_dir = Path(sys.argv[1])
        base_dir = Path(sys.argv[2])
        parent_pid = int(sys.argv[3]) if len(sys.argv) > 3 else None

        print("extract_dir:", extract_dir)
        print("base_dir:", base_dir)
        if parent_pid is not None:
            print("parent_pid:", parent_pid)

        exe_path = base_dir / "ToolBox.exe"

        print("waiting for ToolBox process to exit...")
        wait_for_process_exit(parent_pid)

        print("waiting for ToolBox.exe to unlock...")
        wait_for_unlock(exe_path)

        apply_update(extract_dir, base_dir)

        print("update done")

        restart(base_dir)

        print("restart done")
        success = True

    except Exception as e:
        print("ERROR:", e)

    if success:
        time.sleep(1)
    else:
        input("press enter to exit...")


if __name__ == "__main__":
    main()
