#!/usr/bin/env bash
# Deploy LangStudy to JD Cloud: local frontend build, rsync, venv, nginx, pm2.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REMOTE="${DEPLOY_HOST:-ubuntu@111.228.6.222}"
REMOTE_DIR="${DEPLOY_PATH:-/opt/langstudy}"
STAGING="/tmp/langstudy-deploy"
PORT="${DEPLOY_PORT:-8792}"
DOMAIN="${DEPLOY_DOMAIN:-lang.aidigitcloud.cn}"

echo "==> Build frontend"
cd "${ROOT}/frontend"
if [ ! -d node_modules ]; then
  npm install
fi
npm run build

echo "==> Stage to ${REMOTE}:${STAGING}"
ssh "${REMOTE}" "rm -rf '${STAGING}' && mkdir -p '${STAGING}'"
rsync -az \
  --exclude '.git' \
  --exclude 'node_modules' \
  --exclude 'frontend/node_modules' \
  --exclude 'backend/.venv' \
  --exclude 'backend/.env' \
  --exclude 'backend/data' \
  --exclude 'frontend/dist' \
  --exclude '__pycache__' \
  --exclude '.DS_Store' \
  "${ROOT}/" "${REMOTE}:${STAGING}/"
rsync -az "${ROOT}/frontend/dist/" "${REMOTE}:${STAGING}/frontend/dist/"

if [[ -f "${ROOT}/backend/.env" ]]; then
  echo "==> Upload local backend/.env as bootstrap (not committed)"
  scp "${ROOT}/backend/.env" "${REMOTE}:${STAGING}/backend/.env.localupload"
fi

echo "==> Install into ${REMOTE_DIR}, nginx, pm2"
ssh "${REMOTE}" bash -s <<REMOTE
set -euo pipefail
STAGING='${STAGING}'
REMOTE_DIR='${REMOTE_DIR}'
PORT='${PORT}'
DOMAIN='${DOMAIN}'

sudo mkdir -p "\${REMOTE_DIR}/backend/data"
sudo rsync -a --delete \
  --exclude '.env' \
  --exclude 'backend/.env' \
  --exclude 'backend/.venv' \
  --exclude 'backend/data' \
  --exclude 'node_modules' \
  "\${STAGING}/" "\${REMOTE_DIR}/"

if [[ -f "\${STAGING}/backend/.env.localupload" && ! -f "\${REMOTE_DIR}/backend/.env" ]]; then
  sudo cp "\${STAGING}/backend/.env.localupload" "\${REMOTE_DIR}/backend/.env"
fi
if [[ ! -f "\${REMOTE_DIR}/backend/.env" ]]; then
  sudo cp "\${REMOTE_DIR}/backend/.env.example" "\${REMOTE_DIR}/backend/.env"
fi
sudo chown -R ubuntu:ubuntu "\${REMOTE_DIR}"
# Nginx terminates TLS; rate limits must see the real client IP, not 127.0.0.1.
ENV_FILE="\${REMOTE_DIR}/backend/.env"
if grep -q '^TRUST_PROXY=' "\${ENV_FILE}"; then
  sed -i 's/^TRUST_PROXY=.*/TRUST_PROXY=1/' "\${ENV_FILE}"
else
  echo 'TRUST_PROXY=1' >> "\${ENV_FILE}"
fi

if [[ ! -x "\${REMOTE_DIR}/backend/.venv/bin/python" ]]; then
  python3.12 -m venv "\${REMOTE_DIR}/backend/.venv"
fi
"\${REMOTE_DIR}/backend/.venv/bin/pip" install -q -r "\${REMOTE_DIR}/backend/requirements.txt"

sudo tee /etc/nginx/conf.d/langstudy.conf >/dev/null <<NGINX
# LangStudy
server {
    listen 80;
    server_name \${DOMAIN};

    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location / {
        return 301 https://\\\$host\\\$request_uri;
    }
}

server {
    listen 443 ssl;
    server_name \${DOMAIN};

    ssl_certificate /etc/nginx/ssl/aidigitcloud.cn/fullchain.pem;
    ssl_certificate_key /etc/nginx/ssl/aidigitcloud.cn/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    client_max_body_size 30m;

    location / {
        proxy_pass http://127.0.0.1:\${PORT};
        proxy_http_version 1.1;
        proxy_set_header Host \\\$host;
        proxy_set_header X-Real-IP \\\$remote_addr;
        proxy_set_header X-Forwarded-For \\\$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \\\$scheme;
        proxy_set_header Connection "";
        proxy_read_timeout 180s;
        proxy_send_timeout 180s;
    }
}
NGINX

sudo nginx -t
sudo systemctl reload nginx

sudo -u ubuntu pm2 delete langstudy >/dev/null 2>&1 || true
sudo -u ubuntu pm2 start "\${REMOTE_DIR}/backend/.venv/bin/python" \
  --name langstudy \
  --cwd "\${REMOTE_DIR}/backend" \
  -- -m uvicorn app.main:app --host 127.0.0.1 --port "\${PORT}"
sudo -u ubuntu pm2 save

sleep 2
curl -fsS "http://127.0.0.1:\${PORT}/api/health"
echo
curl -fsS -o /dev/null -w "HTTPS %{http_code}\\n" --resolve "\${DOMAIN}:443:127.0.0.1" "https://\${DOMAIN}/api/health"
rm -rf "\${STAGING}"
REMOTE

echo "==> Done → https://${DOMAIN}"
