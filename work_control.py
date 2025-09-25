#!/usr/bin/env python3

import subprocess
import sys
from pathlib import Path

from commons import log, notify

BASE_DIR = Path(__file__).resolve().parent
WORK_MODE_FILE = BASE_DIR / ".work_mode"


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
    print(f"Usage:\n  {sys.argv[0]} block\n  {sys.argv[0]} unblock")
    sys.exit(1)


def main():
    """
    Main entry point for the wrapper script.

    Parses the command line argument ('block' or 'unblock') and runs
    all managed scripts accordingly.
    """
    if len(sys.argv) != 2:
        usage()

    action = sys.argv[1].lower()
    if action not in ("block", "unblock"):
        usage()

    scripts = ["dir_blocker.py", "net_blocker.py", "app_dropper.py"]

    # Set/reset lock file
    if action == "block":
        if WORK_MODE_FILE.exists():
            WORK_MODE_FILE.unlink()
            log("Removed .work_mode file — no more work!")
        else:
            log(".work_mode file already absent.")
    elif action == "unblock":
        WORK_MODE_FILE.touch()
        log("Created .work_mode file — work mode is ON.")

    for script in scripts:
        run_script(script, action)

    log(f"All scripts executed successfully with parameter '{action}'.")


if __name__ == "__main__":
    main()
