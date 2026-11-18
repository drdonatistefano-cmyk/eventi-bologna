#!/usr/bin/env python3
"""Cartelloni letti da GitHub (15/11/2026): quello che prima Claude apriva il lunedì con Firecrawl.

Uso: python3 scripts/cartelloni.py <citta> <cartella-uscita>     (citta: bo, mi, ... come in dati/sentinella.json)

Fa tre cose, nel rispetto di robots.txt e con una pausa fra una pagina e l'altra:
  1. CARTELLONI: apre in un browser vero (Playwright) ogni pagina di dati/sentinella.json della città,
     salva il testo visibile in <uscita>/<citta>/pagine/<nome>.txt e segna se è cambiato dalla settimana prima;
     se la pagina ha dati schema.org Event li mette fra i candidati.
  2. TICKETONE: legge l'API pubblica Eventim (spettacoli in vendita in città) e la abbina alla guida con
     scripts/ticketone_abbina.py: i link d'acquisto sugli eventi già in guida li mette subito (regola fissa),
     gli spettacoli che mancano li lascia fra i candidati.
  3. SONGKICK (se la città ha l'indirizzo in CITTA): concerti dai dati schema.org MusicEvent → candidati.

Scrive <uscita>/<citta>/candidati.json e <uscita>/<citta>/LEGGIMI.md. Il giro del lunedì di Claude legge
solo questi file: non apre pagine web. Le aggiunte alla guida le decide Claude, non questo programma
(fanno eccezione i link TicketOne sugli eventi già presenti).
Per una città nuova (Ravenna, Ferrara, ...): pagine in dati/sentinella.json e una voce in CITTA.
"""
import datetime, hashlib, html, json, os, re, subprocess, sys, time, unicodedata, urllib.parse, urllib.request, urllib.robotparser

QUI = os.path.dirname(os.path.abspath(__file__))
RADICE = os.path.dirname(QUI)
UA = "Mozilla/5.0 (compatible; AchEventsBot/1.0; +https://achevents.com/)"
OGGI = datetime.date.today().isoformat()
LIMITE = (datetime.date.today() + datetime.timedelta(days=366)).isoformat()
# eventim: id città dell'API Eventim/TicketOne, uno o più (None = da trovare); songkick: pagina metro-area
# Ravenna 1137 e Ferrara 2136 dal 18/11/2026 (pagine ticketone.it/city/ravenna-1137 e /city/ferrara-2136). L'id copre il comune
# capoluogo: i teatri della provincia (Faenza, Lugo, Cento, Copparo) arrivano dalla sentinella e dai flussi automatici.
CITTA = {
    "bo": {"nome": "Bologna", "eventi": "eventi.js", "eventim": 218, "songkick": None},
    "mi": {"nome": "Milano", "eventi": "milano/eventi.js", "eventim": 215,
           "songkick": "https://www.songkick.com/metro-areas/30338-italy-milan"},
    # Ravenna: 1137 è un id «cityd» del sito e l'API non lo accetta (0 risultati il 18/11). Si cerca per nome e si tengono
    # solo gli spettacoli in provincia di Ravenna (location.state = RA): copre anche Faenza, Lugo, Cervia.
    "ra": {"nome": "Ravenna", "eventi": "ravenna/eventi.js", "eventim": 1137, "cerca": "Ravenna", "provincia": "RA", "songkick": None},
    "fe": {"nome": "Ferrara", "eventi": "ferrara/eventi.js", "eventim": 2136, "songkick": None},
}
CATEGORIE = ["Concerti", "Teatro", "Mostre e Musei"]
BLOCCO = re.compile(r"(?i)502 bad gateway|503 service|504 gateway|verifica di sicurezza|just a moment|checking your browser|attention required"
                    r"|403 error|request blocked|access denied|403 forbidden")   # 18/11: CloudFront (Alighieri, Ravenna Festival) rifiuta GitHub
NON_SPETTACOLO = re.compile(r"(?i)\babbonament|\bcarnet\b|gift ?card|buono regalo|voucher|\bstagione \d{4}\s*/\s*\d{2,4}\b|^\S+(\s\S+)? \d{4}/\d{2,4}$|\bmembership\b|\btessera\b")
STOP = set("e and the di il la lo i gli le de del della dei in a al alla live tour concerto teatro milano bologna 2026 2027 2028 show con feat ft x special guest".split())
REP = {"quando": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), "pagine": [], "ticketone": {}, "songkick": {}, "errori": []}


def get(u, tent=2, n=6_000_000):
    for i in range(tent):
        try:
            r = urllib.request.Request(u, headers={"User-Agent": UA, "Accept-Language": "it-IT,it;q=0.9", "Accept": "*/*"})
            with urllib.request.urlopen(r, timeout=40) as x:
                return x.read(n).decode("utf-8", "replace")
        except Exception as e:
            err = f"{type(e).__name__}: {e}"
            time.sleep(3)
    raise RuntimeError(err[:200])


_RP = {}
def permesso(u):
    p = urllib.parse.urlsplit(u); base = f"{p.scheme}://{p.netloc}"
    if base not in _RP:
        rp = urllib.robotparser.RobotFileParser()
        try: rp.parse(get(base + "/robots.txt", tent=1, n=200_000).splitlines())
        except Exception: rp = None
        _RP[base] = rp
    return True if _RP[base] is None else _RP[base].can_fetch(UA, u)


def tok(s):
    s = unicodedata.normalize("NFD", (s or "").lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return {w for w in re.findall(r"[a-z0-9]+", s) if w not in STOP and len(w) > 1}


def slug(s):
    s = unicodedata.normalize("NFD", s.lower()); s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:60]


def jsonld(h):
    out = []
    for b in re.findall(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', h, re.S | re.I):
        try: d = json.loads(html.unescape(b.strip()))
        except Exception: continue
        st = [d]
        while st:
            x = st.pop()
            if isinstance(x, list): st += x; continue
            if not isinstance(x, dict): continue
            t = x.get("@type"); t = " ".join(t) if isinstance(t, list) else str(t or "")
            if "Event" in t and x.get("startDate"):
                loc = x.get("location") or {}
                if isinstance(loc, list): loc = loc[0] if loc else {}
                ind = loc.get("address") if isinstance(loc, dict) else ""
                if isinstance(ind, dict): ind = ind.get("addressLocality") or ind.get("streetAddress") or ""
                perf = x.get("performer") or []
                perf = perf if isinstance(perf, list) else [perf]
                out.append({"data": str(x["startDate"])[:10], "ora": str(x["startDate"])[11:16] if len(str(x["startDate"])) > 11 else "",
                            "fino": str(x.get("endDate") or "")[:10], "titolo": html.unescape(str(x.get("name") or ""))[:160],
                            "artisti": [html.unescape(str(p.get("name", ""))) for p in perf if isinstance(p, dict)][:5],
                            "luogo": html.unescape(str(loc.get("name", "") if isinstance(loc, dict) else ""))[:100],
                            "comune": str(ind or "")[:60], "url": str(x.get("url") or "")[:300],
                            "genere": x.get("genre") if isinstance(x.get("genre"), str) else ", ".join(x.get("genre") or [])[:80]})
            for v in x.values():
                if isinstance(v, (dict, list)): st.append(v)
    return out


def carica_guida(c):
    t = open(os.path.join(RADICE, CITTA[c]["eventi"]), encoding="utf-8").read()
    return json.loads(t[t.index("{"):].rstrip().rstrip(";"))["eventi"]


def in_guida(ev, titolo, data, luogo=""):
    tt, tl = tok(titolo), tok(luogo)
    for e in ev:
        if not (e["data"] <= data <= (e.get("fino") or e["data"])): continue
        te = tok(e["artista"])
        if tt and te and len(tt & te) / max(1, min(len(tt), len(te))) >= 0.5:
            if not tl or not tok(e["luogo"]) or (tl & tok(e["luogo"])): return True
    return False


# ---------------------------------------------------------------- 1. cartelloni
def cartelloni(c, cart, cand, ev):
    pagine = [p for p in json.load(open(os.path.join(RADICE, "dati", "sentinella.json"), encoding="utf-8"))["pagine"] if p["citta"] == c]
    dove = os.path.join(cart, c, "pagine"); os.makedirs(dove, exist_ok=True)
    prima = {}
    fp = os.path.join(cart, c, "impronte.json")
    if os.path.exists(fp): prima = json.load(open(fp))
    impronte = {}
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        b = pw.chromium.launch(args=["--disable-http2"])   # Arcimboldi rifiuta HTTP/2 dai programmi
        ctx = b.new_context(user_agent=UA + " Chrome/124", locale="it-IT", viewport={"width": 1280, "height": 1600})
        for p in pagine:
            r = {"nome": p["nome"], "url": p["url"], "file": f"pagine/{slug(p['nome'])}.txt"}
            if not permesso(p["url"]):
                r["esito"] = "robots.txt vieta"; REP["pagine"].append(r); continue
            testo, h, errore = "", "", ""
            for prova in (1, 2):
                pg = ctx.new_page()
                try:
                    pg.goto(p["url"], timeout=60000, wait_until="commit")
                    try: pg.wait_for_load_state("domcontentloaded", timeout=30000)
                    except Exception: pass
                    try: pg.wait_for_load_state("networkidle", timeout=12000)
                    except Exception: pass
                    for _ in range(3):                      # carica anche gli elenchi che crescono scorrendo
                        pg.mouse.wheel(0, 4000); pg.wait_for_timeout(800)
                    testo = pg.inner_text("body"); h = pg.content(); errore = ""
                except Exception as e:
                    errore = f"{type(e).__name__}: {str(e).splitlines()[0][:100]}"
                finally:
                    pg.close()
                testo = re.sub(r"\n{2,}", "\n", "\n".join(l.strip() for l in (testo or "").splitlines() if l.strip()))[:80000]
                if not errore and not BLOCCO.search(testo[:1500]) and len(testo) > 400: break
                time.sleep(20)                              # errore del sito o pagina di protezione: si riprova una volta
            f_testo = os.path.join(cart, c, r["file"])
            if errore or BLOCCO.search(testo[:1500]) or len(testo) <= 400:
                motivo = errore or ("pagina di protezione contro i programmi" if re.search(r"(?i)verifica di sicurezza|just a moment|cloudflare", testo[:1500])
                                    else "errore del sito" if re.search(r"(?i)bad gateway|502|503|504", testo[:300]) else "pagina quasi vuota")
                r["esito"] = "non letta: " + motivo
                r["cambiata"] = False
                r["testo"] = "quello della lettura precedente" if os.path.exists(f_testo) else "nessuno"
                impronte[p["url"]] = prima.get(p["url"], "")
            else:
                imp = hashlib.sha1(re.sub(r"\d+", "", testo).encode()).hexdigest()
                impronte[p["url"]] = imp
                r.update(esito="ok", caratteri=len(testo), cambiata=prima.get(p["url"]) != imp)
                open(f_testo, "w", encoding="utf-8").write(f"# {p['nome']}\n# {p['url']}\n# letta il {OGGI}\n\n{testo}\n")
                # 18/11/2026: anche i link interni della pagina (testo → indirizzo), per trovare la pagina del calendario
                # quando la sentinella legge una home con poco testo, senza che Claude apra il sito
                base = urllib.parse.urlsplit(p["url"]).netloc
                visti_l, righe_l = set(), []
                for hr, tx in re.findall(r'<a\b[^>]*href="([^"#]+)"[^>]*>(.*?)</a>', h, re.S | re.I):
                    u = urllib.parse.urljoin(p["url"], html.unescape(hr))
                    t_ = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", tx))).strip()[:80]
                    if urllib.parse.urlsplit(u).netloc == base and u not in visti_l:
                        visti_l.add(u); righe_l.append(f"{t_}\t{u}")
                open(f_testo[:-4] + ".link.tsv", "w", encoding="utf-8").write("\n".join(righe_l[:400]) + "\n")
                if not re.search(r"songkick\.com", p["url"]):     # Songkick si legge a parte, tutte le pagine
                    ej = [e for e in jsonld(h) if OGGI <= e["data"] <= LIMITE]
                    r["eventi_strutturati"] = len(ej)
                    for e in ej:
                        e["fonte"] = p["nome"]; e["gia_in_guida"] = in_guida(ev, e["titolo"], e["data"], e["luogo"])
                        if not e["gia_in_guida"]: cand.append(e)
            REP["pagine"].append(r)
            time.sleep(2)
        b.close()
    json.dump(impronte, open(fp, "w"), indent=1)


# ---------------------------------------------------------------- 2. TicketOne
def ticketone(c, cart, cand):
    cid = CITTA[c].get("eventim")
    if not cid:
        REP["ticketone"] = {"esito": "manca l'id città Eventim"}; return
    gruppi = {}
    for cid, cat in [(i, k) for i in (cid if isinstance(cid, list) else [cid]) for k in CATEGORIE]:
        for pag in range(1, 9):
            u = ("https://public-api.eventim.com/websearch/search/api/exploration/v2/productGroups?webId=web__ticketone-it&language=it"
                 f"&city_ids={cid}&page={pag}&sort=DateAsc&in_stock=true&categories={urllib.parse.quote(cat)}")
            try: d = json.loads(get(u))
            except Exception as e:
                REP["errori"].append(f"TicketOne {cat} p.{pag}: {e}"); break
            for g in d.get("productGroups", []): gruppi[g["productGroupId"]] = g
            if pag >= int(d.get("totalPages") or 1): break
            time.sleep(1.5)
    if not gruppi and CITTA[c].get("cerca"):   # l'id non ha dato nulla: ricerca per nome, filtrata per provincia
        pr = CITTA[c].get("provincia")
        for cat in CATEGORIE:
            for pag in range(1, 9):
                u = ("https://public-api.eventim.com/websearch/search/api/exploration/v2/productGroups?webId=web__ticketone-it&language=it"
                     f"&search_term={urllib.parse.quote(CITTA[c]['cerca'])}&page={pag}&sort=DateAsc&in_stock=true&categories={urllib.parse.quote(cat)}")
                try: d = json.loads(get(u))
                except Exception as e:
                    REP["errori"].append(f"TicketOne ricerca {cat} p.{pag}: {e}"); break
                for g in d.get("productGroups", []):
                    g["products"] = [x for x in g.get("products", [])
                                     if not pr or x.get("typeAttributes", {}).get("liveEntertainment", {}).get("location", {}).get("state") == pr]
                    g["productCount"] = len(g["products"])   # dopo il filtro: le date rimaste sono tutte quelle in provincia
                    if g["products"]: gruppi[g["productGroupId"]] = g
                if pag >= int(d.get("totalPages") or 1): break
                time.sleep(1.5)
        REP["ticketone_ricerca"] = f"per nome «{CITTA[c]['cerca']}», provincia {pr}: {len(gruppi)} gruppi"
    G = list(gruppi.values())
    json.dump(G, open(os.path.join(cart, c, "ticketone.json"), "w"), ensure_ascii=False)
    REP["ticketone"] = {"gruppi": len(G), **({"ricerca": REP.pop("ticketone_ricerca")} if "ticketone_ricerca" in REP else {})}
    if not G: return
    # abbinamento: lo stesso programma che Claude lanciava a mano, su una copia
    tmp = f"/tmp/t1_{c}"; os.makedirs(tmp, exist_ok=True)
    ev = carica_guida(c)
    json.dump(ev, open(tmp + "/eventi.json", "w"), ensure_ascii=False)
    p = subprocess.run([sys.executable, os.path.join(QUI, "ticketone_abbina.py"), tmp, os.path.join(cart, c, "ticketone.json"),
                        CITTA[c]["nome"], "--aggiungi"], capture_output=True, text=True)
    REP["ticketone"]["abbinamento"] = p.stdout.strip()[-400:]
    if p.returncode:
        REP["errori"].append("ticketone_abbina: " + p.stderr[-300:]); return
    dopo = json.load(open(tmp + "/eventi.json"))
    n0 = len(ev)
    vecchi, nuovi = dopo[:n0], dopo[n0:]
    link = [(a, b) for a, b in zip(ev, vecchi) if a.get("id") == b.get("id") and a.get("biglietti") != b.get("biglietti")]
    REP["ticketone"]["link_nuovi"] = len(link)
    REP["ticketone"]["spettacoli_mancanti"] = len(nuovi)
    for x in nuovi:
        cand.append({"data": x["data"], "fino": x["fino"], "ora": x["ora"], "titolo": x["artista"], "luogo": x["luogo"], "comune": x["citta"],
                     "url": x["biglietti"], "genere": f"{x['genere']}/{x['tipo']}".strip("/"), "descrizione": x["descrizione"],
                     "fonte": "TicketOne", "gia_in_guida": False, "evento_pronto": x})
    if link:
        # i link si applicano subito: passano da aggiorna.py, che convalida tutto o non scrive nulla
        file_js = os.path.join(RADICE, CITTA[c]["eventi"])
        cc = ["--citta", c] if c != "bo" else []
        json.dump(vecchi, open(tmp + "/da_scrivere.json", "w"), ensure_ascii=False)
        q = subprocess.run([sys.executable, os.path.join(QUI, "aggiorna.py"), tmp + "/da_scrivere.json", "--out", file_js] + cc,
                           capture_output=True, text=True, cwd=tmp)
        REP["ticketone"]["link_scritti"] = q.returncode == 0
        if q.returncode: REP["errori"].append("convalida dei link TicketOne: " + q.stdout[-300:])
    controllo_ticketone(c, G, cand)


# 18/11/2026 (Stefano: «verificate se ci sono tutti i link?»): ogni domenica si confronta ogni data in vendita su TicketOne
# nei prossimi 3 mesi con la guida, e si dice che cosa manca. Prima un gruppo TicketOne già usato da un evento contava
# come «coperto» anche se la guida aveva solo la prima data (Cremonini 27/11 sì, 28/11 no; Giacobazzi 17/11 sì, 15/12 no).
def controllo_ticketone(c, G, cand):
    def url(x): return x["url"]["domain"] + x["url"]["path"]
    def somiglia(a, b):   # stessa regola di ticketone_abbina.py: almeno metà delle parole del titolo più corto, e almeno 2 se ne ha 2
        i = a & b
        return bool(i) and len(i) / max(1, min(len(a), len(b))) >= 0.5 and len(i) >= min(2, len(a), len(b))
    oggi, fine = OGGI, (datetime.date.fromisoformat(OGGI) + datetime.timedelta(days=92)).isoformat()
    ev = carica_guida(c)   # dopo i link appena scritti
    try:
        t = open(os.path.join(RADICE, CITTA[c]["eventi"].replace("eventi.js", "mostre.js")), encoding="utf-8").read()
        mo = json.loads(t[t.index("{"):].rstrip().rstrip(";")).get("mostre", [])
    except Exception:
        mo = []
    u2g = {}
    for g in G:
        u2g[url(g)] = g["productGroupId"]
        for x in g["products"]: u2g[url(x)] = g["productGroupId"]
    per_gruppo = {}
    for e in ev:
        b = (e.get("biglietti") or "").split("?")[0]
        if b in u2g: per_gruppo.setdefault(u2g[b], []).append(e)
    gia_cand = {x.get("url") for x in cand}
    R = {"date_in_vendita": 0, "coperte": 0, "date_mancanti": 0, "senza_link_ticketone": 0, "non_in_guida": 0, "mostre_senza_link": 0, "mostre_non_in_guida": 0}
    da_controllare = []
    for g in G:
        sub = [x["name"] for x in g.get("categories", []) if "parentCategory" in x]
        mostra = any(x.startswith(("Mostre", "Musei")) for x in sub)
        tg = tok(g["name"]) | tok(g.get("mainAttraction", {}).get("name", ""))
        for x in g["products"]:
            le = x["typeAttributes"]["liveEntertainment"]; d = le["startDate"][:10]
            if not (oggi <= d <= fine): continue
            if mostra:
                m = next((m for m in mo if (m.get("inizio") or "") <= d <= (m.get("fine") or "9999") and somiglia(tg, tok(m.get("titolo") or ""))), None)
                if not m:
                    R["mostre_non_in_guida"] += 1; da_controllare.append({"cosa": "mostra in vendita su TicketOne, non in guida", "titolo": g["name"], "luogo": le["location"]["name"], "url": url(g)})
                elif not re.search(r"ticketone|tiqets", m.get("biglietti") or ""):
                    R["mostre_senza_link"] += 1; da_controllare.append({"cosa": "mostra in guida senza link d'acquisto", "titolo": m.get("titolo"), "id": m.get("id"), "url": url(g)})
                break   # una mostra conta una volta, non per ogni giorno
            R["date_in_vendita"] += 1
            if url(g) in gia_cand or url(x) in gia_cand: continue
            E = per_gruppo.get(g["productGroupId"], [])
            if any(e["data"] <= d <= (e.get("fino") or e["data"]) for e in E):
                R["coperte"] += 1; continue
            if E:   # lo spettacolo c'è, questa data no: candidato pronto, copiato dalla scheda già in guida
                base = min(E, key=lambda e: abs((datetime.date.fromisoformat(e["data"]) - datetime.date.fromisoformat(d)).days))
                nuovo = {**base, "id": "", "data": d, "fino": d, "ora": le["startDate"][11:16] if le["startDate"][11:16] not in ("", "00:00") else "n.d.",
                         "biglietti": url(x), "biglietti_tipo": "Acquista", "disp_verificata": OGGI}
                R["date_mancanti"] += 1
                cand.append({"data": d, "fino": d, "ora": nuovo["ora"], "titolo": base["artista"], "luogo": base["luogo"], "comune": base.get("citta", ""),
                             "url": url(x), "genere": f"{base.get('genere','')}/{base.get('tipo','')}".strip("/"), "descrizione": base.get("descrizione", ""),
                             "fonte": "TicketOne (data in più di uno spettacolo già in guida)", "gia_in_guida": False, "evento_pronto": nuovo})
                gia_cand.add(url(x)); continue
            simile = next((e for e in ev if e["data"] <= d <= (e.get("fino") or e["data"]) and somiglia(tg, tok(e["artista"] + " " + e.get("titolo", "")))), None)
            if simile and "ticketone" not in (simile.get("biglietti") or ""):
                R["senza_link_ticketone"] += 1
                da_controllare.append({"cosa": "forse lo stesso spettacolo, in guida senza TicketOne: controllare e, se è lui, mettere il link",
                                       "id": simile["id"], "in_guida": simile["artista"], "su_ticketone": g["name"], "data": d, "url": url(x)})
            elif not simile:
                R["non_in_guida"] += 1
                da_controllare.append({"cosa": "in vendita su TicketOne, non in guida e non fra i candidati (spesso pacchetti, prove TV, laboratori)",
                                       "titolo": g["name"], "data": d, "luogo": le["location"]["name"], "categorie": sub, "url": url(x)})
    REP["controllo_ticketone"] = {**R, "da_controllare": da_controllare[:80]}


# ---------------------------------------------------------------- 3. Songkick
def songkick(c, cart, cand, ev):
    base = CITTA[c].get("songkick")
    if not base: return
    tutti, pag = [], 1
    while pag <= 20:
        u = base + ("" if pag == 1 else f"?page={pag}")
        if not permesso(u):
            REP["songkick"]["esito"] = "robots.txt vieta"; break
        try: h = get(u, tent=2)
        except Exception as e:
            REP["errori"].append(f"Songkick p.{pag}: {e}"); break
        evs = [e for e in jsonld(h) if OGGI <= e["data"] <= LIMITE]
        if not evs: break
        tutti += evs; pag += 1; time.sleep(2)
    visti = set()
    for e in tutti:
        k = (e["data"], e["titolo"].lower(), e["luogo"].lower())
        if k in visti: continue
        visti.add(k)
        e["fonte"] = "Songkick"
        e["gia_in_guida"] = in_guida(ev, " ".join(e["artisti"]) or e["titolo"], e["data"], e["luogo"])
        if not e["gia_in_guida"]: cand.append(e)
    REP["songkick"].update({"pagine": pag - 1, "concerti": len(visti), "mancanti": sum(1 for e in cand if e["fonte"] == "Songkick")})


def main():
    c, cart = sys.argv[1], sys.argv[2]
    if c not in CITTA: sys.exit(f"città {c} non configurata in CITTA")
    os.makedirs(os.path.join(cart, c), exist_ok=True)
    ev = carica_guida(c)
    cand = []
    for nome, f in (("cartelloni", lambda: cartelloni(c, cart, cand, ev)), ("ticketone", lambda: ticketone(c, cart, cand)),
                    ("songkick", lambda: songkick(c, cart, cand, ev))):
        try: f()
        except Exception as e: REP["errori"].append(f"{nome}: {type(e).__name__}: {str(e)[:200]}")
    # niente abbonamenti e carnet, niente doppioni fra fonti (stesso giorno, stesso titolo e luogo)
    tolti = [e for e in cand if NON_SPETTACOLO.search(e["titolo"])]
    cand = [e for e in cand if not NON_SPETTACOLO.search(e["titolo"])]
    uniti, visti = [], {}
    for e in sorted(cand, key=lambda e: (e["fonte"] != "TicketOne", e["data"])):   # TicketOne prima: ha il link d'acquisto
        k = (e["data"], frozenset(tok(e["titolo"])) or e["titolo"])
        doppio = next((x for kk, x in visti.items() if kk[0] == k[0] and (k[1] == kk[1] or (tok(e["titolo"]) & tok(x["titolo"]) and
                       len(tok(e["titolo"]) & tok(x["titolo"])) / max(1, min(len(tok(e["titolo"])), len(tok(x["titolo"])))) >= 0.6))), None)
        if doppio:
            doppio.setdefault("anche_su", []).append(e["fonte"]); continue
        visti[k] = e; uniti.append(e)
    REP["tolti_non_spettacoli"] = len(tolti)
    cand = sorted(uniti, key=lambda e: (e["data"], e["titolo"]))
    json.dump({"citta": CITTA[c]["nome"], **REP, "candidati": cand}, open(os.path.join(cart, c, "candidati.json"), "w"), ensure_ascii=False, indent=1)
    cambiate = [p for p in REP["pagine"] if p.get("cambiata")]
    righe = [f"# Cartelloni di {CITTA[c]['nome']} letti da GitHub — {REP['quando']}", "",
             "Il giro del lunedì legge questi file e non apre pagine web.", "",
             f"- Candidati da giudicare (non ancora in guida): **{len(cand)}** in `candidati.json`",
             f"- TicketOne: {REP['ticketone']}", f"- Songkick: {REP['songkick'] or 'non previsto per questa città'}", "",
             *controllo_righe(REP.get("controllo_ticketone")),
             "## Pagine dei cartelloni", "", "| Pagina | Esito | Cambiata | Eventi strutturati | Testo |", "|---|---|---|---|---|"]
    for p in REP["pagine"]:
        righe.append(f"| {p['nome']} | {p.get('esito')} | {'**sì**' if p.get('cambiata') else 'no'} | {p.get('eventi_strutturati', '')} | `{p['file']}` |")
    if REP["errori"]:
        righe += ["", "## Errori", ""] + [f"- {e}" for e in REP["errori"]]
    open(os.path.join(cart, c, "LEGGIMI.md"), "w", encoding="utf-8").write("\n".join(righe) + "\n")
    print(f"{c}: {len(REP['pagine'])} pagine ({len(cambiate)} cambiate), candidati {len(cand)}, TicketOne {REP['ticketone']}, Songkick {REP['songkick']}, errori {len(REP['errori'])}")
    for e in REP["errori"]: print("  !", e)


def controllo_righe(R):
    if not R: return []
    r = ["## Controllo TicketOne (date in vendita nei prossimi 3 mesi)", "",
         f"- Date in vendita: {R['date_in_vendita']}, già in guida con il link: {R['coperte']}",
         f"- Date in più di spettacoli già in guida, messe fra i candidati pronti: **{R['date_mancanti']}**",
         f"- Forse in guida ma senza link TicketOne, da controllare: **{R['senza_link_ticketone']}**",
         f"- In vendita e non in guida (spesso pacchetti, prove TV, laboratori): {R['non_in_guida']}",
         f"- Mostre in vendita su TicketOne: senza link in guida {R['mostre_senza_link']}, non in guida {R['mostre_non_in_guida']}",
         "", "Il dettaglio è in `candidati.json`, voce `controllo_ticketone.da_controllare`.", ""]
    return r


if __name__ == "__main__":
    main()
