#!/usr/bin/env python3

import os
import sys
import subprocess
from pathlib import Path

from commons import log, notify, check_work_mode_file



BASE_DIR = Path(__file__).resolve().parent
PATHS_FILE = BASE_DIR / "work_paths.txt"
# Absolute paths to utilities
FIND_BIN = "/usr/bin/find"
CHMOD_BIN = "/bin/chmod"
OSASCRIPT_BIN = "/usr/bin/osascript"
SUDO_BIN = "/usr/bin/sudo"


def block_path(path: str) -> None:
    """
    Block access to the specified path by setting permissions to 0,
    skipping symlinks and files outside the root.

    :param path: path to block
    :type path: str
    """
    if not os.path.exists(path):
        log(f"Path not found or inaccessible: {path}")
        return

    root_path = os.path.abspath(path)

    try:
        for root, dirs, files in os.walk(root_path, topdown=False, followlinks=False):
            for name in files:
                file_path = os.path.join(root, name)
                if os.path.islink(file_path):
                    target = os.path.realpath(file_path)
                    if not target.startswith(root_path):
                        log(f"Skipping external symlink file: {file_path} -> {target}")
                        continue
                try:
                    os.chmod(file_path, 0)
                except Exception as e:
                    log(f"Error chmod file {file_path}: {e}")

            for name in dirs:
                dir_path = os.path.join(root, name)
                if os.path.islink(dir_path):
                    target = os.path.realpath(dir_path)
                    if not target.startswith(root_path):
                        log(f"Skipping external symlink dir: {dir_path} -> {target}")
                        continue
                try:
                    os.chmod(dir_path, 0)
                except Exception as e:
                    log(f"Error chmod directory {dir_path}: {e}")

        if not os.path.islink(root_path):
            os.chmod(root_path, 0)

        log(f"Access for {path} is now blocked")
    except Exception as e:
        log(f"Error blocking {path}: {e}")



def unblock_path(path: str) -> None:
    """
    Unblock access to the specified path by setting directories to 755 and files to 644.

    :param path: path to unblock
    :type path: str
    """
    if not os.path.exists(path):
        log(f"Path not found or inaccessible: {path}")
        return

    try:
        # Unblock directories: 755
        subprocess.run([SUDO_BIN, FIND_BIN, path, "-type", "d", "-exec", CHMOD_BIN, "755", "{}", "+"], check=True)
        # Unblock files: 644
        subprocess.run([SUDO_BIN, FIND_BIN, path, "-type", "f", "-exec", CHMOD_BIN, "644", "{}", "+"], check=True)
        log(f"Access for {path} is now unblocked")
    except subprocess.CalledProcessError as e:
        log(f"Subprocess error during unblocking {path}: {e}")


def read_paths_from_file(filepath: str) -> list[str]:
    """
    Read paths from a file, one per line.

    :param filepath: path to the file
    :type filepath: str
    :return: list of paths
    :rtype: list[str]
    """
    if not os.path.isfile(filepath):
        log(f"File not found: {filepath}")
        sys.exit(1)
    with open(filepath, "r") as f:
        return [line.strip() for line in f if line.strip()]


def usage() -> None:
    """Print usage information and exit."""
    print(
        "Usage:\n"
        f"  {sys.argv[0]} block path1 [path2 ...]\n"
        f"  {sys.argv[0]} unblock path1 [path2 ...]\n"
        f"  {sys.argv[0]} block -f /path/to/file.txt\n"
        f"  {sys.argv[0]} unblock -f /path/to/file.txt"
    )
    sys.exit(1)


def main():
    """Main function to parse arguments and perform block/unblock actions."""
    if len(sys.argv) < 2:
        usage()

    action = sys.argv[1]
    args = sys.argv[2:]

    if not args:
        if PATHS_FILE.is_file():
            paths = read_paths_from_file(str(PATHS_FILE))
            log(f"Using default paths from {PATHS_FILE}")
        else:
            log(f"No paths specified and default file not found: {PATHS_FILE}")
            usage()
            return
    else:
        if args[0] == "-f":
            if len(args) < 2:
                usage()
                return
            paths = read_paths_from_file(os.path.expanduser(args[1]))
        else:
            paths = args

    if action == "block":
        for path in paths:
            block_path(os.path.expanduser(path))
        notify(f"Access to projects ({len(paths)}) is blocked. Time to rest!")
    elif action == "unblock":
        check_work_mode_file()
        for path in paths:
            unblock_path(os.path.expanduser(path))
        notify(f"Access to projects ({len(paths)}) is unblocked. You can work now!")
    else:
        usage()


if __name__ == "__main__":
    main()
