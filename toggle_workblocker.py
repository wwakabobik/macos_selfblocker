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

LAUNCH_AGENTS_DIR = os.path.expanduser("~/Library/LaunchAgents")


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


def is_agent_loaded(label: str) -> bool:
    """
    Check if a launch agent is currently loaded.

    :param label: Label of the launch agent
    :type label: str
    :return: True if loaded, False otherwise
    :rtype: bool
    """
    try:
        output = subprocess.check_output(["launchctl", "list"]).decode()
        lines = output.splitlines()
        for line in lines:
            if label in line:
                if line.strip().endswith(label):
                    return True
        return False
    except subprocess.CalledProcessError:
        return False


def toggle_agents(action: str) -> None:
    """
    Toggle launch agents by enabling or disabling them.

    :param action: 'enable' or 'disable'
    :type action: str
    """
    for suffix in AGENT_SUFFIXES:
        label = f"{AGENT_TEMPLATE}.{suffix}"
        plist_path = os.path.join(LAUNCH_AGENTS_DIR, f"{label}.plist")
        launchctl_label = f"gui/{UID}/{label}"

        if action == "disable":
            if is_agent_loaded(label):
                run_command(["launchctl", "bootout", f"gui/{UID}", plist_path])
            else:
                print(f"ℹ️ {launchctl_label} is already unloaded")

            print(f"🚫 Disabling {launchctl_label}")
            run_command(["launchctl", "disable", launchctl_label])

        elif action == "enable":
            run_command(["launchctl", "enable", launchctl_label])

            if is_agent_loaded(label):
                print(f"ℹ️ {launchctl_label} is already loaded, unloading before loading again")
                run_command(["launchctl", "bootout", f"gui/{UID}", plist_path])

            print(f"✅ Enabling {launchctl_label}")
            run_command(["launchctl", "bootstrap", f"gui/{UID}", plist_path])

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
