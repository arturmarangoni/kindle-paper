"""Carregado automaticamente pelo Python do servidor (PYTHONPATH=patches em build.sh).

Os runners do GitHub às vezes não conseguem conectar ao Open-Meteo (o handshake TLS expira). Aqui:
- toda chamada httpx.get que falha por rede é repetida algumas vezes;
- a última resposta boa do Open-Meteo fica salva no data/ (que o cache do Actions guarda entre impressões),
  e é usada se todas as tentativas falharem, por até 12 horas.
"""
import os
import time
from pathlib import Path

import httpx

_orig_get = httpx.get
_DATA = Path(os.environ.get("PAPER_DATA_DIR", "."))
_LAST = _DATA / "open-meteo-last.json"
_MAX_AGE = 12 * 3600


def _get(url, *args, **kw):
    is_weather = "open-meteo.com" in str(url)
    kw.setdefault("timeout", 15)
    if is_weather:
        kw["timeout"] = max(kw["timeout"], 25) if isinstance(kw["timeout"], (int, float)) else kw["timeout"]
    err = None
    for attempt in range(4):
        try:
            r = _orig_get(url, *args, **kw)
            if is_weather and r.status_code == 200:
                _LAST.write_bytes(r.content)
            return r
        except (httpx.TimeoutException, httpx.NetworkError) as e:
            err = e
            time.sleep(3 * (attempt + 1))
    if is_weather and _LAST.exists() and time.time() - _LAST.stat().st_mtime < _MAX_AGE:
        print(f"Open-Meteo indisponível ({err!r}); usando o último clima salvo", flush=True)
        return httpx.Response(200, content=_LAST.read_bytes(), request=httpx.Request("GET", str(url)))
    raise err


httpx.get = _get
