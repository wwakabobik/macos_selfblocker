#!/usr/bin/env python3

import getpass
import os
import subprocess
import sys
from typing import List


USERNAME = getpass.getuser()
UID = os.getuid()

AGENT_TEMPLATE = f"com.{USERNAME}.workblocker"
AGENT_SUFFIXES = [
    "block",
    "unblock",
    "relock_loader",
    "relock_unloader",
]


def run_command(command: List[str]) -> None:
    """
    Run a command using subprocess.run and handle errors.

    :param command: Command to run as a list of strings
    :type command: List[str]
    """
    try:
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as e:
        print(f"⚠️ Error running: {' '.join(command)}\n{e}")


def toggle_agents(action: str) -> None:
    """
    Toggle launch agents by enabling or disabling them.

    :param action: 'enable' or 'disable'
    :type action: str
    """
    for suffix in AGENT_SUFFIXES:
        label = f"gui/{UID}/{AGENT_TEMPLATE}.{suffix}"
        if action == "disable":
            print(f"🚫 Disabling {label}")
            run_command(["launchctl", "disable", label])
        elif action == "enable":
            print(f"✅ Enabling {label}")
            run_command(["launchctl", "enable", label])
        else:
            print(f"❌ Unknown action: {action}")
            sys.exit(1)


def main():
    """Main entry point for the script."""
    if len(sys.argv) != 2 or sys.argv[1] not in {"enable", "disable"}:
        print("Usage: python toggle_workblocker.py [enable|disable]")
        sys.exit(1)

    action = sys.argv[1]
    print(f"👤 Current user: {USERNAME}")
    toggle_agents(action)


if __name__ == "__main__":
    main()
