#!/bin/bash

# Обновляем IP
sudo python3 /path/to/generate_slack_ips.py

# Применяем правила
sudo pfctl -f /etc/pf.conf
sudo pfctl -e

echo "Slack заблокирован."
