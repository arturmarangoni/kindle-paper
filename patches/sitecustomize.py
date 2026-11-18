"""Carregado automaticamente pelo Python do servidor (PYTHONPATH=patches em build.sh).

1. Clima resiliente. Os runners do GitHub às vezes não conseguem conectar ao Open-Meteo (o handshake TLS expira):
   - toda chamada httpx.get que falha por rede é repetida algumas vezes;
   - a última resposta boa do Open-Meteo fica salva no data/ (que o cache do Actions guarda entre impressões),
     e é usada, por até 24 horas, se todas as tentativas falharem ou se o Open-Meteo recusar o pedido (429).

2. Letra maior (a tela do Kindle 4 é pequena):
   - PAPER_ARTICLE_SIZE: qual dos 4 tamanhos do Stop Press usar no texto das matérias (0 a 3; o original é 1).
     No modo estático o Kindle não pode trocar o tamanho, então ele é escolhido aqui.
   - PAPER_TEXT_BUMP: quantos pixels a mais nas letras pequenas da capa e das seções (até 16 px), com o espaço
     entre linhas crescendo na mesma proporção. Títulos grandes ficam como estão. A página de mercados, uma
     tabela de colunas fixas, fica no tamanho original.

3. Rodapé das páginas folheáveis com a hora da impressão ("IMPRESSO ÀS 18:56").

5. Notícias da região: o Público não tem RSS por cidade, então as listas do site (publico.pt/api/list/local/
   <cidade>, em JSON) são convertidas em RSS aqui, na hora em que o Stop Press as pede. E feeds nacionais com
   "#regiao" no endereço ficam só com as notícias que citam as cidades da região.

4. Datas em português do Brasil (locale pt_BR; o workflow instala o locale no runner). Os demais textos são
   traduzidos por patches/localize.py.
"""
import importlib.abc
import importlib.machinery
import locale
import os
import re
import sys
import time
from pathlib import Path

import httpx

# --- 4. datas em português ------------------------------------------------------------------------
for _loc in ("pt_BR.UTF-8", "pt_BR.utf8", "pt_PT.UTF-8"):
    try:
        locale.setlocale(locale.LC_TIME, _loc)
        break
    except locale.Error:
        pass
else:
    print("sitecustomize: locale pt_BR indisponível; datas ficam em inglês", flush=True)

# --- 1. clima resiliente -------------------------------------------------------------------------

_orig_get = httpx.get
_DATA = Path(os.environ.get("PAPER_DATA_DIR", "."))
_LAST = _DATA / "open-meteo-last.json"
_MAX_AGE = 24 * 3600  # o bloqueio do Open-Meteo é diário


def _get(url, *args, **kw):
    is_weather = "open-meteo.com" in str(url)
    kw.setdefault("timeout", 15)
    if is_weather:
        kw["timeout"] = max(kw["timeout"], 25) if isinstance(kw["timeout"], (int, float)) else kw["timeout"]
    err = None
    for attempt in range(4):
        try:
            r = _orig_get(url, *args, **kw)
            if "publico.pt/api/list/" in str(url) and r.status_code == 200:
                return _publico_rss(url, r)
            if str(url).endswith("#regiao") and r.status_code == 200:
                return _so_regiao(url, r)
            if is_weather:
                if r.status_code == 200:
                    _LAST.write_bytes(r.content)
                elif _fresh():
                    # 429: o Open-Meteo limita pedidos por IP, e os IPs do GitHub são compartilhados.
                    print(f"Open-Meteo respondeu {r.status_code}; usando o último clima salvo", flush=True)
                    return _saved(url)
            return r
        except (httpx.TimeoutException, httpx.NetworkError) as e:
            err = e
            time.sleep(3 * (attempt + 1))
    if is_weather and _fresh():
        print(f"Open-Meteo indisponível ({err!r}); usando o último clima salvo", flush=True)
        return _saved(url)
    raise err


def _publico_rss(url, r):
    """Uma lista de notícias do site do Público (JSON) como feed RSS, para o Stop Press ler como os outros."""
    import html
    from datetime import datetime
    from email.utils import format_datetime

    def esc(v):
        return html.escape(str(v or ""), quote=True)

    items = []
    for a in r.json():
        link = a.get("fullUrl") or a.get("url")
        if not a.get("titulo") or not link:
            continue
        when = ""
        try:
            when = format_datetime(datetime.fromisoformat(a["data"]))
        except Exception:
            pass
        img = a.get("multimediaPrincipal")
        media = f'<media:content url="{esc(img)}" medium="image" width="1200"/>' if isinstance(img, str) and img.startswith("http") else ""
        items.append(f"<item><title>{esc(a['titulo'])}</title><link>{esc(link)}</link><guid>{esc(link)}</guid>"
                     f"<description>{esc(a.get('descricao') or a.get('lead'))}</description>"
                     f"<pubDate>{when}</pubDate>{media}</item>")
    rss = ('<?xml version="1.0" encoding="utf-8"?><rss version="2.0" xmlns:media="http://search.yahoo.com/mrss/">'
           f"<channel><title>Público</title><link>https://www.publico.pt</link>{''.join(items)}</channel></rss>")
    return httpx.Response(200, content=rss.encode("utf-8"), request=httpx.Request("GET", str(url)),
                          headers={"content-type": "application/rss+xml"})


# Cidades da região. Um feed com "#regiao" no fim do endereço (em stop-press.toml) fica só com as notícias que
# citam uma delas no título, no resumo ou nas categorias.
_REGIAO = re.compile(r"\b(porto|matosinhos|senhora da hora|le[çc]a|maia|gaia|gondomar|valongo|vila do conde|"
                     r"p[óo]voa de varzim|espinho|trofa|stcp|metro do porto)\b", re.I)


def _so_regiao(url, r):
    """Um feed nacional (RSS) reduzido às notícias da região. Desporto fica de fora (o "Porto" do futebol)."""
    import xml.etree.ElementTree as ET

    root = ET.fromstring(r.content)
    channel = root.find("channel")
    if channel is None:
        return r
    for item in channel.findall("item"):
        link = item.findtext("link", "") or ""
        text = " ".join([item.findtext("title", "") or "", (item.findtext("description", "") or "")[:400],
                         *[c.text or "" for c in item.findall("category")]])
        if "desporto" in link or not _REGIAO.search(text):
            channel.remove(item)
    return httpx.Response(200, content=ET.tostring(root, encoding="utf-8"), request=httpx.Request("GET", str(url)),
                          headers={"content-type": "application/rss+xml"})


def _fresh():
    return _LAST.exists() and time.time() - _LAST.stat().st_mtime < _MAX_AGE


def _saved(url):
    return httpx.Response(200, content=_LAST.read_bytes(), request=httpx.Request("GET", str(url)))


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


def _patch_offline(offline):
    """Rodapé da cópia que o Kindle folheia: a hora da impressão, e o que o Home faz no modo estático."""
    from paper.draw import H, W, INK, font

    def _footer(p, stamp):
        p.d.rectangle([0, H - 30, W, H], fill=255)
        p.rule(H - 28, w=1)
        p.text((W / 2, H - 20), f"IMPRESSO ÀS {stamp}  ·  CIMA/BAIXO: MATÉRIAS  ·  HOME: CAPA",
               font("sans", 11, 700), INK, anchor="ma")

    offline._footer = _footer


_PATCHES = {"paper.draw": _patch_draw, "paper.ui": _patch_ui, "paper.pages": _patch_pages,
            "paper.offline": _patch_offline}


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
