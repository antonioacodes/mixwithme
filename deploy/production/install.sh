#!/bin/bash
# One-time administrator setup. Inspect before running; takes checkout and domain.
set -euo pipefail
export PATH=/usr/sbin:/usr/bin:/sbin:/bin
[[ $EUID == 0 && $# == 2 ]] || exit 2
repo=$(realpath "$1")
source_dir=$(cd "$(dirname "$0")" && pwd)
domain=$2
[[ $domain =~ ^[a-zA-Z0-9.-]+$ && -d $repo/.git ]] || exit 2
config=/etc/nginx/sites-enabled/$domain.conf
[[ -f $config && -f /etc/nginx/ssl-certificates/$domain.crt && -f /etc/nginx/ssl-certificates/$domain.key ]] || exit 2
apt-get update -qq
apt-get install -y python3.12-venv libsndfile1
id mixwithme >/dev/null 2>&1 || useradd --system --home-dir /var/lib/mixwithme --shell /usr/sbin/nologin mixwithme
install -d -m 755 -o deploy -g deploy /opt/mixwithme /opt/mixwithme/releases
install -d -m 700 -o mixwithme -g mixwithme /var/lib/mixwithme
install -d -m 755 -o mixwithme -g mixwithme /var/cache/mixwithme
if [[ ! -f /etc/mixwithme.env ]]; then
  (umask 077; printf 'API_TOKEN=%s\nDATA_DIR=/var/lib/mixwithme\n' "$(openssl rand -hex 32)" > /etc/mixwithme.env)
fi
install -m 755 -o root -g root "$source_dir/restart.sh" /usr/local/sbin/mixwithme-restart
for name in api worker web; do
  install -m 644 "$source_dir/mixwithme-$name.service" /etc/systemd/system/
done
printf 'deploy ALL=(root) NOPASSWD: /usr/local/sbin/mixwithme-restart\n' > /etc/sudoers.d/mixwithme
chmod 440 /etc/sudoers.d/mixwithme
visudo -cf /etc/sudoers.d/mixwithme
systemctl daemon-reload
systemctl enable mixwithme-api mixwithme-worker mixwithme-web
backup=$(mktemp /etc/nginx/mixwithme-vhost-backup.XXXXXX)
cp -p "$config" "$backup"
python3 - "$domain" "$config" "$repo" <<'PY'
import sys
from pathlib import Path
domain, target, repo = sys.argv[1:]
template = '''limit_req_zone $binary_remote_addr zone=mixwithme:10m rate=5r/s;
limit_conn_zone $binary_remote_addr zone=mixwithme_conn:10m;
server {
    listen 80;
    listen [::]:80;
    server_name DOMAIN;
    location ^~ /.well-known/acme-challenge/ { root "CHECKOUT"; }
    location / { return 301 https://$host$request_uri; }
}
server {
    listen 443 ssl;
    listen [::]:443 ssl;
    http2 on;
    server_name DOMAIN;
    ssl_certificate /etc/nginx/ssl-certificates/DOMAIN.crt;
    ssl_certificate_key /etc/nginx/ssl-certificates/DOMAIN.key;
    location ^~ /.well-known/acme-challenge/ { root "CHECKOUT"; }
    location ~ ^/api/tracks/[a-f0-9]+/versions$ {
        client_max_body_size 250m;
        client_body_timeout 120s;
        limit_req zone=mixwithme burst=10 nodelay;
        limit_conn mixwithme_conn 4;
        rewrite ^/api/(.*)$ /$1 break;
        proxy_pass http://127.0.0.1:8100;
        proxy_request_buffering off;
        proxy_read_timeout 190s;
        proxy_send_timeout 130s;
        proxy_set_header Host $host;
        proxy_set_header Authorization $http_authorization;
        add_header Cache-Control "no-store" always;
        add_header X-Content-Type-Options "nosniff" always;
    }
    location /api/ {
        client_max_body_size 512k;
        limit_req zone=mixwithme burst=20 nodelay;
        limit_conn mixwithme_conn 8;
        proxy_pass http://127.0.0.1:8100/;
        proxy_set_header Host $host;
        proxy_set_header Authorization $http_authorization;
        add_header Cache-Control "no-store" always;
        add_header X-Content-Type-Options "nosniff" always;
    }
    location / {
        proxy_pass http://127.0.0.1:3100;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
'''
Path(target).write_text(template.replace('DOMAIN', domain).replace('CHECKOUT', repo))
PY
if ! nginx -t; then
  cp -p "$backup" "$config"
  echo 'Nginx validation failed; previous configuration restored.' >&2
  exit 1
fi
systemctl reload nginx
echo 'Setup complete. Run the release script as deploy from the checkout.'
