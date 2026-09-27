#!/usr/bin/env bash
# Tek konteyner dağıtımı (Run:ai vb.): bağımlılıkları kur, arayüzü derle, API + arayüzü tek porttan sun.
# Gerekenler: python3 >= 3.10, node >= 20.   Kullanım: bash deploy/start.sh   (port: $PORT, varsayılan 8080)
set -euo pipefail
cd "$(dirname "$0")/.."
[ -w "${HOME:-/}" ] || export HOME=/tmp       # rastgele kullanıcıyla çalışan kümelerde yazılabilir ev dizini

python3 -m venv .venv
.venv/bin/pip install --no-cache-dir -q -r requirements.txt gunicorn
(cd ui && npm ci --no-audit --no-fund --loglevel=error && npx vite build)

# tek işçi: işler, SSE akışları ve önbellekler bellekte
exec .venv/bin/gunicorn --workers 1 --threads 8 --timeout 180 --bind "0.0.0.0:${PORT:-8080}" backend.api.app:app
