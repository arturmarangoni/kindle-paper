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

# Tamanho da letra (veja patches/sitecustomize.py): texto das matérias no 3º dos 4 tamanhos (0 a 3; o original é
# 1) e +2 px nas letras pequenas da capa e das seções.
export PAPER_ARTICLE_SIZE=${PAPER_ARTICLE_SIZE:-2} PAPER_TEXT_BUMP=${PAPER_TEXT_BUMP:-2}

# O servidor roda numa cópia do Stop Press, adaptada por patches/localize.py (português, seção Itália).
WORK="$ROOT/work"
rm -rf "$WORK" && cp -R "$SP/server" "$WORK"
"$PY" "$ROOT/patches/localize.py" "$WORK"

PID=
trap '[ -z "$PID" ] || kill $PID 2>/dev/null' EXIT INT TERM

get() { curl -sf --max-time "${3:-600}" -o "$OUT/$2.part" "http://127.0.0.1:$PORT/$1" && mv "$OUT/$2.part" "$OUT/$2"; }

# Uma impressão completa. Devolve erro se o servidor morrer no meio ou não responder.
print_once() {
  (cd "$WORK" && PYTHONPATH="$ROOT/patches" STOP_PRESS_CONFIG="$ROOT/stop-press.toml" PAPER_DATA_DIR="$ROOT/data" \
    exec "$PY" -m uvicorn paper.app:app --port "$PORT") &
  PID=$!
  i=0
  until curl -sf --max-time 60 -o /dev/null "http://127.0.0.1:$PORT/kindle.png"; do
    kill -0 $PID 2>/dev/null || { echo "o servidor morreu ao subir"; return 1; }
    i=$((i + 1)); [ $i -lt 60 ] || { echo "o servidor não subiu"; return 1; }
    sleep 2
  done
  # Aquecimento: o primeiro pedido dispara as buscas (clima, mercados, notícias). Espera elas chegarem antes de
  # imprimir, senão a capa pode sair sem o clima.
  sleep 15
  get "kindle.png" kindle.png || return 1
  get "kindle.png" kindle.png || return 1
  get "ui.png?k=auto" ui.png || return 1        # a página que o Kindle desenha ao acordar
  get "offline.tar" offline.tar || return 1     # o jornal inteiro, que os botões do Kindle folheiam
  get "edition.mobi" edition.mobi 300 || echo "edição .mobi não gerada (Calibre ausente?)"
}

# O servidor às vezes morre no meio ("free(): invalid size", nas fotos baixadas em paralelo): tenta até 3 vezes.
n=1
until print_once; do
  kill -9 $PID 2>/dev/null || true
  wait $PID 2>/dev/null || true
  [ $n -lt 3 ] || { echo "a impressão falhou 3 vezes"; exit 1; }
  n=$((n + 1))
  echo "a impressão falhou; tentativa $n de 3"
  sleep 5
done
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
<title>A&amp;I Press</title>
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
