#!/usr/bin/env python3


import getpass
import json
import plistlib
import subprocess
import sys

from pathlib import Path
from typing import Dict, List, Optional, Tuple

from commons import log


BASE_DIR = Path(__file__).resolve().parent
MAIN_SCRIPT = BASE_DIR / 'work_control.py'
SCHEDULE_FILE = BASE_DIR / 'workblocker_schedule.json'
LOG_DIR = Path.home() / 'Library' / 'Logs' / 'workblocker'


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
    plist_dict = {
        'Label': label,
        'ProgramArguments': [str(script_path), action],
        'RunAtLoad': False,
        'StandardOutPath': str(log_dir / f"{label}_stdout.log"),
        'StandardErrorPath': str(log_dir / f"{label}_stderr.log"),
        'LimitLoadToSessionType': 'Aqua',
    }

    if schedule:
        plist_dict['StartCalendarInterval'] = schedule

    return plist_dict


def save_plist(plist_dict: Dict, filepath: Path):
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
    subprocess.run(['launchctl', 'unload', str(plist_path)], check=False)
    subprocess.run(['launchctl', 'load', str(plist_path)], check=False)
    log(f"Reloaded {plist_path}")


def main():
    """Main function to generate and save plist files for blocking and unblocking."""
    user = getpass.getuser()

    # Path to the script from argument or default
    if len(sys.argv) > 1:
        script_path = Path(sys.argv[1]).expanduser()
    else:
        script_path = MAIN_SCRIPT

    # Path to JSON schedule
    schedule_path = SCHEDULE_FILE
    schedule_data = load_schedule(schedule_path)

    if schedule_data is None:
        # If there is no custom schedule, use default from the task
        # By default, block outside work hours
        # Work intervals:
        # - Tuesday (2), Wednesday (3): 11-15
        # - Thursday (4): 10-18
        # - Monday (1), Friday (5): 12-16
        default_intervals = [
            {"days": [2, 3], "start": {"Hour": 11, "Minute": 0}, "end": {"Hour": 15, "Minute": 0}},
            {"days": [4], "start": {"Hour": 10, "Minute": 0}, "end": {"Hour": 18, "Minute": 0}},
            {"days": [1, 5], "start": {"Hour": 12, "Minute": 0}, "end": {"Hour": 16, "Minute": 0}},
        ]
        block_schedule, unblock_schedule = process_intervals_schedule(default_intervals)
    else:
        # If there is a custom schedule, expect either
        # "block": [], "unblock": [] (old format) or
        # "intervals": [{days,start,end}, ...]
        if 'intervals' in schedule_data:
            block_schedule, unblock_schedule = process_intervals_schedule(schedule_data['intervals'])
        else:
            # fallback на to old formatting (just list for для block/unblock)
            block_schedule = schedule_data.get('block', [])
            unblock_schedule = schedule_data.get('unblock', [])

    # Generate launch agents
    launch_agents = Path.home() / 'Library' / 'LaunchAgents'
    launch_agents.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    block_label = f'com.{user}.workblocker.block'
    block_plist = generate_plist(block_label, str(script_path), 'block', LOG_DIR, block_schedule)
    save_plist(block_plist, launch_agents / f'{block_label}.plist')

    unblock_label = f'com.{user}.workblocker.unblock'
    unblock_plist = generate_plist(unblock_label, str(script_path), 'unblock', LOG_DIR, unblock_schedule)
    save_plist(unblock_plist, launch_agents / f'{unblock_label}.plist')
    reload_plist(launch_agents / f'{block_label}.plist')
    reload_plist(launch_agents / f'{unblock_label}.plist')


if __name__ == '__main__':
    main()
