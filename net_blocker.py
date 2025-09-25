#!/usr/bin/env python3

import os
import sys
import subprocess
from pathlib import Path

from commons import log, notify, check_work_mode_file


# === Constants ===
BASE_DIR = Path(__file__).resolve().parent
DOMAINS_FILE = BASE_DIR / "work_domains.txt"
ANCHOR_FILE = "/etc/pf.anchors/work_blocker"
PF_CONF_FILE = "/etc/pf.conf"
ANCHOR_NAME = "work_blocker"
OSASCRIPT_BIN = "/usr/bin/osascript"
PFCTL_BIN = "/sbin/pfctl"



def resolve_ips(domains: list[str]) -> list[str]:
    """
    Resolve a list of domain names to their IP addresses (IPv4 only).

    :param domains: List of domains
    :type domains: list
    :return: List of IP addresses
    :rtype: list
    """
    ip_addresses = set()
    for domain in domains:
        try:
            result = subprocess.run(["dig", "+short", domain], capture_output=True, text=True)
            lines = result.stdout.strip().split("\n")
            for line in lines:
                line = line.strip()
                if line and all(c.isdigit() or c == "." for c in line):
                    ip_addresses.add(line)
        except Exception as e:
            log(f"Failed to resolve {domain}: {e}")
    return sorted(ip_addresses)


def load_domains() -> list[str]:
    """
    Load domain names from a file.

    :return: List of domains
    :rtype: list
    """
    if not DOMAINS_FILE.exists():
        log(f"Domains file not found: {DOMAINS_FILE}")
        sys.exit(1)

    with open(DOMAINS_FILE, "r") as f:
        return [line.strip() for line in f if line.strip() and not line.startswith("#")]


def write_anchor_file(ips: list[str]) -> None:
    """
    Write PF rules to the anchor file to block specified IPs.

    :param ips: List of IP addresses
    :type ips: list
    """
    try:
        with open(ANCHOR_FILE, "w") as f:
            for ip in ips:
                f.write(f"block drop out quick to {ip}\n")
        log(f"Saved {len(ips)} IPs to anchor file: {ANCHOR_FILE}")
    except PermissionError:
        log(f"Permission denied: cannot write to {ANCHOR_FILE}. Use sudo.")
        sys.exit(1)


def ensure_pf_conf_includes_anchor() -> None:
    """Ensure /etc/pf.conf includes the custom anchor for blocking rules."""
    anchor_rule = f'anchor "{ANCHOR_NAME}"'
    anchor_load = f'load anchor "{ANCHOR_NAME}" from "{ANCHOR_FILE}"'

    with open(PF_CONF_FILE, "r") as f:
        contents = f.read()

    if anchor_rule not in contents:
        try:
            with open(PF_CONF_FILE, "a") as f:
                f.write(f"\n{anchor_rule}\n{anchor_load}\n")
            log("Added anchor rules to /etc/pf.conf")
        except PermissionError:
            log(f"Permission denied: cannot write to {PF_CONF_FILE}. Use sudo.")
            sys.exit(1)


def apply_pf() -> None:
    """Apply the pf rules from the updated config."""
    try:
        subprocess.run([PFCTL_BIN, "-f", PF_CONF_FILE], check=True)
        subprocess.run([PFCTL_BIN, "-e"], check=False)
        log("pfctl rules applied and pf enabled")
    except subprocess.CalledProcessError as e:
        log(f"Failed to apply pfctl rules: {e}")
        sys.exit(1)


def disable_pf_block() -> None:
    """Clear anchor file and reload pf without blocking rules."""
    try:
        # Just empty the anchor file instead of deleting it
        with open(ANCHOR_FILE, "w") as f:
            pass
        log(f"Cleared anchor file: {ANCHOR_FILE}")
        subprocess.run([PFCTL_BIN, "-f", PF_CONF_FILE], check=True)
        log("pfctl reloaded with cleared rules")
    except Exception as e:
        log(f"Failed to disable PF blocking rules: {e}")
        sys.exit(1)


def usage() -> None:
    """Print usage instructions and exit."""
    print(
        "Usage:\n"
        f"  {sys.argv[0]} block     # Block access to domains\n"
        f"  {sys.argv[0]} unblock   # Unblock access\n"
    )
    sys.exit(1)


def main() -> None:
    """Main entry point to handle block/unblock commands."""
    if len(sys.argv) != 2:
        usage()

    if os.geteuid() != 0:
        print("❌ This script must be run with sudo.")
        sys.exit(1)

    action = sys.argv[1]

    if action == "block":
        log("📡 Blocking network resources...")
        domains = load_domains()
        log(f"Loaded {len(domains)} domains")
        ips = resolve_ips(domains)
        log(f"Resolved {len(ips)} IP addresses")
        write_anchor_file(ips)
        ensure_pf_conf_includes_anchor()
        apply_pf()
        notify("Network access is now blocked. Time to enjoy your life!")
        log("✅ Network access blocked.")
    elif action == "unblock":
        check_work_mode_file()
        log("🔓 Unblocking network access...")
        disable_pf_block()
        notify("Network access is unblocked. Stay responsible!")
        log("✅ Network access unblocked.")
    else:
        usage()


if __name__ == "__main__":
    main()
