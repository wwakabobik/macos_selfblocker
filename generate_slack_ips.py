import subprocess

slack_domains = ["slack.com", "slack-edge.com", "slack-msgs.com"]


def get_ip_addresses(domains):
    ip_addresses = set()
    for domain in domains:
        try:
            result = subprocess.run(["dig", "+short", domain], capture_output=True, text=True)
            lines = result.stdout.strip().split("\n")
            for line in lines:
                if line and all(c.isdigit() or c == "." for c in line):  # IPv4 only
                    ip_addresses.add(line)
        except Exception as e:
            print(f"Error resolving {domain}: {e}")
    return sorted(ip_addresses)


def write_to_file(ip_list, filepath="/etc/pf.anchors/slack_ips.txt"):
    with open(filepath, "w") as f:
        for ip in ip_list:
            f.write(f"{ip}\n")
    print(f"Saved {len(ip_list)} IPs to {filepath}")


if __name__ == "__main__":
    ips = get_ip_addresses(slack_domains)
    write_to_file(ips)
