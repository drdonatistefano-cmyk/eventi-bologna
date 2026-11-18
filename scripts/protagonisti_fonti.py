"""Protagonisti dalle pagine degli eventi (regola del 17/11/2026, Stefano: «Bosso deve comparire sul box dell'evento»).

Per gli spettacoli senza campo «chi» apre UNA volta la pagina `fonte` (o `biglietti`) dell'evento, se il robots.txt lo permette,
e cerca i nomi: dati schema.org (performer, actor, director, organizer persona) e descrizione della pagina (og:description,
meta description, primi paragrafi), passata a protagonisti.chi(). Il risultato (anche vuoto) resta in dati/chi_pagine.json,
così ogni pagina si legge una volta sola. Non apre mai TicketOne/Eventim (robots.txt) né DICE (lista MAI).

uso: python3 scripts/protagonisti_fonti.py [bo mi ra fe] [--max 150]
"""
import json, os, re, sys, time, html, urllib.request, urllib.robotparser
from urllib.parse import urlsplit
QUI = os.path.dirname(os.path.abspath(__file__)); RADICE = os.path.dirname(QUI)
sys.path.insert(0, QUI)
import protagonisti as P

UA = "Mozilla/5.0 (compatible; AchEventsGuide/1.0; +https://achevents.com)"
FILE = {"bo": "eventi.js", "mi": "milano/eventi.js", "ra": "ravenna/eventi.js", "fe": "ferrara/eventi.js"}
CACHE = os.path.join(RADICE, "dati", "chi_pagine.json")
MAI = ("ticketone.", "eventim.", "dice.fm", "songkick.", "facebook.", "instagram.", "vivaticket.", "ticketmaster.", "fever")
GENERI = {"Teatro", "Classica", "Jazz"}   # dove il titolo spesso non dice chi va in scena
MAX = int(sys.argv[sys.argv.index("--max") + 1]) if "--max" in sys.argv else 150


def get(u, t=20):
    r = urllib.request.Request(u, headers={"User-Agent": UA, "Accept-Language": "it"})
    with urllib.request.urlopen(r, timeout=t) as f:
        return f.read(1_500_000).decode(f.headers.get_content_charset() or "utf-8", "replace")


ROB = {}
def permesso(u):
    p = urlsplit(u); b = f"{p.scheme}://{p.netloc}"
    if b not in ROB:
        rp = urllib.robotparser.RobotFileParser()
        try: rp.parse(get(b + "/robots.txt", 10).splitlines())
        except Exception: rp.parse([])
        ROB[b] = rp
    return ROB[b].can_fetch(UA, u)


def persone(j, out):
    """nomi di persone nei dati schema.org (performer, actor, director)"""
    if isinstance(j, list):
        for x in j: persone(x, out)
        return
    if not isinstance(j, dict): return
    for k in ("performer", "performers", "actor", "actors", "director", "composer"):
        v = j.get(k)
        for x in (v if isinstance(v, list) else [v] if v else []):
            n = x.get("name") if isinstance(x, dict) else x if isinstance(x, str) else ""
            if n and isinstance(n, str): out.append(("dirige " if k == "director" and "Music" in str(j.get("@type")) else "regia di " if k == "director" else "") + n.strip())
    for k in ("@graph", "subEvent", "workPerformed"):
        if k in j: persone(j[k], out)


def dalla_pagina(h, e):
    nomi = []
    for b in re.findall(r'<script[^>]*ld\+json[^>]*>(.*?)</script>', h, re.S | re.I):
        try: persone(json.loads(b.strip()), nomi)
        except Exception: pass
    tit = norm_t = P.norm(e.get("artista"))
    nomi = [n for n in nomi if P.buono(n.split(" di ")[-1].replace("dirige ", ""), e.get("artista", "")) and len(n) < 60]
    testi = re.findall(r'<meta[^>]+(?:property|name)="(?:og:description|description)"[^>]+content="([^"]{20,})"', h, re.I)
    corpo = re.sub(r"(?is)<(script|style|nav|header|footer)[^>]*>.*?</\1>", " ", h)
    testi += [re.sub(r"<[^>]+>", " ", p) for p in re.findall(r"(?is)<p[^>]*>(.*?)</p>", corpo)[:12]]
    testo = html.unescape(" ".join(testi))
    testo = re.sub(r"\s+", " ", testo)[:4000]
    c = P.chi({"artista": e.get("artista", ""), "descrizione": testo})
    # 18/11/2026: i nomi presi dal testo devono stare vicino al titolo dello spettacolo. Un articolo su tutta la stagione
    # (mentelocale, «Teatro Carcano, la stagione 2026-2027») aveva dato a Gioele Dix i protagonisti di un altro spettacolo.
    if c:
        t_ = P.norm(testo); k_ = P.norm(e.get("artista", ""))[:25]
        pos = [m.start() for m in re.finditer(re.escape(k_), t_)] if k_ else []
        def vicino(n):
            q = P.norm(n.split(" di ")[-1].replace("dirige ", "").split(" e ")[0])
            return any(abs(m.start() - x) < 400 for x in pos for m in re.finditer(re.escape(q), t_)) if q else False
        if not pos or not all(vicino(n) for n in re.split(r",\s*", c)): c = ""
    if nomi and not c:
        sem = [n for n in nomi if not n.startswith(("regia", "dirige"))][:2]
        alt = [n for n in nomi if n.startswith(("regia", "dirige"))][:1]
        c = ", ".join(([" e ".join(sem)] if sem else []) + alt)
    return c


def main():
    citta = [a for a in sys.argv[1:] if a in FILE] or list(FILE)
    cache = json.load(open(CACHE, encoding="utf-8")) if os.path.exists(CACHE) else {}
    letti, trovati = 0, 0
    for c in citta:
        p = os.path.join(RADICE, FILE[c]); s = open(p, encoding="utf-8").read()
        i, j = s.index("{"), s.rindex("}") + 1; d = json.loads(s[i:j]); cambiati = 0
        # una pagina che vale per più spettacoli (pagina iniziale, cartellone) non dice chi va in scena in ciascuno
        uso = {}
        for e in d["eventi"]:
            for x in {e.get("fonte"), e.get("biglietti")}:
                if x: uso[x] = uso.get(x, 0) + 1
        for e in d["eventi"]:
            if e.get("chi") or e.get("genere") not in GENERI: continue
            u = next((x for x in (e.get("fonte"), e.get("biglietti"), ) if (x or "").startswith("https://") and not any(m in x for m in MAI)
                      and uso.get(x, 0) == 1 and len(urlsplit(x).path.strip("/")) > 3
                      and not re.search(r"(?i)stagion|cartellon|calendari|programm|rassegna|season", urlsplit(x).path)), "")
            if not u: continue
            if u not in cache:
                if letti >= MAX: continue
                try:
                    if not permesso(u): cache[u] = ""; continue
                    letti += 1; time.sleep(1)
                    cache[u] = dalla_pagina(get(u), e)
                except Exception as x:
                    cache[u] = ""; print("  non letto", u[:80], x)
            v = P.pulisci(cache[u], e.get("artista", ""))
            if v:
                e["chi"] = v; cambiati += 1
        if cambiati:
            open(p, "w", encoding="utf-8").write(s[:i] + json.dumps(d, ensure_ascii=False, separators=(",", ":")) + s[j:])
        trovati += cambiati
        print(f"{c}: {cambiati} spettacoli con protagonisti dalle pagine")
    json.dump(cache, open(CACHE, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    print(f"pagine lette ora: {letti} · in memoria: {len(cache)} · con nomi: {sum(1 for v in cache.values() if v)}")


if __name__ == "__main__":
    main()
