#!/usr/bin/env bash
# Run as deploy. Runtime and data are outside the public checkout.
set -euo pipefail
export PATH=/usr/bin:/bin
export NEXT_TELEMETRY_DISABLED=1
export API_INTERNAL_URL=http://127.0.0.1:8100
export NODE_OPTIONS=--max-old-space-size=2048
repo=$(pwd)
sha=${1:?commit required}
[[ $sha =~ ^[0-9a-f]{40}$ ]] || exit 2
[[ $(git rev-parse HEAD) == "$sha" ]] || exit 2
base=/opt/mixwithme
exec 9>"$base/release.lock"
flock -n 9 || { echo 'Another release is running'; exit 1; }
[[ $(find "$base/releases" -mindepth 1 -maxdepth 1 -type d | wc -l) -lt 10 ]] || {
  echo 'Release retention limit reached; administrator must archive old releases.'; exit 1;
}
[[ $(df -Pk "$base" | awk 'NR==2 {print $4}') -gt 4194304 ]] || {
  echo 'At least 4 GiB free required for a build.'; exit 1;
}
release=$(mktemp -d "$base/releases/${sha:0:12}.XXXXXX")
chmod 755 "$release"
git archive "$sha" | tar -x -C "$release"
python3.12 -m venv "$release/backend/.venv"
"$release/backend/.venv/bin/pip" install --disable-pip-version-check -r "$release/backend/requirements.txt"
(cd "$release/backend" && .venv/bin/python -m pytest -q)
(cd "$release/frontend" && npm ci --no-fund --no-audit && npm audit --omit=dev --audit-level=high && npm run build)
mkdir -p "$release/frontend/.next/cache"
chmod -R a+rX "$release"
previous=$(readlink -f "$base/current" || true)
ln -s "$release" "$base/next"
mv -Tf "$base/next" "$base/current"
if ! sudo -n /usr/local/sbin/mixwithme-restart; then
  echo 'New release failed health checks.'
  if [[ -n $previous && -d $previous ]]; then
    ln -s "$previous" "$base/next"
    mv -Tf "$base/next" "$base/current"
    sudo -n /usr/local/sbin/mixwithme-restart
    echo 'Previous application release restored; database was not downgraded.'
  fi
  exit 1
fi
echo "Application release healthy: $sha"
