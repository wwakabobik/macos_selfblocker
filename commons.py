#!/usr/bin/env python3

import sys
import subprocess
from pathlib import Path
from datetime import datetime


BASE_DIR = Path(__file__).resolve().parent
LOG_FILE = BASE_DIR / "work_access_control.log"
WORK_MODE_FILE = BASE_DIR / ".work_mode"
OSASCRIPT_BIN = "/usr/bin/osascript"


def log(msg: str) -> None:
    """
    Log a message with a timestamp to the log file.

    :param msg: Message to log
    :type msg: str
    """
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"{ts}: {msg}"
    try:
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")
    except Exception:
        pass
    print(line)


def notify(message: str, subtitle: str = "", title: str = "🚫 Self Blocker", sound: bool = False) -> None:
    """
    Show a macOS notification using osascript.

    :param message: Notification message
    :type message: str
    :param subtitle: Notification subtitle (optional)
    :type subtitle: str
    :param sound: Whether to play a sound with the notification
    :type sound: bool
    :param title: Notification title
    :type title: str
    """
    try:
        subprocess.run([
            OSASCRIPT_BIN,
            "-e",
            f'display notification "{message}" with title "{title}"'
        ], check=True)
        cmd = [
            OSASCRIPT_BIN,
            "-e",
            f'display notification "{message}" with title "{title}"'
        ]
        if subtitle:
            cmd[-1] += f' subtitle "{subtitle}"'
        if sound:
            cmd[-1] += ' sound name "Submarine"'
        subprocess.run(cmd, check=True)
    except Exception as e:
        log(f"Failed to show notification: {e}")


def check_work_mode_file() -> None:
    """Prevent unblock unless .work_mode exists (i.e. it's not work time)."""
    if WORK_MODE_FILE.exists():
        log("❌ Cannot unblock: not work time.")
        sys.exit(1)
