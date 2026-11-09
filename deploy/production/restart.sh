#!/bin/bash
# Installed by root, never writable by deploy. No arguments or arbitrary commands.
set -euo pipefail
export PATH=/usr/sbin:/usr/bin:/sbin:/bin
[[ $# == 0 && $EUID == 0 ]] || exit 2
umask 077
trap 'systemctl start mixwithme-api mixwithme-worker || true' ERR
systemctl stop mixwithme-api mixwithme-worker
# Database snapshot before starting new code. WAVs remain in persistent storage.
if [[ -f /var/lib/mixwithme/mixwithme.sqlite3 ]]; then
  install -d -m 700 /var/backups/mixwithme
  python3 - <<'PY'
import sqlite3, time
with sqlite3.connect('/var/lib/mixwithme/mixwithme.sqlite3') as src:
    with sqlite3.connect('/var/backups/mixwithme/database-'+str(time.time_ns())+'.sqlite3') as dst:
        src.backup(dst)
PY
fi
systemctl restart mixwithme-api mixwithme-worker mixwithme-web
for attempt in $(seq 1 40); do
  if curl --fail --silent --max-time 2 http://127.0.0.1:8100/health >/dev/null &&
     curl --fail --silent --max-time 2 http://127.0.0.1:3100/ >/dev/null &&
     systemctl is-active --quiet mixwithme-worker; then
    exit 0
  fi
  sleep 2
done
echo 'Application health check failed' >&2
exit 1
