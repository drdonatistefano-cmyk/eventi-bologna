#!/usr/bin/env python3
"""Ravenna: elenco eventi del sito turistico ufficiale del Comune (turismo.ra.it, robots.txt permette tutto).

leggi(get) -> lista di voci {url, categoria, titolo, inizio, fine, diverse, luogo}
descrizione(get, url, cache) -> frase dalla scheda (og:description), letta una volta e ricordata.
`get(url)` è la funzione di scaricamento dello script che chiama (restituisce il testo o None).
"""
import html as H, re

BASE = "https://www.turismo.ra.it/eventi/"
MESI = {m: i + 1 for i, m in enumerate("gennaio febbraio marzo aprile maggio giugno luglio agosto settembre ottobre novembre dicembre".split())}


def _data(g, m, a):
    return f"{int(a):04d}-{MESI[m]:02d}-{int(g):02d}"


def date(testo):
    t = testo.lower().replace("°", "").strip()
    m = re.match(r"(\d{1,2})\s+([a-z]+)\s+(\d{4})\s*-\s*(\d{1,2})\s+([a-z]+)\s+(\d{4})", t)
    if m and m.group(2) in MESI and m.group(5) in MESI:
        return _data(*m.group(1, 2, 3)), _data(*m.group(4, 5, 6))
    m = re.match(r"(\d{1,2})\s+([a-z]+)\s*-\s*(\d{1,2})\s+([a-z]+)\s+(\d{4})", t)
    if m and m.group(2) in MESI and m.group(4) in MESI:
        a = int(m.group(5)); a1 = a - 1 if MESI[m.group(2)] > MESI[m.group(4)] else a
        return _data(m.group(1), m.group(2), a1), _data(m.group(3), m.group(4), a)
    m = re.match(r"(\d{1,2})\s*-\s*(\d{1,2})\s+([a-z]+)\s+(\d{4})", t)
    if m and m.group(3) in MESI:
        return _data(m.group(1), m.group(3), m.group(4)), _data(m.group(2), m.group(3), m.group(4))
    m = re.match(r"(\d{1,2})\s+([a-z]+)\s+(\d{4})", t)
    if m and m.group(2) in MESI:
        d = _data(*m.group(1, 2, 3)); return d, d
    return None, None


def pagina(h):
    i = h.find("Risultati di ricerca")
    if i < 0: return []
    h = re.sub(r"(?is)<(script|style|svg).*?</\1>", " ", h[i:])
    h = re.sub(r'<a [^>]*href="(https://www\.turismo\.ra\.it/eventi/[a-z-]+/[a-z0-9-]+)/?"[^>]*>', r"\n[[\1]]", h)
    righe = [r.strip() for r in H.unescape(re.sub(r"<[^>]+>", "\n", h)).split("\n") if r.strip()]
    out, i = [], 0
    while i < len(righe):
        r = righe[i]
        m = re.match(r"\[\[(.+?)\]\]$", r)
        if m and i + 1 < len(righe) and not righe[i + 1].startswith("[["):
            u = m.group(1); cat = righe[i - 1] if i else ""
            j = i + 1; dtesto = righe[j]; diverse = False
            if j + 1 < len(righe) and righe[j + 1].startswith("(diverse"): diverse = True; j += 1
            if j + 1 < len(righe) and righe[j + 1].startswith("[[" + u + "]]"):
                tit = righe[j + 1][len(u) + 4:].strip() or (righe[j + 2] if j + 2 < len(righe) else "")
                k = j + 2 if righe[j + 1][len(u) + 4:].strip() else j + 3
                luogo = righe[k] if k < len(righe) and not righe[k].startswith("[[") else ""
                ini, fin = date(dtesto)
                if ini and tit:
                    out.append({"url": u, "categoria": cat, "titolo": tit, "inizio": ini, "fine": fin, "diverse": diverse,
                                "luogo": re.sub(r"\s+e altri luoghi$", "", luogo).strip(), "altri_luoghi": luogo.endswith("altri luoghi")})
                i = k; continue
        i += 1
    return out


def leggi(get, max_pagine=12):
    voci, visti = [], set()
    for n in range(1, max_pagine + 1):
        h = get(BASE if n == 1 else f"{BASE}page/{n}/")
        if not h: break
        nuove = [v for v in pagina(h) if v["url"] not in visti]
        if not nuove: break
        for v in nuove: visti.add(v["url"])
        voci += nuove
        if f"/eventi/page/{n + 1}/" not in h: break
    return voci


def descrizione(get, url, cache):
    if url in cache: return cache[url]
    h = get(url) or ""
    m = re.search(r'<meta property="og:description" content="([^"]*)"', h) or re.search(r'<meta name="description" content="([^"]*)"', h)
    d = re.sub(r"\s+", " ", H.unescape(m.group(1))).strip() if m else ""
    cache[url] = d
    return d
