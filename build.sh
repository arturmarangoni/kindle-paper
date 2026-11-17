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

(cd "$SP/server" && PYTHONPATH="$ROOT/patches" STOP_PRESS_CONFIG="$ROOT/stop-press.toml" PAPER_DATA_DIR="$ROOT/data" \
  exec "$PY" -m uvicorn paper.app:app --port "$PORT") &
PID=$!
trap 'kill $PID 2>/dev/null' EXIT INT TERM

i=0
until curl -sf -o /dev/null "http://127.0.0.1:$PORT/kindle.png"; do
  i=$((i + 1)); [ $i -lt 90 ] || { echo "o servidor não subiu"; exit 1; }
  sleep 2
done

# Aquecimento: o primeiro pedido dispara as buscas (clima, mercados, notícias). Espera elas chegarem antes de
# imprimir, senão a capa pode sair sem o clima.
sleep 15
curl -sf -o /dev/null "http://127.0.0.1:$PORT/kindle.png"

get() { curl -sf --max-time 900 -o "$OUT/$2" "http://127.0.0.1:$PORT/$1"; }
get "kindle.png" kindle.png
get "ui.png?k=auto" ui.png          # a página que o Kindle desenha ao acordar
get "offline.tar" offline.tar       # o jornal inteiro, que os botões do Kindle folheiam
get "edition.mobi" edition.mobi || echo "edição .mobi não gerada (Calibre ausente?)"
date -u +%Y-%m-%dT%H:%MZ > "$OUT/printed.txt"
touch "$OUT/.nojekyll"
# As mesmas páginas que o Kindle folheia, soltas, para ler no navegador.
rm -rf "$OUT/pages" && mkdir -p "$OUT/pages"
tar -xf "$OUT/offline.tar" -C "$OUT/pages"
PAGES=$(cat "$OUT/pages/pages.txt")
CHAPTERS=$(tr '\n' ',' < "$OUT/pages/chapters.txt" | sed 's/,$//')
cat > "$OUT/index.html" <<EOF
<!doctype html><html lang="pt"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Stop Press</title>
<style>
  body{margin:0;background:#d9d6cf;font:15px/1.4 system-ui,sans-serif;color:#222;display:flex;flex-direction:column;align-items:center;min-height:100vh}
  #page{width:min(600px,100vw);aspect-ratio:3/4;background:#fff;box-shadow:0 2px 14px #0003;margin:16px 0 8px;cursor:pointer;display:block}
  nav{display:flex;gap:8px;flex-wrap:wrap;justify-content:center;padding:0 16px 16px}
  button{font:inherit;padding:8px 14px;border:1px solid #888;border-radius:6px;background:#f6f4ef;cursor:pointer}
  #n{align-self:center;min-width:6em;text-align:center}
  p{margin:0 16px 20px;max-width:600px;text-align:center;color:#555;font-size:13px}
</style>
<img id="page" alt="Página do jornal">
<nav>
  <button id="ps" title="Matéria anterior (↑)">⇤ matéria</button>
  <button id="pp" title="Página anterior (←)">← página</button>
  <span id="n"></span>
  <button id="np" title="Próxima página (→ ou clique na página)">página →</button>
  <button id="ns" title="Próxima matéria (↓)">matéria ⇥</button>
  <button id="home" title="Capa">capa</button>
</nav>
<p>Impresso em $(date -u '+%d/%m/%Y %H:%M') UTC · as mesmas páginas que o Kindle folheia. Setas do teclado também funcionam.</p>
<script>
const N=$PAGES, CH=[$CHAPTERS]; let p=+(location.hash.slice(1))||1;
const img=document.getElementById('page'), n=document.getElementById('n');
function show(){p=Math.min(Math.max(p,1),N);img.src='pages/p'+String(p).padStart(3,'0')+'.png';n.textContent=p+' / '+N;history.replaceState(null,'','#'+p)}
const nextStory=()=>{const c=CH.find(c=>c>p);if(c)p=c},prevStory=()=>{let t=1;for(const c of CH)if(c<p)t=c;p=t};
const act={np:()=>p++,pp:()=>p--,ns:nextStory,ps:prevStory,home:()=>p=1};
for(const id in act)document.getElementById(id).onclick=()=>{act[id]();show()};
img.onclick=()=>{p++;show()};
addEventListener('keydown',e=>{const k={ArrowRight:'np',ArrowLeft:'pp',ArrowDown:'ns',ArrowUp:'ps',Home:'home'}[e.key];if(k){e.preventDefault();act[k]();show()}});
show();
</script>
EOF
ls -la "$OUT"
