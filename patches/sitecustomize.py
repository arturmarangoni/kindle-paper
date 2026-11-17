"""Carregado automaticamente pelo Python do servidor (PYTHONPATH=patches em build.sh).

1. Clima resiliente. Os runners do GitHub às vezes não conseguem conectar ao Open-Meteo (o handshake TLS expira):
   - toda chamada httpx.get que falha por rede é repetida algumas vezes;
   - a última resposta boa do Open-Meteo fica salva no data/ (que o cache do Actions guarda entre impressões),
     e é usada se todas as tentativas falharem, por até 12 horas.

2. Letra maior (a tela do Kindle 4 é pequena):
   - PAPER_ARTICLE_SIZE: qual dos 4 tamanhos do Stop Press usar no texto das matérias (0 a 3; o original é 1).
     No modo estático o Kindle não pode trocar o tamanho, então ele é escolhido aqui.
   - PAPER_TEXT_BUMP: quantos pixels a mais nas letras pequenas da capa e das seções (até 16 px), com o espaço
     entre linhas crescendo na mesma proporção. Títulos grandes ficam como estão. A página de mercados, uma
     tabela de colunas fixas, fica no tamanho original.
"""
import importlib.abc
import importlib.machinery
import os
import sys
import time
from pathlib import Path

import httpx

# --- 1. clima resiliente -------------------------------------------------------------------------

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

# --- 2. letra maior --------------------------------------------------------------------------------

ARTICLE_SIZE = os.environ.get("PAPER_ARTICLE_SIZE")
BUMP = int(os.environ.get("PAPER_TEXT_BUMP", "0") or 0)
SMALL = 16  # só letras até este tamanho crescem
FAMILIES = {"sans", "body", "italic", "head"}
_off = [0]  # > 0 enquanto desenha uma página que fica no tamanho original


def _patch_draw(draw):
    if not BUMP:
        return
    orig_font = draw.font
    ratio = {}  # id(fonte aumentada) -> proporção, para o espaço entre linhas

    def font(family, size, weight=400):
        if family in FAMILIES and size <= SMALL and not _off[0]:
            new = size + BUMP
            f = orig_font(family, new, weight)
            ratio[id(f)] = new / size
            return f
        return orig_font(family, size, weight)

    draw.font = font
    for name in ("para", "justified"):
        orig = getattr(draw.Page, name)

        def wrapped(self, x, y, w, s, f, leading=None, *a, _orig=orig, **kw):
            if leading:
                leading = round(leading * ratio.get(id(f), 1))
            return _orig(self, x, y, w, s, f, leading, *a, **kw)

        setattr(draw.Page, name, wrapped)


def _patch_ui(ui):
    if ARTICLE_SIZE is None:
        return
    size = max(0, min(len(ui.SIZES) - 1, int(ARTICLE_SIZE)))
    orig_load = ui.load_reader

    def load_reader():
        orig_load()
        ui._reader["size"] = size

    ui.load_reader = load_reader
    ui._reader["size"] = size


def _patch_pages(pages):
    if not BUMP:
        return
    orig = pages.markets

    def markets(*a, **kw):
        _off[0] += 1
        try:
            return orig(*a, **kw)
        finally:
            _off[0] -= 1

    pages.markets = markets
    pages.PAGES["markets"] = markets


_PATCHES = {"paper.draw": _patch_draw, "paper.ui": _patch_ui, "paper.pages": _patch_pages}


class _Finder(importlib.abc.MetaPathFinder):
    """Aplica os ajustes logo depois que o módulo do Stop Press é carregado, antes de quem o importa."""

    def find_spec(self, name, path, target=None):
        if name not in _PATCHES:
            return None
        spec = importlib.machinery.PathFinder.find_spec(name, path)
        if spec is None or spec.loader is None:
            return spec
        loader = spec.loader
        orig_exec = loader.exec_module

        def exec_module(module):
            orig_exec(module)
            _PATCHES[name](module)

        loader.exec_module = exec_module
        return spec


sys.meta_path.insert(0, _Finder())
