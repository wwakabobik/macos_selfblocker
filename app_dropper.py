#!/usr/bin/env python3
"""
app_dropper.py — safely quit/kill and (optionally) disable auto-start for a list of apps.

Usage:
  ./app_dropper.py drop -f ~/.work_drop.txt         # drop apps from list (interactive)
  ./app_dropper.py drop -f ~/.work_drop.txt --yes   # no prompt
  ./app_dropper.py drop -f ~/.work_drop.txt --force # force kill immediately (no AppleScript quit)
  ./app_dropper.py drop -f ~/.work_drop.txt --no-unload  # don't touch launch agents
  ./app_dropper.py status -f ~/.work_drop.txt       # show status of listed apps
  ./app_dropper.py list                             # print example list / help

List file format (~/.work_drop.txt):
  Comments start with #
  Lines can be:
    AppName                (e.g. Slack, "Visual Studio Code")
    bundle:com.tinyspeck.slackmacgap  (bundle identifier)
    proc:Slack              (force match process name)
"""
from __future__ import annotations
import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import List

from commons import log, notify

BASE_DIR = Path(__file__).resolve().parent
OSASCRIPT = "/usr/bin/osascript"
PKILL = "/usr/bin/pkill"
PGREP = "/usr/bin/pgrep"
LAUNCHCTL = "/bin/launchctl"


def run(cmd: List[str], check: bool = False, capture: bool = False) -> subprocess.CompletedProcess:
    """
    Wrapper around subprocess.run with common parameters.

    :param cmd: Command list
    :type cmd: List[str]
    :param check: check return code
    :type check: bool
    :param capture: capture output
    :type capture: bool
    :return: CompletedProcess
    :rtype: subprocess.CompletedProcess
    """
    return subprocess.run(cmd, check=check, capture_output=capture, text=True)

def apple_script_quit(app_name: str) -> bool:
    """
    Ask macOS to quit the app gracefully via AppleScript.

    :param app_name: Application name (as shown in macOS)
    :type app_name: str
    """
    script = f'tell application "{app_name}" to quit'
    try:
        run([OSASCRIPT, "-e", script], check=True)
        log(f"AppleScript quit issued to '{app_name}'")
        return True
    except subprocess.CalledProcessError as e:
        log(f"AppleScript quit failed for '{app_name}': {e}")
        return False

def pgrep_pids(pattern: str) -> List[int]:
    """
    Return list of PIDs matching pattern using pgrep; empty list if none.

    :param pattern: pattern to match (for pgrep -f)
    :type pattern: str
    :return: list of PIDs
    :rtype: List[int]
    """
    try:
        res = run([PGREP, "-f", pattern], check=False, capture=True)
        if res.stdout.strip() == "":
            return []
        return [int(x) for x in res.stdout.strip().splitlines() if x.strip().isdigit()]
    except Exception as e:
        log(f"pgrep error for '{pattern}': {e}")
        return []

def kill_pids(pids: List[int], sig: int = 15) -> None:
    """
    Send signal to list of pids.

    :param pids: list of PIDs
    :type pids: List[int]
    :param sig: signal number (default 15=SIGTERM, 9=SIGKILL)
    :type sig: int
    """
    for pid in pids:
        try:
            os.kill(pid, sig)
            log(f"Sent signal {sig} to PID {pid}")
        except ProcessLookupError:
            log(f"PID {pid} not found")
        except PermissionError:
            log(f"No permission to signal PID {pid}")
        except Exception as e:
            log(f"Error signaling PID {pid}: {e}")

def force_kill_by_name(name: str) -> None:
    """
    Use pkill -f to kill processes matching name (SIGTERM then SIGKILL if needed).

    :param name: pattern to match (for pkill -f)
    :type name: str
    """
    # Try SIGTERM first
    try:
        run([PKILL, "-f", name], check=False)
        log(f"pkill -f {name} (SIGTERM) issued")
    except Exception as e:
        log(f"pkill error (SIGTERM) for '{name}': {e}")

    # wait a moment then SIGKILL remaining
    pids = pgrep_pids(name)
    if pids:
        log(f"PIDs still alive after SIGTERM for '{name}': {pids}; sending SIGKILL")
        kill_pids(pids, sig=9)

def find_launch_agents_for_app(app_hint: str) -> List[Path]:
    """
    Search common LaunchAgents/LaunchDaemons for plist names containing the hint.

    :param app_hint: hint string to search for (in filename or contents)
    :type app_hint: str
    :return: list of matching plist paths
    :rtype: List[Path]
    """
    candidates = []
    dirs = [
        Path.home() / "Library" / "LaunchAgents",
        Path("/Library/LaunchAgents"),
        Path("/Library/LaunchDaemons"),
        Path("/System/Library/LaunchAgents"),
        Path("/System/Library/LaunchDaemons"),
    ]
    for d in dirs:
        if not d.exists():
            continue
        for p in d.glob("*.plist"):
            try:
                # match filename or contents if readable
                if app_hint.lower() in p.name.lower():
                    candidates.append(p)
                    continue
                # peek into file content (small)
                text = p.read_text(errors="ignore").lower()
                if app_hint.lower() in text:
                    candidates.append(p)
            except Exception:
                continue
    return candidates

def unload_launch_agent(plist_path: Path) -> None:
    """
    Unload a launchctl plist (requires sudo for system dirs).

    :param plist_path: path to the plist file
    :type plist_path: Path
    """
    try:
        # 'launchctl bootout' recommended for modern macOS, but older uses unload
        run([LAUNCHCTL, "bootout", str(plist_path)], check=False)
        log(f"Attempted to bootout {plist_path}")
    except Exception:
        try:
            run([LAUNCHCTL, "unload", str(plist_path)], check=False)
            log(f"Attempted to unload {plist_path}")
        except Exception as e:
            log(f"Failed to unload {plist_path}: {e}")

def status_of_app(entry: str) -> str:
    """
    Return a short status for the entry.

    :param entry: entry string (AppName, bundle:ID, proc:Name)
    :type entry: str
    :return: "running" or "not running"
    :rtype: str
    """
    # supports 'bundle:com.foo', 'proc:Name' or plain 'AppName'
    if entry.startswith("bundle:"):
        bundle = entry.split(":",1)[1]
        pids = pgrep_pids(bundle)
    elif entry.startswith("proc:"):
        proc = entry.split(":",1)[1]
        pids = pgrep_pids(proc)
    else:
        pids = pgrep_pids(entry)
    return "running" if pids else "not running"

def load_list_file(path: Path) -> List[str]:
    """
    Load entries from the list file, ignoring comments and empty lines.

    :param path: path to the list file
    :type path: Path
    :return: list of entries
    :rtype: List[str]
    """
    if not path.exists():
        log(f"List file not found: {path}")
        sys.exit(1)
    entries = []
    for ln in path.read_text().splitlines():
        ln = ln.strip()
        if not ln or ln.startswith("#"):
            continue
        entries.append(ln)
    return entries

def confirm(prompt: str) -> bool:
    """
    Ask user for yes/no confirmation.

    :param prompt: prompt message
    :type prompt: str
    :return: True if yes, False if no
    :rtype: bool
    """
    ans = input(prompt + " [y/N]: ").strip().lower()
    return ans in ("y","yes")

def drop_entry(entry: str, force: bool = False, do_unload: bool = True, dry: bool = False) -> None:
    """
    Try to drop one entry:
     - if not force: try AppleScript quit by app name
     - check running pids (pgrep), send SIGTERM then SIGKILL
     - optionally unload launch agents containing the hint

     :param entry: entry string (AppName, bundle:ID, proc:Name)
     :type entry: str
     :param force: if True, skip AppleScript and immediately pkill
     :type force: bool
     :param do_unload: if True, try to unload launch agents
     :type do_unload: bool
     :param dry: if True, do not actually perform actions
    """
    log(f"Processing '{entry}'")
    # use different strategies
    if entry.startswith("bundle:"):
        app_hint = entry.split(":",1)[1]
        # AppleScript needs app name; try to derive friendly name from bundle (best effort)
        app_name_for_as = ""
    elif entry.startswith("proc:"):
        app_hint = entry.split(":",1)[1]
        app_name_for_as = ""
    else:
        app_hint = entry
        app_name_for_as = entry

    if dry:
        log(f"[DRY] Would try to quit: {entry}")
        return

    # 1) graceful quit via AppleScript if we have a name and not forced
    if not force and app_name_for_as:
        try:
            apple_script_quit(app_name_for_as)
        except Exception as e:
            log(f"AppleScript attempt error: {e}")

    # 2) wait a short time and check pids matching hint
    import time
    time.sleep(0.8)
    pids = pgrep_pids(app_hint)
    if pids:
        log(f"PIDs found for '{entry}': {pids} — sending SIGTERM then SIGKILL if needed")
        kill_pids(pids, sig=15)
        time.sleep(0.8)
        pids = pgrep_pids(app_hint)
        if pids:
            log(f"PIDs still present after SIGTERM: {pids} — sending SIGKILL")
            kill_pids(pids, sig=9)
    else:
        log(f"No processes found for '{entry}'")

    # 3) optionally unload launch agents/daemons
    if do_unload:
        plists = find_launch_agents_for_app(app_hint)
        if plists:
            log(f"Found {len(plists)} launchd plists for hint '{app_hint}': {plists}")
            for p in plists:
                try:
                    unload_launch_agent(p)
                except Exception as e:
                    log(f"Failed to unload {p}: {e}")
        else:
            log(f"No launchd plists found for '{app_hint}'")

def cmd_drop(list_file: Path, force: bool, do_unload: bool, dry: bool, assume_yes: bool) -> None:
    """
    Command to drop apps from the list file.

    :param list_file: path to the list file
    :type list_file: Path
    :param force: force kill (skip AppleScript)
    :type force: bool
    :param do_unload: whether to unload launch agents
    :type do_unload: bool
    :param dry: dry run (no actions)
    :type dry: bool
    :param assume_yes: assume yes to prompts
    :type assume_yes: bool
    """
    entries = load_list_file(list_file)
    if not entries:
        log("No entries in list.")
        return
    log("Will process the following entries:")
    for e in entries:
        log(" - " + e + " : " + status_of_app(e))
    if not assume_yes and not confirm("Proceed to drop these apps?"):
        log("Aborted.")
        return
    for e in entries:
        drop_entry(e, force=force, do_unload=do_unload, dry=dry)
    notify(f"{len(entries)} work apps shut down. Step away and enjoy your time off!", title="Work Blocker")


def cmd_status(list_file: Path) -> None:
    """
    Command to show status of apps from the list file.

    :param list_file: path to the list file
    :type list_file: Path
    """
    entries = load_list_file(list_file)
    for e in entries:
        log(f"{e}: {status_of_app(e)}")

def print_example(list_file: Path) -> None:
    """"
    Print example list file to the specified path.

    :param list_file: path to write the example list
    :type list_file: Path
    """
    example = """# Example ~/.work_drop.txt
# plain app name (used with AppleScript and pgrep)
Slack
"Visual Studio Code"
# bundle id
bundle:com.tinyspeck.slackmacgap
# raw process match (pgrep -f)
proc:Code
"""
    list_file.write_text(example)
    log(f"Example list written to {list_file}")

def main() -> None:
    """Main function to parse arguments and execute commands."""
    p = argparse.ArgumentParser(description="Drop (quit/kill) work apps.")
    sub = p.add_subparsers(dest="cmd")

    default_list_file = BASE_DIR / "work_drop.txt"

    parser_drop = sub.add_parser("drop")
    parser_drop.add_argument("-f", "--file", type=Path, default=default_list_file)
    parser_drop.add_argument("--force", action="store_true", help="skip AppleScript graceful quit; immediately pkill")
    parser_drop.add_argument("--no-unload", dest="unload", action="store_false", help="do not unload launch agents")
    parser_drop.add_argument("--dry-run", action="store_true")
    parser_drop.add_argument("--yes", action="store_true", help="assume yes")

    parser_status = sub.add_parser("status")
    parser_status.add_argument("-f", "--file", type=Path, default=default_list_file)

    parser_list = sub.add_parser("list")

    args = p.parse_args()

    if args.cmd == "drop":
        cmd_drop(args.file, force=args.force, do_unload=args.unload, dry=args.dry_run, assume_yes=args.yes)
    elif args.cmd == "status":
        cmd_status(args.file)
    elif args.cmd == "list":
        print_example(default_list_file)
    else:
        p.print_help()


if __name__ == "__main__":
    main()
