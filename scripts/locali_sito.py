#!/usr/bin/env python3
"""Programmi completi dei locali, letti dal loro sito (dal 14/11/2026, richiesta di Stefano:
«i programmi devono essere completi o perdiamo di credibilità»).

Configurazione: dati/locali_sito.json → {"bo": [ {...}, ... ], "mi": [...]}, ogni voce:
  nome     nome del luogo come scritto nella guida
  comune   comune ufficiale
  metodo   tribe | ics | jsonld | elenco
  url      tribe/ics: indirizzo del sito; jsonld/elenco: pagina del calendario (anche più pagine: lista)
  genere   genere di base (Rock, Jazz, Classica, Pop e altra musica, Teatro, Serate e club) — opzionale
  tipo     tipo di base (es. Prosa) — opzionale
  max      quante pagine evento aprire al massimo (elenco, predefinito 60)
Metodi:
  tribe   API The Events Calendar (WordPress): /wp-json/tribe/events/v1/events
  ics     calendario ICS (?ical=1)
  jsonld  pagine del calendario con dati schema.org Event
  elenco  pagina del calendario → link delle pagine evento → data/ora/titolo/biglietti da ogni pagina
           (JSON-LD, microdata, <time datetime>, altrimenti la prima data scritta in italiano dopo il titolo)
Rispetta robots.txt, una pagina ogni 1,5 secondi per sito.

Prova senza toccare i dati:  python3 scripts/locali_sito.py --prova bo|mi [nome]
"""
import datetime, html, json, os, re, sys, time, urllib.parse, urllib.request, urllib.robotparser

UA = "Mozilla/5.0 (compatible; AchEventsGuide/1.0; +https://achevents.com)"
OGGI = datetime.date.today().isoformat()
LIMITE = (datetime.date.today() + datetime.timedelta(days=366)).isoformat()
MESI = {m: i for i, m in enumerate("gennaio febbraio marzo aprile maggio giugno luglio agosto settembre ottobre novembre dicembre".split(), 1)}
MESI.update({m[:3]: i for m, i in list(MESI.items())})
MESI.update({"sett": 9})
MRX = "|".join(sorted(MESI, key=len, reverse=True))
BIGL = r"ticketone\.it|vivaticket\.|dice\.fm|link\.dice\.fm|ticketsms\.it|mailticket\.it|liveticket\.it|boxerticket\.it|musicglue\.com|eventbrite\.|18tickets\.it|webtic\.it|ticketmaster\.it|go2\.it|bigliettoveloce\.it|crowdticket|ticketgate|clappit|showtime\.|happyticket|diyticket\.it|xceed\.me|ticketlandia|feverup\.com|ticketing|biglietteria|shop\.|/tickets?/|/biglietti/"
EVLINK = r"/(?:event|events|evento|eventi|spettacolo|spettacoli|concerto|concerti|show|shows|calendario|programma|stagione|produzioni|opere|appuntamenti|in-scena|evento-dettaglio)/[a-z0-9%][^\"'#?\s]{2,}"
_ult, _rp = {}, {}


def get(u, n=1_500_000):
    host = urllib.parse.urlparse(u).netloc
    att = 1.5 - (time.time() - _ult.get(host, 0))
    if att > 0: time.sleep(att)
    _ult[host] = time.time()
    try:
        r = urllib.request.Request(u, headers={"User-Agent": UA, "Accept-Language": "it-IT,it;q=0.9"})
        with urllib.request.urlopen(r, timeout=20) as x:
            return x.geturl(), x.read(n).decode("utf-8", "replace")
    except Exception:
        return u, ""


def permesso(u):
    p = urllib.parse.urlparse(u); base = f"{p.scheme}://{p.netloc}"
    if base not in _rp:
        rp = urllib.robotparser.RobotFileParser()
        _, t = get(base + "/robots.txt", 100_000); rp.parse(t.splitlines()); _rp[base] = rp
    return _rp[base].can_fetch("*", u)


def testo(h):
    h = re.sub(r"(?s)<script.*?</script>|<style.*?</style>|<noscript.*?</noscript>", " ", h)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", h))).strip()


def pulisci_titolo(t, sito=""):
    t = html.unescape(re.sub(r"<[^>]+>", " ", t or "")); t = re.sub(r"\s+", " ", t).strip()
    parti = re.split(r"\s+[|–—-]\s+", t)
    if len(parti) > 1:
        dom = re.sub(r"^www\.|\.[a-z]+$", "", sito).replace("-", " ").lower()
        parti = [p for p in parti if not (dom and (dom.split(".")[0][:6] in p.lower().replace(" ", "")))] or parti[:1]
        t = parti[0]
    esaurito = bool(re.match(r"(?i)\s*sold\s*-?\s*out\s*[/:|-]*\s*", t))
    t = re.sub(r"(?i)^\s*(sold\s*-?\s*out|annullato|rinviato|nuova data)\s*[/:|–-]+\s*", "", t).strip()
    sig = {"DJ", "MC", "CCCP", "AC/DC", "USA", "UK", "EP", "LP", "BJF", "TCBO", "ERT", "OCM"}
    parole = t.split()
    if sum(1 for w in parole if w.isupper() and len(w) > 2) >= max(1, len(parole) // 2):
        corte = {"IL", "LA", "LO", "LE", "DI", "DA", "IN", "CON", "PER", "AL", "DEL", "DELLA", "E", "A", "O", "UN", "UNA", "GLI", "I", "DE", "AI", "NEL", "SU", "TRA", "FRA"}
        t = " ".join((w.lower() if (w in corte and i > 0) else w.capitalize()) if w.isupper() and w not in sig and (len(re.sub(r"\W", "", w)) > 2 or w in corte) else w
                     for i, w in enumerate(parole))
    return t.strip(" -–|"), esaurito


def jsonld(h):
    out = []
    for b in re.findall(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', h, re.S):
        try: d = json.loads(b.strip())
        except Exception:
            try: d = json.loads(html.unescape(b.strip()))
            except Exception: continue
        st = [d]
        while st:
            x = st.pop()
            if isinstance(x, list): st += x; continue
            if not isinstance(x, dict): continue
            t = x.get("@type"); t = " ".join(t) if isinstance(t, list) else str(t or "")
            if re.search(r"Event", t) and x.get("startDate"):
                off = x.get("offers") or {}
                off = off[0] if isinstance(off, list) and off else off
                out.append({"titolo": str(x.get("name") or ""), "inizio": str(x.get("startDate")), "fine": str(x.get("endDate") or ""),
                            "url": str(x.get("url") or ""), "biglietti": str((off or {}).get("url") or "") if isinstance(off, dict) else "",
                            "stato": str(x.get("eventStatus") or "") + " " + str((off or {}).get("availability") or "" if isinstance(off, dict) else ""),
                            "descrizione": str(x.get("description") or "")})
            for v in x.values():
                if isinstance(v, (dict, list)): st.append(v)
    return out


def data_iso(s):
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2}))?", s or "")
    if not m: return "", ""
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}", (f"{m.group(4)}:{m.group(5)}" if m.group(4) and m.group(4) + m.group(5) != "0000" else "")


def date_testo(t):
    """Prima data (o intervallo) scritta in italiano nel testo: ritorna (inizio, fine, ora)."""
    anno_oggi = int(OGGI[:4])
    def mese(x): return MESI.get(x.lower().rstrip("."))
    m = re.search(r"(?i)\bdal?\s+(\d{1,2})(?:\s+(%s)\.?)?(?:\s+(20\d\d))?\s+al?\s+(\d{1,2})\s+(%s)\.?\s+(20\d\d)" % (MRX, MRX), t)
    if m and mese(m.group(5)):
        y2, m2 = int(m.group(6)), mese(m.group(5)); m1 = mese(m.group(2)) if m.group(2) else m2
        y1 = int(m.group(3)) if m.group(3) else (y2 - 1 if m1 > m2 else y2)
        ini, fin = f"{y1:04d}-{m1:02d}-{int(m.group(1)):02d}", f"{y2:04d}-{m2:02d}-{int(m.group(4)):02d}"
        resto = t[m.end():m.end() + 160]
    else:
        m = re.search(r"(?i)\b(\d{1,2})\s+(%s)\.?\s*,?\s*(20\d\d)?\b" % MRX, t) or re.search(r"\b(\d{1,2})[/.](\d{1,2})[/.](20\d\d)\b", t)
        if not m: return "", "", ""
        if m.group(2).isdigit(): g, mm, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        else:
            g, mm = int(m.group(1)), mese(m.group(2)); y = int(m.group(3)) if m.group(3) else anno_oggi
            if not m.group(3) and f"{y:04d}-{mm:02d}-{g:02d}" < OGGI:
                try: passati = (datetime.date.fromisoformat(OGGI) - datetime.date(y, mm, g)).days
                except ValueError: return "", "", ""
                if passati > 120: y += 1      # gennaio scritto a novembre = anno dopo; un giorno appena passato resta passato
        if not (1 <= mm <= 12 and 1 <= g <= 31): return "", "", ""
        ini = fin = f"{y:04d}-{mm:02d}-{g:02d}"
        resto = t[m.end():m.end() + 160]
    o = re.search(r"(?i)(?:\bore|\bh\.?|\balle|inizio(?: ore)?|apertura porte[^0-9]{0,15}?inizio)\s*(\d{1,2})[:.,](\d{2})", resto) or \
        re.search(r"\b(\d{1,2})[:.](\d{2})\b", resto[:60]) or re.search(r"(?i)\bore\s*(\d{1,2})()(?![\d:.,])", resto)
    ora = f"{int(o.group(1)):02d}:{o.group(2) or '00'}" if o and int(o.group(1)) < 24 else ""
    return ini, fin, ora


def link_biglietti(h, sito):
    for u in re.findall(r'href="(https?://[^"]+)"', h):
        u = html.unescape(u)
        if urllib.parse.urlparse(u).netloc.endswith(sito.replace("www.", "")) and not re.search(r"/(?:biglietti|tickets?|shop)/", u): continue
        if re.search(r"awin1\.com|facebook|instagram|twitter|whatsapp|mailto|tesser|preadesione|newsletter", u): continue
        if re.search(r"search\?|/b2b\.htm|^https?://(www\.)?(dice\.fm|happyticket\.it|vivaticket\.com|ticketone\.it|webtic\.it)/?(#.*)?$|/biglietti/?$", u, re.I): continue
        if re.search(BIGL, u, re.I):
            return re.sub(r"[?&](fbclid|utm_[a-z]+|gclid)=[^&]*", "", u).rstrip("?&")
    return ""


# ---------- metodi ----------
def m_tribe(c):
    base = c["url"].rstrip("/"); out = []; pag = 1
    while pag <= 10:
        u = f"{base}/wp-json/tribe/events/v1/events?per_page=50&page={pag}&start_date={OGGI}&end_date={LIMITE}"
        if not permesso(u): break
        _, j = get(u)
        try: d = json.loads(j)
        except Exception: break
        for e in d.get("events", []):
            ini, ora = data_iso(e.get("start_date", "")); fin, _ = data_iso(e.get("end_date", ""))
            if e.get("all_day"): ora = ""
            out.append({"titolo": e.get("title", ""), "data": ini, "fino": fin or ini, "ora": ora, "fonte": e.get("url", ""),
                        "biglietti": e.get("website") if re.search(BIGL, e.get("website") or "", re.I) else "",
                        "descrizione": testo(e.get("excerpt") or e.get("description") or "")[:300],
                        "categorie": " ".join(x.get("name", "") for x in e.get("categories", [])),
                        "sede": html.unescape(((e.get("venue") or {}) if isinstance(e.get("venue"), dict) else {}).get("venue", "") or "")})
        if pag >= int(d.get("total_pages") or 1): break
        pag += 1
    return out


def m_ics(c):
    base = c["url"].rstrip("/"); out = []
    u = base if "ical" in base or base.endswith(".ics") else base + "/?ical=1"
    if not permesso(u): return out
    _, t = get(u, 5_000_000)
    t = re.sub(r"\r?\n[ \t]", "", t)
    for b in re.findall(r"BEGIN:VEVENT(.*?)END:VEVENT", t, re.S):
        f = lambda k: (re.search(r"^%s[^:\n]*:(.*)$" % k, b, re.M) or [None, ""])[1].strip()
        ds, de = f("DTSTART"), f("DTEND")
        if not re.match(r"\d{8}", ds): continue
        ini = f"{ds[:4]}-{ds[4:6]}-{ds[6:8]}"; ora = f"{ds[9:11]}:{ds[11:13]}" if len(ds) >= 13 else ""
        fin = f"{de[:4]}-{de[4:6]}-{de[6:8]}" if re.match(r"\d{8}", de) else ini
        if not ora and fin > ini: fin = (datetime.date.fromisoformat(fin) - datetime.timedelta(days=1)).isoformat()
        un = lambda s: s.replace("\\,", ",").replace("\\;", ";").replace("\\n", " ").strip()
        out.append({"titolo": un(f("SUMMARY")), "data": ini, "fino": max(fin, ini), "ora": ora, "fonte": f("URL"), "biglietti": "",
                    "descrizione": un(f("DESCRIPTION"))[:300], "categorie": un(f("CATEGORIES"))})
    return out


def scopri(base, rx):
    """Pagina del calendario: tra prima pagina e link «eventi/calendario/programma…» quella con più link a pagine evento."""
    f, h = get(base)
    if not h: return base
    p = urllib.parse.urlparse(f)
    cand = [f]
    for a in re.findall(r'href="([^"#]+)"', h):
        a = urllib.parse.urljoin(f, html.unescape(a)); pa = urllib.parse.urlparse(a)
        if pa.netloc == p.netloc and re.search(r"/(event|eventi|calendar|calendario|programma|program|concerti|stagione|spettacoli|agenda|cartellone|live|shows?|in-scena|prossimi|eventi-in-programma)[^/]*/?$", pa.path.lower()) and a not in cand and len(pa.path) < 70:
            cand.append(a)
    best, bn = f, -1
    for u in cand[:8]:
        if not permesso(u): continue
        _, hh = (f, h) if u == f else get(u)
        n = len({x for x in re.findall(r'href="([^"]+)"', hh) if rx.search(urllib.parse.urlparse(urllib.parse.urljoin(u, x)).path)})
        if n > bn: best, bn = u, n
    return best


def pagine_calendario(c):
    urls = c["url"] if isinstance(c["url"], list) else [c["url"]]
    if c.get("scopri"):
        urls = [scopri(urls[0], re.compile(c.get("link") or EVLINK, re.I))]; c["url_trovato"] = urls[0]
    viste = []
    for u in urls:
        for p in range(1, 1 + int(c.get("pagine", 1))):
            uu = u if p == 1 else (u.rstrip("/") + f"/page/{p}/" if "{p}" not in u else u.replace("{p}", str(p)))
            if "{p}" in u and p == 1: uu = u.replace("{p}", "1")
            if not permesso(uu): continue
            f, h = get(uu)
            if not h: break
            viste.append((f, h))
    return viste


def m_jsonld(c):
    out = []
    for f, h in pagine_calendario(c):
        for e in jsonld(h):
            ini, ora = data_iso(e["inizio"]); fin, _ = data_iso(e["fine"])
            out.append({"titolo": e["titolo"], "data": ini, "fino": fin or ini, "ora": ora, "fonte": e["url"] or f,
                        "biglietti": e["biglietti"] if re.search(BIGL, e["biglietti"], re.I) else "", "descrizione": testo(e["descrizione"])[:300],
                        "stato": e["stato"]})
    return out


def m_elenco(c):
    sito = urllib.parse.urlparse(c["url"] if isinstance(c["url"], str) else c["url"][0]).netloc
    rx = re.compile(c.get("link") or EVLINK, re.I)
    links = []
    for f, h in pagine_calendario(c):
        for a in re.findall(r'href="([^"]+)"', h):
            a = urllib.parse.urljoin(f, html.unescape(a)).split("#")[0]
            pa = urllib.parse.urlparse(a)
            if pa.netloc != urllib.parse.urlparse(f).netloc or not rx.search(pa.path + ("?" + pa.query if pa.query else "")): continue
            if re.search(r"/(?:category|categoria|tag|feed|page|author)/|\.(?:jpe?g|png|pdf|webp)$", a, re.I): continue
            if a.rstrip("/") in (f.rstrip("/"),) or a in links: continue
            links.append(a)
    out = []
    for u in links[:int(c.get("max", 60))]:
        if not permesso(u): continue
        f, h = get(u)
        if not h: continue
        jl = [e for e in jsonld(h) if data_iso(e["inizio"])[0]]
        tit = ""
        if c.get("titolo_url"):   # sito senza titolo leggibile (es. Estragon): il titolo è nell'indirizzo della pagina
            slug = [x for x in urllib.parse.urlparse(f).path.split("/") if x][-1]
            slug = re.sub(r"[-_]+\d{3,}$|^\d{3,}[-_]+|\.\w+$", "", urllib.parse.unquote(slug))
            tit = " ".join(w.capitalize() if not w.isupper() else w for w in re.split(r"[-_]+", slug) if w)
        for rx_t in (() if tit else (r'<meta property="og:title" content="([^"]*)"', r"<h1[^>]*>(.*?)</h1>", r"<h2[^>]*>(.*?)</h2>", r"<title>(.*?)</title>")):
            mt = re.search(rx_t, h, re.S)
            if not mt: continue
            cand, _ = pulisci_titolo(mt.group(1), sito)
            nucleo = re.sub(r"^www\.|\..*$", "", sito)[:7].lower()
            if cand and not GENERICI.match(cand) and not (nucleo and nucleo in cand.lower().replace(" ", "") and len(cand.split()) <= 4) and re.search(r"[A-Za-zÀ-ÿ]{2}", cand):
                tit = cand; break
        if jl:
            e = jl[0]; ini, ora = data_iso(e["inizio"]); fin, _ = data_iso(e["fine"])
            out.append({"titolo": e["titolo"] or tit, "data": ini, "fino": fin or ini, "ora": ora, "fonte": f,
                        "biglietti": e["biglietti"] if re.search(BIGL, e["biglietti"], re.I) else link_biglietti(h, sito), "descrizione": testo(e["descrizione"])[:300], "stato": e["stato"]})
            continue
        md = re.search(r'itemprop="startDate"[^>]*content="([^"]+)"', h) or re.search(r'<time[^>]+datetime="(20\d\d-\d\d-\d\d[^"]*)"', h)
        corpo = h
        i1 = h.find("<h1")
        if i1 > 0: corpo = h[i1:]
        t = testo(corpo)
        if md:
            ini, ora = data_iso(md.group(1)); fin = ini
            if not ora: ora = date_testo(t)[2]
        else:
            ini, fin, ora = date_testo(t[:3000])
        if not ini: continue
        dett = ""
        for p in re.findall(r"<p[^>]*>(.*?)</p>", corpo, re.S):
            p = testo(p)
            if len(p) > 60 and not re.search(r"cookie|privacy|newsletter|©", p, re.I): dett = p; break
        out.append({"titolo": tit, "data": ini, "fino": fin or ini, "ora": ora, "fonte": f, "biglietti": link_biglietti(h, sito), "descrizione": dett[:300]})
    return out


GENERICI = re.compile(r"(?i)^\s*(\d{1,2}[/.]\d{1,2}[/.]\d{2,4}|\d{1,2}\s+\w+\s+20\d\d|spettacoli|eventi|evento|programma|calendario|stagione.*|home|homepage|prosa|family|extra|altri eventi|note d'autore|ridere alla grande|teatro \w+|biglietti|news|concerti|art ?bonus|sostienici|dona(zioni)?|abbonamenti|abbonati|newsletter|contatti|chi siamo)\s*$")


METODI = {"tribe": m_tribe, "ics": m_ics, "jsonld": m_jsonld, "elenco": m_elenco}


def leggi(c):
    """Eventi futuri (entro 12 mesi) di un locale, con titoli puliti; deduplicati per data+titolo."""
    sito = urllib.parse.urlparse(c["url"] if isinstance(c["url"], str) else c["url"][0]).netloc
    try: grezzi = METODI[c["metodo"]](c)
    except Exception as ex:
        return [], f"errore: {ex}"[:120]
    visti, out = set(), []
    for e in grezzi:
        if not e.get("data") or e["data"] > LIMITE or (e.get("fino") or e["data"]) < OGGI: continue
        if c.get("escludi") and re.search(c["escludi"], e["titolo"] + " " + e.get("categorie", ""), re.I): continue
        if c.get("solo") and not re.search(c["solo"], e["titolo"] + " " + e.get("categorie", ""), re.I): continue
        if c.get("sede") and e.get("sede") and not re.search(c["sede"], e["sede"], re.I): continue      # evento del locale ma in un'altra sede
        if c.get("sede") and re.search(r"(?i)\b(al|a|presso)\s+(planetario|villa|casa|museo|palazzo|chiesa|basilica)\b", e["titolo"]): continue
        tit, esaurito = pulisci_titolo(e["titolo"], sito)
        if not tit or len(tit) < 2: continue
        st = (e.get("stato") or "").lower()
        if "cancel" in st or re.search(r"(?i)\bannullat", e["titolo"]): continue
        if "soldout" in st.replace(" ", "") or "sold out" in st: esaurito = True
        k = (e["data"], tit.lower())
        if k in visti: continue
        visti.add(k)
        d = re.sub(r"\s+", " ", e.get("descrizione") or "").strip()
        frase = re.split(r"(?<=[.!?])\s", d)[0] if d else ""
        frase = " ".join(frase.split()[:25]).rstrip(",;:") if 25 <= len(frase) else ""
        out.append({"titolo": tit, "data": e["data"], "fino": max(e.get("fino") or e["data"], e["data"]), "ora": e.get("ora") or "",
                    "fonte": e.get("fonte") or "", "biglietti": e.get("biglietti") or "", "esaurito": esaurito,
                    "descrizione": frase, "categorie": e.get("categorie", "")})
    out.sort(key=lambda e: (e["titolo"].lower(), e["data"]))
    unite = []
    for e in out:
        u = unite[-1] if unite else None
        if u and u["titolo"].lower() == e["titolo"].lower() and e["data"] <= (datetime.date.fromisoformat(u["fino"]) + datetime.timedelta(days=3)).isoformat():
            u["fino"] = max(u["fino"], e["fino"]); u["repliche"] = u.get("repliche", 1) + 1
            if not u["biglietti"]: u["biglietti"] = e["biglietti"]
            continue
        unite.append(dict(e))
    unite = [e for e in unite if not GENERICI.match(e["titolo"])]
    unite.sort(key=lambda e: (e["data"], e["ora"]))
    return unite, "ok"


def config(citta):
    p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dati", "locali_sito.json")
    return json.load(open(p)).get(citta, []) if os.path.exists(p) else []


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "--prova":
        citta = sys.argv[2]; solo = sys.argv[3].lower() if len(sys.argv) > 3 else ""
        rad = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        f = os.path.join(rad, "eventi.js" if citta == "bo" else "milano/eventi.js")
        s = open(f).read(); G = json.loads(s[s.index("=") + 1:].rstrip().rstrip(";"))["eventi"]
        for c in config(citta):
            if solo and solo not in c["nome"].lower(): continue
            t0 = time.time(); ev, esito = leggi(c)
            nostri = [e for e in G if e["luogo"] == c["nome"] and (e.get("fino") or e["data"]) >= OGGI]
            print(f"\n== {c['nome']} [{c['metodo']}] sito {len(ev)} · guida {len(nostri)} · {esito} · {time.time()-t0:.0f}s · {c.get('url_trovato') or c['url']}")
            for e in ev[:6]: print("   ", e["data"], e["ora"] or "--:--", e["titolo"][:55], "|", (e["biglietti"] or "-")[:50])
