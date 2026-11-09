#!/usr/bin/env bash
set -euo pipefail
# Values arrive as environment variables, never interpolated into shell source.
: "${VPS_HOST:?Missing VPS_HOST secret}"
: "${VPS_USER:?Missing VPS_USER secret}"
: "${VPS_SSH_KEY:?Missing VPS_SSH_KEY secret}"
: "${VPS_PORT:?Missing VPS_PORT secret}"
: "${VPS_KNOWN_HOSTS:?Missing pinned VPS_KNOWN_HOSTS secret}"
: "${PROJECT_PATH:?Missing project path}"
: "${TARGET_SHA:?Missing target SHA}"
: "${REPOSITORY:?Missing repository}"
[[ "$VPS_HOST" =~ ^[a-zA-Z0-9][a-zA-Z0-9.:-]*$ ]] || { echo 'Invalid SSH host'; exit 1; }
[[ "$VPS_USER" =~ ^[a-z_][a-z0-9_-]*$ && "$VPS_USER" != root ]] || { echo 'Use a non-root deploy user'; exit 1; }
[[ "$VPS_PORT" =~ ^[0-9]{1,5}$ ]] && ((10#$VPS_PORT >= 1 && 10#$VPS_PORT <= 65535)) || { echo 'Invalid SSH port'; exit 1; }
[[ "${CHECK_ONLY:-true}" == true || "${CHECK_ONLY:-true}" == false ]] || exit 1
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
ssh_dir=$(mktemp -d)
trap 'rm -rf -- "$ssh_dir"' EXIT
chmod 700 "$ssh_dir"
printf '%s\n' "$VPS_SSH_KEY" > "$ssh_dir/key"
chmod 600 "$ssh_dir/key"
printf '%s\n' "$VPS_KNOWN_HOSTS" > "$ssh_dir/known_hosts"
payload=$(python3 - <<'PY'
import base64, json, os
config = {'path': os.environ['PROJECT_PATH'], 'sha': os.environ['TARGET_SHA'],
          'repository': os.environ['REPOSITORY'], 'user': os.environ['VPS_USER'],
          'check_only': os.environ.get('CHECK_ONLY', 'true') == 'true'}
print(base64.b64encode(json.dumps(config).encode()).decode())
PY
)
unset VPS_SSH_KEY VPS_KNOWN_HOSTS
ssh -F /dev/null -T -i "$ssh_dir/key" -p "$VPS_PORT" \
  -o BatchMode=yes -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes \
  -o HostKeyAlias=mixwithme-vps -o UserKnownHostsFile="$ssh_dir/known_hosts" \
  -o GlobalKnownHostsFile=/dev/null -o ConnectTimeout=15 \
  -o ServerAliveInterval=15 -o ServerAliveCountMax=3 \
  "$VPS_USER@$VPS_HOST" "python3 - '$payload'" < "$script_dir/deploy_pull.py"
