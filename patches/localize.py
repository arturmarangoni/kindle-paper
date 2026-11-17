"""Adapta o código do Stop Press (baixado a cada impressão) a este jornal:

- textos da interface em português do Brasil (as datas vêm do locale pt_BR, ver sitecustomize.py);
- números no formato brasileiro (169.857 e 0,3%);
- vento em km/h;
- uma quinta seção, "italia", com página própria depois de Mundo;
- a capa alterna Mundo e Portugal em "Também hoje".

Cada troca é literal e tem de ser encontrada: se o Stop Press mudar e algum trecho sumir, a impressão falha
com o trecho em questão, em vez de sair um jornal meio traduzido. O workflow fixa a versão do Stop Press.

Uso: python localize.py <pasta server do Stop Press>
"""
import sys
from pathlib import Path

SEC_TITLE = "{S.sections.get(a['section'], {}).get('title', a['section']).upper()}"

EDITS = {
    "config.py": [
        # Aceita seções além das quatro de fábrica.
        ("        if k in out:\n            out[k].update(v)", "        out.setdefault(k, {}).update(v)"),
    ],
    "sources.py": [
        ('"wind_speed_unit": "mph"', '"wind_speed_unit": "kmh"'),
    ],
    "photos.py": [
        # Vinhetas de vídeo do g1 (a mesma imagem genérica "AGORA NO G1" em várias matérias): não são fotos.
        ("def load(url: str | None) -> Image.Image | None:\n    if not url:\n        return None",
         "def load(url: str | None) -> Image.Image | None:\n    if not url or 'video.glbimg.com' in url:\n        return None"),
    ],
    "offline.py": [
        ("MAX_ARTICLES = 24", "MAX_ARTICLES = 30"),  # cinco seções em vez de quatro
    ],
    "pages.py": [
        ('TITLES = {"front": "Front Page", "markets": "Markets", "world": "World", "stats": "Numbers", "day": "Your Day"}',
         'TITLES = {"front": "Capa", "markets": "Mercados", "world": "Mundo", "italia": "Itália", "stats": "Números", '
         '"day": "Seu dia"}'),
        ('ORDER = ["front", "world", "markets"]', 'ORDER = ["front", "world", "italia", "markets"]'),
        # tempo decorrido
        ('return f"{max(mins, 1)}m ago"', 'return f"há {max(mins, 1)} min"'),
        ('return f"{mins // 60}h ago"', 'return f"há {mins // 60} h"'),
        ('return f"{mins // 1440}d ago"', 'return f"há {mins // 1440} d"'),
        ('f"CHARGE ME · {pct}%"', 'f"CARREGUE · {pct}%"'),
        # rodapé com as seções
        ("""right = f"{n} in today's edition · {now().strftime('%H:%M')}" if n else f"Printed {now().strftime('%H:%M')}\"""",
         """right = f"{n} na edição de hoje · {now().strftime('%H:%M')}" if n else f"Impresso às {now().strftime('%H:%M')}\""""),
        # capa
        ("""f"No. {t.timetuple().tm_yday} · {t.strftime('%A').upper()} EDITION\"""",
         """f"Nº {t.timetuple().tm_yday} · EDIÇÃO DE {t.strftime('%A').upper()}\""""),
        ('f"{S.place.upper()} EDITION"', "S.place.upper()"),
        ('t.strftime("%A %d %B %Y").upper()', 't.strftime("%A, %d de %B").upper()'),
        ("""wx = f"{w['summary']} · {w['temp']}°C · H {w['days'][0]['hi']}° L {w['days'][0]['lo']}°\"""",
         """wx = f"{w['summary']} · {w['temp']}°C · {w['days'][0]['hi']}°/{w['days'][0]['lo']}°\""""),
        ('bits = [f"Leading the world pages: {top}." if top else ""]',
         'bits = [f"Destaque: {top}." if top else ""]'),
        ("""bits.append(f"The {lead_mk['name']} is {'up' if lead_mk['change_pct'] >= 0 else 'down'} "
                        f"{abs(lead_mk['change_pct']):.1f}% at {price(lead_mk)}.")""",
         """bits.append(f"O {lead_mk['name']} está em {'alta' if lead_mk['change_pct'] >= 0 else 'queda'} "
                        f"de {_pct(abs(lead_mk['change_pct']))}, a {price(lead_mk)}.")"""),
        ("""bits.append(f"In {S.place}, {w['summary'].lower()}, {w['temp']}°C.")""",
         """bits.append(f"Em {S.place}, {w['summary'].lower()}, {w['temp']}°C.")"""),
        ("""f"World · {lead['source']} · {ago(lead['when'])}\"""",
         """f"{_section_title(lead)} · {lead['source']} · {ago(lead['when'])}\""""),
        # A manchete sempre com foto: a primeira das seis primeiras notícias locais que tenha uma.
        ('top = (n.get("world") or [{}])[0].get("title")', 'top = (_pick_lead(_local_news()) or {}).get("title")'),
        ('    world = n.get("world") or []\n    if world:', '    world = _local_news()  # a capa: só Portugal, a região primeiro\n    if world:'),
        ("        lead = world[0]\n", "        lead = _pick_lead(world)\n        world = [lead] + [i for i in world if i is not lead]\n"),
        ('p.photo((W - M - 220, y + 4, W - M, y + 150), lead.get("image"))',
         'p.photo((W - M - 220, y + 4, W - M, y + 150), _lead_image(lead))'),
        ('"Also today"', '"Também hoje"'),
        ('for item in (world[1:] + (n.get("home") or []))[:6]:', 'for item in world[1:7]:'),
        ('my = p.kicker(gx, top, "Markets")', 'my = p.kicker(gx, top, "Mercados")'),
        ('dy = p.kicker(M, y, "Your day")', 'dy = p.kicker(M, y, "Seu dia")'),
        ('label = "Today" if d["date"] == t.date() else d["date"].strftime("%A")',
         'label = "Hoje" if d["date"] == t.date() else d["date"].strftime("%A").capitalize()'),
        ("""f"{d['summary']} · {d['hi']}°/{d['lo']}° · rain {d['rain']}%", font("sans", 12, 400), DARK)""",
         """p.fit(f"{d['hi']}°/{d['lo']}° · chuva {d['rain']}% · {d['summary'].lower()}", font("sans", 12, 400), half - 40),
                       font("sans", 12, 400), DARK)"""),
        ('"A clear week. Nothing in the diary."', '"Semana livre. Nada na agenda."'),
        ('"Nothing in the diary."', '"Nada na agenda."'),
        ('when = "All day" if', 'when = "Dia todo" if'),
        ('"At a glance"', '"Em resumo"'),
        # mercados
        ("""f"{exchange} {what} IN\"""",
         """f"{ {'LONDON': 'LONDRES'}.get(exchange, exchange)} {'FECHA' if what == 'CLOSES' else 'ABRE'} EM\""""),
        ('GROUPS = ("Indices", "AI & tech", "Shares", "Currencies, crypto & commodities")',
         'GROUPS = ("Índices", "IA e tecnologia", "Ações", "Câmbio, cripto e commodities")'),
        ('KIND_LABEL = {"index": "Index", "fx": "Currency", "crypto": "Crypto", "commodity": "Commodity", "stock": "Share",\n'
         '              "fund": "Fund"}',
         'KIND_LABEL = {"index": "Índice", "fx": "Câmbio", "crypto": "Cripto", "commodity": "Commodity", "stock": "Ação",\n'
         '              "fund": "Fundo"}'),
        ('US_SESSION = {"REGULAR": "New York open", "PRE": "US pre-market", "PREPRE": "US closed · overnight",\n'
         '              "POST": "US after hours", "POSTPOST": "US closed", "CLOSED": "US closed"}',
         'US_SESSION = {"REGULAR": "Nova York aberta", "PRE": "Pré-mercado nos EUA", "PREPRE": "EUA fechados · madrugada",\n'
         '              "POST": "Pós-mercado nos EUA", "POSTPOST": "EUA fechados", "CLOSED": "EUA fechados"}'),
        ('header(p, "Markets")', 'header(p, "Mercados")'),
        ('section_title(p, y, "Markets")', 'section_title(p, y, "Mercados")'),
        ("""f"{US_SESSION.get(us, 'Latest prices')} · page {ipage + 1} of {pages}\"""",
         """f"{US_SESSION.get(us, 'Últimos preços')} · pág. {ipage + 1} de {pages}\""""),
        ('"US FUTURES"', '"FUTUROS EUA"'),
        ('"no quotes just now"', '"sem cotações agora"'),
        ("""s = f"{'▲' if pct >= 0 else '▼'} {abs(pct):.2f}%\"""",
         """s = f"{'▲' if pct >= 0 else '▼'} {abs(pct):.2f}%".replace(".", ",")"""),
        ('p.text((M, y), "INSTRUMENT", hf, MID)', 'p.text((M, y), "ATIVO", hf, MID)'),
        ('p.text((312, y), "PRICE", hf, MID, anchor="ra")', 'p.text((312, y), "PREÇO", hf, MID, anchor="ra")'),
        ('p.text((388, y), "DAY", hf, MID, anchor="ra")', 'p.text((388, y), "DIA", hf, MID, anchor="ra")'),
        ('"PRE-MARKET" if "pre" in kinds else "AFTER HOURS" if "post" in kinds else "OUT OF HOURS"',
         '"PRÉ" if "pre" in kinds else "PÓS" if "post" in kinds else "PRÉ/PÓS"'),
        ('"30 DAYS"', '"30 DIAS"'),
        ('f"{g} · continued"', 'f"{g} · continuação"'),
        ("""sub += f" · {x['month_pct']:+.1f}% 1m\"""", """sub += f" · {x['month_pct']:+.1f}% 1m".replace(".", ",")"""),
        ('"Business headlines"', '"Manchetes de economia"'),
        ('s = f"{abs(pct):.1f}%"', 's = _pct(abs(pct))'),
        # Mundo, e a mesma página para a Itália
        ("def world() -> Page:", 'def world(key="world", sub="Geopolítica e notícias internacionais", extra="home") -> Page:'),
        ('y = header(p, "World")', "y = header(p, TITLES[key])"),
        ('items = n.get("world") or []', "items = n.get(key) or []"),
        ('y = section_title(p, y, "The World", "Geopolitics & foreign news")',
         'y = section_title(p, y, S.sections[key]["title"], sub)'),
        ('"The wires are quiet."', '"Nenhuma notícia por enquanto."'),
        ('footer(p, "world")', "footer(p, key)"),
        ('for item in items[1:] + (n.get("home") or [])[:4]:',
         "for item in items[1:] + ((n.get(extra) or [])[:4] if extra else []):"),
        # Seu dia
        ('y = header(p, "Your Day")', 'y = header(p, "Seu dia")'),
        ('    home = (sources.news() or {}).get("home") or []', '    home = _local_news()'),
        ('p.text((M, y), t.strftime("%A"), font("head", 40, 900))',
         'p.text((M, y), t.strftime("%A").capitalize(), font("head", 40, 900))'),
        ('t.strftime("%d %B %Y")', 't.strftime("%d de %B de %Y")'),
        ('f"Day {t.timetuple().tm_yday} · week {t.isocalendar().week}"',
         'f"Dia {t.timetuple().tm_yday} · semana {t.isocalendar().week}"'),
        ("""f"Sunrise {w['sunrise']}  ·  sunset {w['sunset']}  ·  {_hm(w['daylight_min'])} of daylight \"""",
         """f"Nascer do sol {w['sunrise']}  ·  pôr do sol {w['sunset']}  ·  {_hm(w['daylight_min'])} de sol \""""),
        ("""f"({'+' if diff >= 0 else '−'}{abs(diff)} min tomorrow)\"""",
         """f"({'+' if diff >= 0 else '−'}{abs(diff)} min amanhã)\""""),
        ('y = p.kicker(M, y, "The diary")', 'y = p.kicker(M, y, "Agenda")'),
        ('"No calendar connected. Put your calendar\'s private iCal address in stop-press.toml "',
         '"Nenhuma agenda conectada. Ponha o endereço iCal privado da sua agenda em stop-press.toml "'),
        ('"(calendar_ics_url) and your appointments appear here."', '"(calendar_ics_url) e seus compromissos aparecem aqui."'),
        ('label = "Today" if d == t.date() else ("Tomorrow" if (d - t.date()).days == 1 else e["start"].strftime("%A %d %b"))',
         'label = "Hoje" if d == t.date() else ("Amanhã" if (d - t.date()).days == 1 else e["start"].strftime("%A, %d %b"))'),
        ('f"Weather · {S.place}"', 'f"Clima · {S.place}"'),
        ("""f"feels {w['feels']}° · wind {w['wind']} mph\"""", """f"sensação {w['feels']}° · {w['wind']} km/h\""""),
        ('"NEXT 24 HOURS"', '"PRÓXIMAS 24 HORAS"'),
        ('p.text((cx0 - 6, y + 74), "rain",', 'p.text((cx0 - 6, y + 74), "chuva",'),
        ('"Today" if i == 0 else d["date"].strftime("%a")', '"Hoje" if i == 0 else d["date"].strftime("%a").capitalize()'),
        ("""f"rain {d['rain']}%\"""", """f"chuva {d['rain']}%\""""),
        ('return f"{mins // 60}h {mins % 60:02d}m"', 'return f"{mins // 60}h{mins % 60:02d}"'),
        ('PAGES = {"front": front, "markets": markets, "world": world, "stats": stats, "day": day}',
         'def italia() -> Page:\n'
         '    return world("italia", "Notícias da Itália, em italiano", None)\n\n\n'
         'PAGES = {"front": front, "markets": markets, "world": world, "italia": italia, "stats": stats, "day": day}'),
    ],
    "ui.py": [
        ('"Today\'s Articles"', '"Matérias de hoje"'),
        ('NAV_LABEL = {"front": "FRONT", "world": "WORLD", "markets": "MARKETS", "stats": "NUMBERS", "day": "DAY", "index": "ALL"}',
         'NAV_LABEL = {"front": "CAPA", "world": "MUNDO", "italia": "ITÁLIA", "markets": "MERCADOS", "stats": "NÚMEROS", '
         '"day": "DIA", "index": "TUDO"}'),
        ('[("BACK", "back", False), ("FRONT PAGE", "home", False), ("ALL ARTICLES", "goto:index", False)]',
         '[("VOLTAR", "back", False), ("CAPA", "home", False), ("TODAS AS MATÉRIAS", "goto:index", False)]'),
        ('[("MARKETS", "back", False), ("CHART RANGE", "range", False), ("FRONT PAGE", "home", False)]',
         '[("MERCADOS", "back", False), ("PERÍODO", "range", False), ("CAPA", "home", False)]'),
        ('f"{len(arts)} filed · {unread} unread · page {ipage + 1} of {pages}"',
         'f"{len(arts)} publicadas · {unread} não lidas · pág. {ipage + 1} de {pages}"'),
        ('f"CONTINUE READING · PAGE {at + 1} OF {n}"', 'f"CONTINUAR LENDO · PÁG. {at + 1} DE {n}"'),
        ('"Nothing filed yet today."', '"Nada publicado hoje ainda."'),
        ("{a['section'].upper()}", SEC_TITLE),
        ('(" · READ" if read else "")', '(" · LIDA" if read else "")'),
        ('header(p, "Article")', 'header(p, "Matéria")'),
        ('"That article has gone from the archive."', '"Esta matéria já saiu do arquivo."'),
        ("""header(p, f"{a['source']} · {apage + 1} of {len(pages)}")""",
         """header(p, f"{a['source']} · {apage + 1} de {len(pages)}")"""),
        ('"· END ·"', '"· FIM ·"'),
        ('"The full text of this one couldn\'t be fetched."', '"Não foi possível baixar o texto completo desta matéria."'),
        ('"PAGE KEYS NEXT/PREVIOUS  ·  LEFT/RIGHT CHART RANGE  ·  BACK TO MARKETS"',
         '"BOTÕES: PRÓXIMA/ANTERIOR  ·  ESQ/DIR: PERÍODO  ·  BACK: MERCADOS"'),
        ('"BACK RETURNS  ·  HOME FRONT"', '"BACK VOLTA  ·  HOME: CAPA"'),
        ('"PAGE KEYS TURN  ·  LEFT/RIGHT TEXT SIZE  ·  BACK RETURNS  ·  HOME FRONT"',
         '"BOTÕES VIRAM  ·  ESQ/DIR: LETRA  ·  BACK VOLTA  ·  HOME: CAPA"'),
        ('"PAGE KEYS FLIP  ·  5-WAY CHOOSE  ·  PRESS READS  ·  MENU ALL ARTICLES"',
         '"BOTÕES VIRAM  ·  DIRECIONAL ESCOLHE  ·  CENTRO ABRE  ·  MENU: TODAS"'),
    ],
}

APPEND = {
    "pages.py": '''

# --- português do Brasil (patches/localize.py) ------------------------------------------------------

def _mix(a, b):
    """As duas listas intercaladas: a[0], b[0], a[1], b[1]..."""
    out = []
    for i in range(max(len(a), len(b))):
        out += a[i:i + 1] + b[i:i + 1]
    return out


def _local_news():
    """A capa e o Seu dia: as notícias da região (dos últimos 3 dias) primeiro, depois as de Portugal."""
    n = sources.news() or {}
    agora = datetime.now(timezone.utc)
    regiao = [i for i in n.get("regiao") or [] if i.get("when") and (agora - i["when"]).total_seconds() < 72 * 3600]
    out, seen = [], set()
    for item in regiao + (n.get("home") or []):
        if item["link"] not in seen:
            seen.add(item["link"])
            out.append(item)
    return out


def _section_title(item):
    links = {i["link"] for i in (sources.news() or {}).get("regiao") or []}
    return S.sections["regiao" if item["link"] in links else "home"]["title"]


def _lead_image(item):
    """A foto da notícia: a do feed, ou a primeira da própria matéria (já baixada pelo arquivo)."""
    from paper import archive, photos
    from paper.edition import _paragraphs

    if photos.available(item.get("image")):
        return item.get("image")
    a = archive.get(item.get("link"))
    for para in _paragraphs((a or {}).get("text") or ""):
        if para.startswith(archive.IMG):
            url = para[len(archive.IMG):-2]
            if photos.available(url):
                return url
    return None


def _pick_lead(items):
    """A manchete da capa: a primeira das seis primeiras notícias que tenha foto (senão, a primeira)."""
    for item in items[:6]:
        if _lead_image(item):
            return item
    return items[0] if items else None


def _pct(v):
    return f"{v:.1f}%".replace(".", ",")


_BR = str.maketrans({",": ".", ".": ","})
_money_en, _price_en, _num_en = money, price, num


def money(v, cur, kind="stock"):
    return _money_en(v, cur, kind).translate(_BR)


def price(x):
    if x["kind"] in ("stock", "fund") or (x["kind"] == "crypto" and x["symbol"] != "BTC-USD"):
        return money(x["price"], x.get("currency", ""))
    return _price_en(x).translate(_BR)


def num(v, suffix=""):
    return _num_en(v, suffix).translate(_BR)
''',
    "sources.py": '''

# --- português do Brasil (patches/localize.py) ------------------------------------------------------
WMO.update({
    0: "Céu limpo", 1: "Pouco nublado", 2: "Parcialmente nublado", 3: "Nublado", 45: "Nevoeiro", 48: "Nevoeiro gelado",
    51: "Garoa fraca", 53: "Garoa", 55: "Garoa forte", 56: "Garoa congelante", 57: "Garoa congelante",
    61: "Chuva fraca", 63: "Chuva", 65: "Chuva forte", 66: "Chuva congelante", 67: "Chuva congelante",
    71: "Neve fraca", 73: "Neve", 75: "Neve forte", 77: "Grãos de neve", 80: "Pancadas de chuva", 81: "Pancadas de chuva",
    82: "Pancadas fortes", 85: "Pancadas de neve", 86: "Pancadas de neve", 95: "Trovoadas", 96: "Trovoada e granizo",
    99: "Trovoada e granizo",
})
''',
}


def main(server: Path):
    src = server / "paper"
    for name, edits in EDITS.items():
        path = src / name
        text = path.read_text(encoding="utf-8")
        for old, new in edits:
            if old not in text:
                sys.exit(f"localize.py: trecho não encontrado em {name}:\n{old}")
            text = text.replace(old, new)
        text += APPEND.get(name, "")
        path.write_text(text, encoding="utf-8")
    for name in APPEND:
        if name not in EDITS:
            path = src / name
            path.write_text(path.read_text(encoding="utf-8") + APPEND[name], encoding="utf-8")
    print(f"localize.py: {sum(len(e) for e in EDITS.values())} trechos traduzidos")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
