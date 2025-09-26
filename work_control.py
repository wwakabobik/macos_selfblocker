#!/usr/bin/env python3

import subprocess
import sys
import time
from pathlib import Path

from commons import log, notify


BASE_DIR = Path(__file__).resolve().parent
WORK_MODE_FILE = BASE_DIR / ".work_mode"


def notify_countdown(seconds: int) -> None:
    """
    Send countdown notifications from N to 1.

    :param seconds: Number of seconds to count down from
    :type seconds: int
    """
    for i in reversed(range(1, seconds + 1)):
        notify(
            f"Blocking in {i} seconds",
            subtitle="Stop everything you're doing now!",
            sound=(i == 1 or i == 10)
        )
        time.sleep(1)


def run_script(script: str, action: str) -> None:
    """
    Run a script with the given action ('block' or 'unblock') using sudo.

    :param script: Script filename to run
    :type script: str
    :param action: Action to pass to the script ('block' or 'unblock')
    :type action: str
    :raises SystemExit: exits if the subprocess returns a non-zero exit code
    """
    script_path = BASE_DIR / script
    if not script_path.exists():
        log(f"Script not found: {script_path}")
        sys.exit(1)

    try:
        # Construct command depending on script
        if script == "app_dropper.py":
            if action == "block":
                cmd = ["sudo", str(script_path), "drop", "--yes"]
            elif action == "unblock":
                log("Skipping app_dropper.py on 'unblock'")
                return
            else:
                log(f"Unsupported action '{action}' for {script}")
                return
        else:
            cmd = ["sudo", str(script_path), action]

        log(f"Running {script_path} with parameter(s): {' '.join(cmd[2:])}")
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        log(f"{script} output:\n{result.stdout.strip()}")
        if result.stderr.strip():
            log(f"{script} errors:\n{result.stderr.strip()}")
    except subprocess.CalledProcessError as e:
        log(f"Error running {script}: {e}")
        sys.exit(1)


def usage() -> None:
    """Print usage instructions and exit the program."""
    log(f"Usage:\n  {sys.argv[0]} block\n  {sys.argv[0]} unblock")
    sys.exit(1)


def main():
    """
    Main entry point for the wrapper script.

    Parses the command line argument ('block' or 'unblock') and runs
    all managed scripts accordingly.
    """
    if len(sys.argv) < 2:
        usage()

    action = sys.argv[1].lower()
    if action not in ("block", "unblock"):
        usage()

    scripts = ["dir_blocker.py", "net_blocker.py", "app_dropper.py"]

    warn_mode = '--warn' in sys.argv

    if action == "block" and warn_mode:
        notify("🚨 Blocking in 5 minutes", subtitle="Get ready to stop working", sound=True)
        time.sleep(4 * 60)
        notify("⚠️ Blocking in 1 minute", subtitle="Wrap up your work", sound=True)
        time.sleep(50)
        notify_countdown(10)

    # Set/reset lock file
    # Set/reset lock file
    if action == "block":
        if not WORK_MODE_FILE.exists():
            WORK_MODE_FILE.touch()
            log("Created .work_mode file — blocking work (not work time).")
        else:
            log(".work_mode file already exists — already blocked.")
            return  # Already blocked
    elif action == "unblock":
        if WORK_MODE_FILE.exists():
            WORK_MODE_FILE.unlink()
            log("Removed .work_mode file — work time is ON.")
        else:
            log(".work_mode file already absent — already unblocked.")
            return  # Already unblocked

    for script in scripts:
        run_script(script, action)

    log(f"All scripts executed successfully with parameter '{action}'.")


if __name__ == "__main__":
    main()
