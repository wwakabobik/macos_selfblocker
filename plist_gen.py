#!/usr/bin/env python3
import plistlib
import sys
import json
from pathlib import Path
import getpass
from typing import List, Dict, Optional

def generate_plist(label: str, script_path: str, args: list, log_dir: Path, schedule: List[Dict]) -> dict:
    """
    Generate a plist dictionary for launchd.

    :param label: label for the launchd job
    :type label: str
    :param script_path: path to the script to run
    :type script_path: str
    :param args: list of arguments for the script
    :type args: list
    :param log_dir: directory for log files
    :type log_dir: Path
    :param schedule: list of schedule dictionaries
    :type schedule: list of dict
    :return: plist dictionary
    :rtype: dict
    """
    plist_dict = {
        'Label': label,
        'ProgramArguments': ['/usr/bin/sudo', script_path] + args,
        'RunAtLoad': True,
        'StandardOutPath': str(Path(log_dir) / f"{label}_stdout.log"),
        'StandardErrorPath': str(Path(log_dir) / f"{label}_stderr.log"),
        'LimitLoadToSessionType': 'Aqua',
    }

    if len(schedule) == 1:
        plist_dict['StartCalendarInterval'] = schedule[0]
    else:
        for i, entry in enumerate(schedule, start=1):
            plist_dict[f'StartCalendarInterval{i}'] = entry

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
    print(f"Plist saved to {filepath}")


def load_schedule(json_path: Path) -> Optional[Dict]:
    """
    Load schedule from a JSON file.

    :param json_path: path to the JSON file
    :type json_path: Path
    :return: schedule dictionary or None
    :rtype: dict or None
    """
    if not json_path.exists():
        print(f"File {json_path} does not exist, using default schedule.")
        return None
    try:
        with open(json_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading JSON schedule from {json_path}: {e}")
        return None


def process_intervals_schedule(schedule_intervals: List[Dict]) -> (List[Dict], List[Dict]):
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
            print(f"Skipping invalid interval (missing days/start/end): {interval}")
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


def main():
    """Main function to generate and save plist files for blocking and unblocking."""
    user = getpass.getuser()
    home = Path.home()

    # Path to the script from argument or default
    if len(sys.argv) > 1:
        script_path = Path(sys.argv[1]).expanduser()
    else:
        script_path = home / 'dir_blocker.py'

    # File with paths
    paths_file = home / '.work_paths.txt'
    log_dir = home / 'Library' / 'Logs'

    # Path to JSON schedule
    schedule_path = home / '.workblocker_schedule.json'

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

    # Generate plist for blocking
    block_label = f'com.{user}.workblocker.block'
    block_args = ['block', '-f', str(paths_file)]
    block_plist = generate_plist(block_label, str(script_path), block_args, log_dir, block_schedule)
    block_filepath = home / 'Library' / 'LaunchAgents' / f'{block_label}.plist'
    save_plist(block_plist, block_filepath)

    # Generate plist for unblocking
    unblock_label = f'com.{user}.workblocker.unblock'
    unblock_args = ['unblock', '-f', str(paths_file)]
    unblock_plist = generate_plist(unblock_label, str(script_path), unblock_args, log_dir, unblock_schedule)
    unblock_filepath = home / 'Library' / 'LaunchAgents' / f'{unblock_label}.plist'
    save_plist(unblock_plist, unblock_filepath)


if __name__ == '__main__':
    main()
