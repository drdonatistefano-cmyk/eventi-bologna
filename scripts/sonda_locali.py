#!/usr/bin/env python3
"""Sonda (14/11/2026): cosa espongono i siti dei locali di Bologna e Milano.

Per ogni sito di dati/locali_candidati.json prova, nel rispetto di robots.txt:
  - API The Events Calendar (/wp-json/tribe/events/v1/events)
  - calendario ICS (?ical=1)
  - dati schema.org Event (JSON-LD) nella prima pagina e nelle pagine «eventi/calendario/programma…»
  - elenco di pagine evento (link /event/, /evento/, /spettacolo/…) e se una pagina evento ha JSON-LD
Scrive sonda_locali.json (non tocca i dati della guida). Si lancia solo dal flusso sonda.yml.
"""
import datetime, html, json, re, sys, time, urllib.parse, urllib.request, urllib.robotparser
from concurrent.futures import ThreadPoolExecutor

UA = "Mozilla/5.0 (compatible; AchEventsGuide/1.0; +https://achevents.com)"
OGGI = datetime.date.today().isoformat()
PAROLE = r"event|eventi|calendar|calendario|programma|program|concerti|stagione|spettacoli|agenda|cartellone|live|shows?|in-scena|prossimi"
EVLINK = r"/(?:event|events|evento|eventi|spettacolo|spettacoli|concerto|concerti|show|shows|calendario|programma|stagione)/[a-z0-9][^\"'#?\s]{3,}"


def get(u, n=400_000):
    try:
        r = urllib.request.Request(u, headers={"User-Agent": UA, "Accept-Language": "it-IT,it;q=0.9"})
        with urllib.request.urlopen(r, timeout=15) as x:
            return x.geturl(), x.read(n).decode("utf-8", "replace"), x.status
    except Exception as e:
        return u, "", str(e)[:80]


def jsonld_eventi(h):
    out = []
    for b in re.findall(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', h, re.S):
        try: d = json.loads(html.unescape(b.strip()))
        except Exception: continue
        st = [d]
        while st:
            x = st.pop()
            if isinstance(x, list): st += x; continue
            if not isinstance(x, dict): continue
            t = x.get("@type"); t = " ".join(t) if isinstance(t, list) else str(t or "")
            if "Event" in t and x.get("startDate"): out.append((str(x.get("startDate"))[:16], str(x.get("name", ""))[:60]))
            for v in x.values():
                if isinstance(v, (dict, list)): st.append(v)
    return out


def sonda(citta, nome, dom):
    r = {"citta": citta, "nome": nome, "dominio": dom}
    base = "https://" + (dom if "." in dom.split("/")[0] else dom)
    fin, h, st = get(base + "/")
    if not h and not dom.startswith("www."):
        fin, h, st = get("https://www." + dom + "/")
    r["stato"] = st; r["finale"] = fin
    if not h: return r
    p = urllib.parse.urlparse(fin); base = f"{p.scheme}://{p.netloc}"
    rp = urllib.robotparser.RobotFileParser()
    _, rb, _ = get(base + "/robots.txt", 60_000); rp.parse(rb.splitlines())
    ok = lambda u: rp.can_fetch("*", u)
    r["robots_ok"] = ok(base + "/")
    if not r["robots_ok"]: return r
    # API tribe
    u = base + "/wp-json/tribe/events/v1/events?per_page=50&start_date=" + OGGI
    if ok(u):
        _, j, s = get(u, 2_000_000)
        try:
            d = json.loads(j); r["tribe"] = {"n": len(d.get("events", [])), "totale": d.get("total"), "esempio": [(e.get("start_date", "")[:16], html.unescape(e.get("title", ""))[:50]) for e in d.get("events", [])[:3]]}
        except Exception: pass
    # ICS
    for q in ("/?ical=1", "/events/?ical=1", "/eventi/?ical=1"):
        u = base + q
        if not ok(u): continue
        _, t, s = get(u, 2_000_000)
        if "BEGIN:VCALENDAR" in t:
            date = [d for d in re.findall(r"DTSTART[^:]*:(\d{8})", t) if f"{d[:4]}-{d[4:6]}-{d[6:]}" >= OGGI]
            r["ics"] = {"url": q, "future": len(date)}; break
    # pagine elenco
    cand = [base + "/"]
    for a in re.findall(r'href="([^"#]+)"', h):
        a = urllib.parse.urljoin(base + "/", html.unescape(a))
        if urllib.parse.urlparse(a).netloc != p.netloc: continue
        path = urllib.parse.urlparse(a).path.lower()
        if re.search(r"/(%s)[^/]*/?$" % PAROLE, path) and a not in cand and len(path) < 60: cand.append(a)
    pagine = []
    for u in cand[:8]:
        if not ok(u): continue
        time.sleep(1)
        f2, h2, s2 = (fin, h, st) if u == base + "/" else get(u)
        ev = [e for e in jsonld_eventi(h2) if e[0][:10] >= OGGI]
        links = sorted({urllib.parse.urljoin(u, l) for l in re.findall(r'href="([^"]*%s)"' % EVLINK.replace("/(?:", "(?:/"), h2, re.I)
                        if urllib.parse.urlparse(urllib.parse.urljoin(u, l)).netloc == p.netloc})
        links = [l for l in links if not re.search(r"/(?:category|tag|feed|page)/|\.(?:jpg|png|pdf)$", l)]
        pagine.append({"url": u, "jsonld_futuri": len(ev), "esempio": ev[:3], "link_evento": len(links), "link_esempio": links[:3]})
    r["pagine"] = pagine
    # una pagina evento: ha JSON-LD?
    best = max(pagine, key=lambda x: x["link_evento"], default=None)
    if best and best["link_evento"]:
        time.sleep(1)
        _, h3, _ = get(best["link_esempio"][0])
        r["pagina_evento"] = {"url": best["link_esempio"][0], "jsonld": jsonld_eventi(h3)[:2],
                              "data_testo": (re.search(r"\b\d{1,2}\s+(?:gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre|ottobre|novembre|dicembre)\s+20\d\d", h3, re.I) or [None])[0] if h3 else None}
    return r


def main():
    L = json.load(open("dati/locali_candidati.json"))
    lavori = [(c, n, d) for c in L for n, d in L[c]]
    with ThreadPoolExecutor(12) as ex:
        ris = list(ex.map(lambda a: sonda(*a), lavori))
    json.dump(ris, open("sonda_locali.json", "w"), ensure_ascii=False, indent=1)
    for x in ris:
        best = max((p["jsonld_futuri"] for p in x.get("pagine", [])), default=0)
        print(x["citta"], x["nome"][:28].ljust(28), x.get("stato"), "robots", x.get("robots_ok"), "tribe", (x.get("tribe") or {}).get("totale"),
              "ics", (x.get("ics") or {}).get("future"), "jsonld", best, "link", max((p["link_evento"] for p in x.get("pagine", [])), default=0))


if __name__ == "__main__":
    main()
