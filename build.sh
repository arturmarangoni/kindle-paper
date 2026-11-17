#!/bin/sh
# Imprime o jornal: sobe um servidor Stop Press temporário, baixa as páginas que o Kindle lê e grava tudo em
# ./public (o site estático). Uso: SP=<pasta do stop-press> sh build.sh
set -e
ROOT=$(cd "$(dirname "$0")" && pwd)
SP=$(cd "${SP:-$ROOT/stop-press-src}" && pwd)
OUT="$ROOT/public"
PORT=${PORT:-8770}
PY=${PY:-python}
mkdir -p "$OUT" "$ROOT/data"

# Diagnóstico: o clima vem do Open-Meteo, que limita pedidos por IP (os IPs do GitHub são compartilhados).
echo "Open-Meteo: $(curl -s -m 20 -o /tmp/om.json -w '%{http_code}' \
  'https://api.open-meteo.com/v1/forecast?latitude=41.158&longitude=-8.629&current=temperature_2m') $(head -c 200 /tmp/om.json)"

(cd "$SP/server" && STOP_PRESS_CONFIG="$ROOT/stop-press.toml" PAPER_DATA_DIR="$ROOT/data" \
  exec "$PY" -m uvicorn paper.app:app --port "$PORT") &
PID=$!
trap 'kill $PID 2>/dev/null' EXIT INT TERM

i=0
until curl -sf -o /dev/null "http://127.0.0.1:$PORT/kindle.png"; do
  i=$((i + 1)); [ $i -lt 90 ] || { echo "o servidor não subiu"; exit 1; }
  sleep 2
done

get() { curl -sf --max-time 900 -o "$OUT/$2" "http://127.0.0.1:$PORT/$1"; }
get "kindle.png" kindle.png
get "ui.png?k=auto" ui.png          # a página que o Kindle desenha ao acordar
get "offline.tar" offline.tar       # o jornal inteiro, que os botões do Kindle folheiam
get "edition.mobi" edition.mobi || echo "edição .mobi não gerada (Calibre ausente?)"
date -u +%Y-%m-%dT%H:%MZ > "$OUT/printed.txt"
touch "$OUT/.nojekyll"
cat > "$OUT/index.html" <<'EOF'
<!doctype html><meta charset="utf-8"><title>Stop Press</title>
<body style="margin:0;background:#ddd;display:grid;place-items:center;min-height:100vh">
<img src="kindle.png" alt="Capa do jornal" style="max-width:100%;box-shadow:0 2px 12px #0003">
EOF
ls -la "$OUT"
