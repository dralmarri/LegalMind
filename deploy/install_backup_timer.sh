#!/usr/bin/env bash
set -euo pipefail
install -m 0644 /opt/LegalMind/deploy/legalmind-backup.service /etc/systemd/system/legalmind-backup.service
install -m 0644 /opt/LegalMind/deploy/legalmind-backup.timer /etc/systemd/system/legalmind-backup.timer
chmod +x /opt/LegalMind/deploy/backup.sh
systemctl daemon-reload
systemctl enable --now legalmind-backup.timer
systemctl list-timers legalmind-backup.timer --no-pager
