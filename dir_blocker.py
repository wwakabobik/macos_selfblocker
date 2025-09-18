#!/usr/bin/env python3

import os
import sys
import stat
import subprocess
from datetime import datetime

LOG_FILE = os.path.expanduser("~/work_access_control.log")


def log(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a") as f:
        f.write(f"{timestamp}: {message}\n")


def notify(message, title="Work Blocker"):
    subprocess.run(["osascript", "-e", f'display notification "{message}" with title "{title}"'])


def change_permissions(paths, mode):
    for path in paths:
        if os.path.exists(path):
            try:
                if os.path.isdir(path):
                    for root, dirs, files in os.walk(path):
                        os.chmod(root, mode)
                        for d in dirs:
                            os.chmod(os.path.join(root, d), mode)
                        for f in files:
                            os.chmod(os.path.join(root, f), mode)
                else:
                    os.chmod(path, mode)
                log(f"{'Заблокирован' if mode == 0 else 'Разблокирован'} доступ к {path}")
            except PermissionError:
                print(f"Ошибка доступа при изменении прав: {path}")
            except Exception as e:
                print(f"Ошибка при обработке {path}: {e}")
        else:
            print(f"Путь не найден или недоступен: {path}")


def read_paths_from_file(filepath):
    if not os.path.isfile(filepath):
        print(f"Файл не найден: {filepath}")
        sys.exit(1)
    with open(filepath, "r") as f:
        lines = [line.strip() for line in f if line.strip()]
    return lines


def usage():
    print(
        f"Использование:\n"
        f"  {sys.argv[0]} block path1 [path2 ...]\n"
        f"  {sys.argv[0]} unblock path1 [path2 ...]\n"
        f"  {sys.argv[0]} block -f /path/to/file.txt\n"
        f"  {sys.argv[0]} unblock -f /path/to/file.txt"
    )
    sys.exit(1)


def main():
    if len(sys.argv) < 3:
        usage()

    action = sys.argv[1]
    args = sys.argv[2:]

    if args[0] == "-f":
        if len(args) < 2:
            usage()
        paths = read_paths_from_file(args[1])
    else:
        paths = args

    if action == "block":
        change_permissions(paths, 0)
        notify("Доступ к проектам заблокирован. Время отдыха!")
    elif action == "unblock":
        change_permissions(paths, 0o755)
        notify("Доступ к проектам восстановлен. Можно работать.")
    else:
        usage()


if __name__ == "__main__":
    main()
