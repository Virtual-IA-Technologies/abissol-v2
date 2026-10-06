#!/usr/bin/env bash
set -euo pipefail
umask 027
commit="$1"
[[ "$commit" =~ ^[a-f0-9]{40}$ ]] || exit 2
root=/home/abissol/apps/abissol-v2
web=/home/abissol/public_html/v2.abissol.org
release="$root/releases/$commit"
test -f "$root/BackEnd/.env"
test -d "$web"
test "$(realpath "$web")" = "$web"
mkdir -p "$release" "$root/shared/storage" "$root/backups"
chmod 700 "$root/backups"
tar -xzf "$root/incoming-$commit.tar.gz" -C "$release"
ln -sfn "$root/BackEnd/.env" "$release/BackEnd/.env"
ln -sfn "$root/shared/storage" "$release/BackEnd/storage"
chown -R abissol:abissol "$release" "$root/shared"
if ! test -x "$root/.venv/bin/python"; then
  runuser -u abissol -- /usr/bin/python3.12 -m venv "$root/.venv"
fi
runuser -u abissol -- "$root/.venv/bin/python" -m pip install --disable-pip-version-check -q -r "$release/BackEnd/requirements.txt"
if test "$(mysql -NBe "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='abissol_v2'")" -gt 0; then
  mysqldump --single-transaction --routines --triggers abissol_v2 | gzip > "$root/backups/abissol_v2-$(date +%Y%m%d-%H%M%S).sql.gz"
fi
cd "$release/BackEnd"
runuser -u abissol -- "$root/.venv/bin/python" -m alembic upgrade head
runuser -u abissol -- "$root/.venv/bin/python" - <<'PY'
from app.database import SessionLocal
from app.bootstrap import seed_platform
from app.services.documentation import sync_repository
with SessionLocal() as db:
    seed_platform(db)
    db.commit()
    sync_repository(db)
print('Plataforma y documentación sincronizadas.')
PY
previous=$(readlink "$root/current" || true)
ln -sfn "$release" "$root/current.next"
mv -Tf "$root/current.next" "$root/current"
cat > /etc/systemd/system/abissol-v2.service <<'SERVICE'
[Unit]
Description=ABISSOL V2 FastAPI
After=network.target mariadb.service
[Service]
User=abissol
Group=abissol
WorkingDirectory=/home/abissol/apps/abissol-v2/current/BackEnd
ExecStart=/home/abissol/apps/abissol-v2/.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8015 --proxy-headers --forwarded-allow-ips=127.0.0.1
Restart=on-failure
RestartSec=3
UMask=0027
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=full
[Install]
WantedBy=multi-user.target
SERVICE
systemctl daemon-reload
systemctl enable abissol-v2.service >/dev/null
systemctl restart abissol-v2.service
ready=false
for attempt in $(seq 1 20); do
  if curl -fsS http://127.0.0.1:8015/health/ready >/dev/null; then ready=true; break; fi
  sleep 1
done
if test "$ready" != true; then
  if test -n "$previous"; then ln -sfn "$previous" "$root/current"; systemctl restart abissol-v2.service; fi
  echo 'La API no pasó la comprobación de salud; frontend conservado.' >&2
  exit 1
fi
for protocol in std ssl; do
  include="/etc/apache2/conf.d/userdata/$protocol/2_4/abissol/v2.abissol.org"
  mkdir -p "$include"
  cat > "$include/abissol-v2.conf" <<'APACHE'
ProxyPreserveHost On
ProxyPass /abissol/api/v1/ http://127.0.0.1:8015/abissol/api/v1/ timeout=180
ProxyPassReverse /abissol/api/v1/ http://127.0.0.1:8015/abissol/api/v1/
ProxyPass /health/ http://127.0.0.1:8015/health/
ProxyPassReverse /health/ http://127.0.0.1:8015/health/
APACHE
  if test "$protocol" = ssl; then echo 'RequestHeader set X-Forwarded-Proto "https"' >> "$include/abissol-v2.conf"; else echo 'RequestHeader set X-Forwarded-Proto "http"' >> "$include/abissol-v2.conf"; fi
done
rsync -a --delete --exclude='.well-known' --exclude='.htaccess' --exclude='.user.ini' --exclude='php.ini' "$release/FrontEnd/frontend-app/dist/" "$web/"
if test -f "$web/.htaccess" && ! test -f "$root/backups/initial-htaccess"; then cp "$web/.htaccess" "$root/backups/initial-htaccess"; fi
cat > "$web/.htaccess" <<'HTACCESS'
Options -Indexes
RewriteEngine On
RewriteCond %{HTTPS} !=on
RewriteRule ^ https://v2.abissol.org%{REQUEST_URI} [R=301,L]
RewriteRule ^(?:abissol/api/v1|health)(?:/|$) - [L]
RewriteCond %{REQUEST_FILENAME} !-f
RewriteCond %{REQUEST_FILENAME} !-d
RewriteRule ^ index.html [L]
<IfModule mod_headers.c>
<FilesMatch "^index\.html$">
Header set Cache-Control "no-cache, no-store, must-revalidate"
</FilesMatch>
<FilesMatch "\.(js|mjs|css|woff2)$">
Header set Cache-Control "public, max-age=31536000, immutable"
</FilesMatch>
Header always set X-Content-Type-Options nosniff
Header always set X-Frame-Options DENY
</IfModule>
HTACCESS
chown -R abissol:abissol "$web"
/usr/local/cpanel/scripts/rebuildhttpdconf >/dev/null
/usr/sbin/httpd -t
/usr/local/cpanel/scripts/restartsrv_httpd --graceful >/dev/null
curl --retry 3 --retry-delay 1 -fsS https://v2.abissol.org/health/ready
curl -fsS https://v2.abissol.org/ | grep -q '<title>ABISSOL'
printf '%s\n' "$commit" > "$root/deployed-commit"
rm -f "$root/incoming-$commit.tar.gz"
echo 'Publicación HTTPS verificada.'
