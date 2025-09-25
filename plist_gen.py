#!/usr/bin/env python3

import argparse
import getpass
import json
import plistlib
import subprocess

from pathlib import Path
from typing import Dict, List, Optional, Tuple

from commons import log


BASE_DIR = Path(__file__).resolve().parent
MAIN_SCRIPT = BASE_DIR / 'work_control.py'
SCHEDULE_FILE = BASE_DIR / 'workblocker_schedule.json'
LOG_DIR = Path.home() / 'Library' / 'Logs' / 'workblocker'


def shift_schedule(schedule: List[Dict], minutes_shift: int) -> List[Dict]:
    """
    Shift the schedule by a given number of minutes.

    :param schedule: list of events, each event is a dict with keys 'Hour', 'Minute', 'Weekday'
    :type schedule: List[Dict]
    :param minutes_shift: amount of minutes to shift (can be negative)
    :type minutes_shift: int
    :return: new list of shifted events
    :rtype: List[Dict]
    """
    shifted = []
    for event in schedule:
        hour = event.get('Hour', 0)
        minute = event.get('Minute', 0)
        weekday = event.get('Weekday')

        total_minutes = hour * 60 + minute + minutes_shift

        # Fix shift to next/previous day if needed
        # launchd Weekday: 1=Sunday ... 7=Saturday
        if total_minutes < 0:
            total_minutes += 24 * 60
            weekday = (weekday - 1) if weekday > 1 else 7
        elif total_minutes >= 24 * 60:
            total_minutes -= 24 * 60
            weekday = (weekday + 1) if weekday < 7 else 1

        new_hour = total_minutes // 60
        new_minute = total_minutes % 60

        shifted.append({
            'Hour': new_hour,
            'Minute': new_minute,
            'Weekday': weekday
        })

    return shifted


def generate_relock_loader_plist(
        label: str, action: str, relock_plist_path: Path, log_dir: Path, schedule: List[Dict]
) -> dict:
    """
    Generate a plist for loading/unloading the relock task.

    :param label: label for the task
    :type label: str
    :param action: 'action' to pass to launchctl ('load' or 'unload')
    :type action: str
    :param relock_plist_path: path to the relock plist
    :type relock_plist_path: Path
    :param log_dir: path to log directory
    :type log_dir: Path
    :param schedule: list of schedule dictionaries
    :type schedule: list of dict
    :return: dictionary for plist
    :rtype: dict
    """

    return {
        'Label': label,
        'ProgramArguments': ['launchctl', action, str(relock_plist_path)],
        'StartCalendarInterval': schedule,
        'RunAtLoad': False,
        'StandardOutPath': str(log_dir / f"{label}_stdout.log"),
        'StandardErrorPath': str(log_dir / f"{label}_stderr.log"),
        'LimitLoadToSessionType': 'Aqua',
    }


def generate_relock_plist(label: str, script_path: str, log_dir: Path, interval_seconds: int = 300) -> dict:
    """
    Generate a plist for the relock task that runs every N seconds.

    :param label: label for the task
    :type label: str
    :param script_path: path to main script
    :type script_path: str
    :param log_dir: path to log directory
    :type log_dir: Path
    :param interval_seconds: how often to run (in seconds)
    :type interval_seconds: int
    :return: plist dictionary
    """
    return {
        'Label': label,
        'ProgramArguments': [str(script_path), 'block'],
        'StartInterval': interval_seconds,
        'RunAtLoad': True,
        'StandardOutPath': str(log_dir / f"{label}_stdout.log"),
        'StandardErrorPath': str(log_dir / f"{label}_stderr.log"),
        'LimitLoadToSessionType': 'Aqua',
    }


def generate_plist(label: str, script_path: str, action: str, log_dir: Path, schedule: List[Dict]) -> dict:
    """
    Generate a plist dictionary for launchd.

    :param label: label for the launchd job
    :type label: str
    :param script_path: path to the script to run
    :type script_path: str
    :param action: action to pass to the script ('block' or 'unblock')
    :type action: str
    :param log_dir: directory for log files
    :type log_dir: Path
    :param schedule: list of schedule dictionaries
    :type schedule: list of dict
    :return: plist dictionary
    :rtype: dict
    """
    args = [str(script_path), action]
    if action == 'block':
        args.append('--warn')
    plist_dict = {
        'Label': label,
        'ProgramArguments': args,
        'RunAtLoad': False,
        'StandardOutPath': str(log_dir / f"{label}_stdout.log"),
        'StandardErrorPath': str(log_dir / f"{label}_stderr.log"),
        'LimitLoadToSessionType': 'Aqua',
    }

    if schedule:
        plist_dict['StartCalendarInterval'] = schedule

    return plist_dict


def save_plist(plist_dict: Dict, filepath: Path) -> None:
    """
    Save the plist dictionary to a file.

    :param plist_dict: plist dictionary
    :type plist_dict: dict
    :param filepath: path to save the plist file
    :type filepath: Path
    """
    with open(filepath, 'wb') as f:
        plistlib.dump(plist_dict, f)
    log(f"Plist saved to {filepath}")


def load_schedule(json_path: Path) -> Optional[Dict]:
    """
    Load schedule from a JSON file.

    :param json_path: path to the JSON file
    :type json_path: Path
    :return: schedule dictionary or None
    :rtype: dict or None
    """
    if not json_path.exists():
        log(f"File {json_path} does not exist, using default schedule.")
        return None
    try:
        with open(json_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        log(f"Error loading JSON schedule from {json_path}: {e}")
        return None


def process_intervals_schedule(schedule_intervals: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
    """
    Convert interval-based schedule into two lists of events - block and unblock.

    Each interval contains:
    - days: list of weekday numbers (1=Sunday, 2=Monday, ..., 7=Saturday)
    - start: time to start unblocking (Hour, Minute)
    - end: time to start blocking (Hour, Minute)
    Returns two lists of schedules for launchd:
    - block_schedule: times to block (i.e., outside work interval)
    - unblock_schedule: times to unblock (start of work interval)

    :param schedule_intervals: list of intervals from json
    :type schedule_intervals: list of dict
    :return: (block_schedule, unblock_schedule)
    :rtype: (list of dict, list of dict)
    """
    block_schedule = []
    unblock_schedule = []

    for interval in schedule_intervals:
        days = interval.get('days', [])
        start = interval.get('start')
        end = interval.get('end')

        if not days or not start or not end:
            log(f"Skipping invalid interval (missing days/start/end): {interval}")
            continue

        # For each day, create two entries: unblock at start, block at end
        for d in days:
            unblock_schedule.append({
                'Hour': start['Hour'],
                'Minute': start['Minute'],
                'Weekday': d
            })
            block_schedule.append({
                'Hour': end['Hour'],
                'Minute': end['Minute'],
                'Weekday': d
            })

    return block_schedule, unblock_schedule


def reload_plist(plist_path: Path) -> None:
    """
    Unload and load the plist to apply changes.

    :param plist_path: path to the plist file
    :type plist_path: Path
    """
    for cmd in [['unload'], ['load']]:
        result = subprocess.run(['launchctl', *cmd, str(plist_path)], capture_output=True, text=True)
        if result.returncode != 0:
            log(f"[launchctl {cmd[0]}] Error: {result.stderr.strip()}")
        else:
            log(f"[launchctl {cmd[0]}] OK: {plist_path}")

def parse_args() -> argparse.Namespace:
    """
    Parse command line arguments.

    :return: parsed arguments
    :rtype: argparse.Namespace
    """

    parser = argparse.ArgumentParser(description="Generate launchd plists for work blocker.")
    parser.add_argument(
        "script_path",
        nargs="?",
        default=MAIN_SCRIPT,
        help="Path to the main work_control script (default: work_control.py in current dir)"
    )
    parser.add_argument(
        "--schedule",
        type=Path,
        default=SCHEDULE_FILE,
        help="Path to the JSON schedule file (default: workblocker_schedule.json)"
    )
    return parser.parse_args()


def get_schedule(schedule_path: Path) -> Tuple[List[Dict], List[Dict]]:
    """
    Get the block and unblock schedule from the JSON file or use defaults.

    :param schedule_path: path to the JSON schedule file
    :type schedule_path: Path
    :return: (block_schedule, unblock_schedule)
    :rtype: (List[Dict], List[Dict])
    """
    schedule_data = load_schedule(schedule_path)

    if schedule_data is None:
        # Default fallback schedule
        default_intervals = [
            {"days": [2, 3], "start": {"Hour": 11, "Minute": 0}, "end": {"Hour": 15, "Minute": 0}},
            {"days": [4], "start": {"Hour": 10, "Minute": 0}, "end": {"Hour": 18, "Minute": 0}},
            {"days": [1, 5], "start": {"Hour": 12, "Minute": 0}, "end": {"Hour": 16, "Minute": 0}},
        ]
        return process_intervals_schedule(default_intervals)

    if 'intervals' in schedule_data:
        return process_intervals_schedule(schedule_data['intervals'])

    # Legacy format with block/unblock keys
    block_schedule = schedule_data.get('block', [])
    unblock_schedule = schedule_data.get('unblock', [])
    return block_schedule, unblock_schedule


def setup_block_unblock_jobs(
        user: str,
        script_path: Path,
        block_schedule: List[Dict],
        unblock_schedule: List[Dict],
        launch_agents: Path,
) -> None:
    """
    Setup the block and unblock launchd jobs.

    :param user: username
    :type user: str
    :param script_path: path to main script
    :type script_path: Path
    :param block_schedule: block schedule
    :type block_schedule: List[Dict]
    :param unblock_schedule: unblock schedule
    :type unblock_schedule: List[Dict]
    :param launch_agents: path to LaunchAgents directory
    :type launch_agents: Path
    """
    block_label = f'com.{user}.workblocker.block'
    block_plist = generate_plist(block_label, str(script_path), 'block', LOG_DIR, block_schedule)
    save_plist(block_plist, launch_agents / f'{block_label}.plist')
    reload_plist(launch_agents / f'{block_label}.plist')

    unblock_label = f'com.{user}.workblocker.unblock'
    unblock_plist = generate_plist(unblock_label, str(script_path), 'unblock', LOG_DIR, unblock_schedule)
    save_plist(unblock_plist, launch_agents / f'{unblock_label}.plist')
    reload_plist(launch_agents / f'{unblock_label}.plist')


def setup_relock_main_job(user: str, script_path: Path, launch_agents: Path) -> Path:
    """
    Setup the main relock job that runs every N seconds.

    :param user: username
    :type user: str
    :param script_path: path to main script
    :type script_path: Path
    :param launch_agents: path to LaunchAgents directory
    :type launch_agents: Path
    :return: path to the relock plist
    :rtype: Path
    """
    relock_label = f'com.{user}.workblocker.relock'
    relock_plist_path = launch_agents / f'{relock_label}.plist'
    relock_plist = generate_relock_plist(relock_label, str(script_path), LOG_DIR, interval_seconds=300)
    save_plist(relock_plist, relock_plist_path)
    return relock_plist_path


def setup_relock_loader_jobs(
        user: str,
        relock_plist_path: Path,
        block_schedule: List[Dict],
        unblock_schedule: List[Dict],
        launch_agents: Path
) -> None:
    """
    Setup the relock loader and unloader jobs.

    :param user: username
    :type user: str
    :param relock_plist_path: path to the relock plist
    :type relock_plist_path: Path
    :param block_schedule: block schedule
    :type block_schedule: List[Dict]
    :param unblock_schedule: unblock schedule
    :type unblock_schedule: List[Dict]
    :param launch_agents: path to LaunchAgents directory
    :type launch_agents: Path
    """
    # --- Loader (shifted block schedule) ---
    relock_load_label = f'com.{user}.workblocker.relock_loader'
    shifted_block_schedule = shift_schedule(block_schedule, 10)
    relock_load_plist = generate_relock_loader_plist(
        relock_load_label,
        'load',
        relock_plist_path,
        LOG_DIR,
        shifted_block_schedule
    )
    save_plist(relock_load_plist, launch_agents / f'{relock_load_label}.plist')
    reload_plist(launch_agents / f'{relock_load_label}.plist')

    # --- Unloader (unblock time) ---
    relock_unload_label = f'com.{user}.workblocker.relock_unloader'
    relock_unload_plist = generate_relock_loader_plist(
        relock_unload_label,
        'unload',
        relock_plist_path,
        LOG_DIR,
        unblock_schedule
    )
    save_plist(relock_unload_plist, launch_agents / f'{relock_unload_label}.plist')
    reload_plist(launch_agents / f'{relock_unload_label}.plist')


def setup_launch_agents(user: str, script_path: Path, block_schedule: List[Dict], unblock_schedule: List[Dict]) -> None:
    """
    Setup all launch agents: block/unblock jobs, relock job, relock loaders.

    :param user: username
    :type user: str
    :param script_path: path to main script
    :type script_path: Path
    :param block_schedule: list of block schedule dicts
    :type block_schedule: List[Dict]
    :param unblock_schedule: list of unblock schedule dicts
    :type unblock_schedule: List[Dict]
    """
    launch_agents = Path.home() / 'Library' / 'LaunchAgents'
    launch_agents.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Block / Unblock
    setup_block_unblock_jobs(user, script_path, block_schedule, unblock_schedule, launch_agents)

    # 2. Relock main task
    relock_plist_path = setup_relock_main_job(user, script_path, launch_agents)

    # 3. Relock loaders (load/unload at proper time)
    setup_relock_loader_jobs(user, relock_plist_path, block_schedule, unblock_schedule, launch_agents)



def main():
    """Main function to parse arguments, load schedule, and setup launch agents."""
    args = parse_args()
    user = getpass.getuser()
    script_path: Path = Path(args.script_path).expanduser()
    schedule_path: Path = args.schedule

    block_schedule, unblock_schedule = get_schedule(schedule_path)
    setup_launch_agents(user, script_path, block_schedule, unblock_schedule)


if __name__ == '__main__':
    main()
