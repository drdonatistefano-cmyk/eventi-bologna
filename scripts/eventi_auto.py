"""Aggiornamento automatico di eventi e mostre (gira su GitHub Actions, senza Claude).
uso: python3 scripts/eventi_auto.py bo|mi [--prova]

Fonti (tutte lette nel rispetto dei robots.txt):
  - DICE (dice.fm/browse/<città>): concerti, club, comicità, teatro, con link ai biglietti
  - Ticketmaster Discovery API, solo se c'è il segreto TICKETMASTER_KEY
  - arte.it (calendario mostre del mese corrente e del prossimo) per le mostre
  - Galleria Wikiarte (wikiarte.com, solo Bologna): mostre in corso e prossime della prima pagina
Regole: non toglie mai eventi o mostre (lo fa aggiorna.py solo per quelli finiti),
aggiunge solo ciò che manca, completa il link biglietti dove manca, e scrive solo
se aggiorna.py convalida tutto. Riepilogo in dati/auto_<città>.json."""
import json, re, sys, os, time, datetime, unicodedata, urllib.request, urllib.parse, subprocess, html

QUI = os.path.dirname(os.path.abspath(__file__))
RADICE = os.path.dirname(QUI)
CITTA = sys.argv[1] if len(sys.argv) > 1 else "bo"
PROVA = "--prova" in sys.argv
sys.argv = [sys.argv[0]] + (["--citta", "mi"] if CITTA == "mi" else [])
sys.path.insert(0, QUI)
import aggiorna as A  # comuni, generi e regole di convalida

CFG = {"bo": dict(eventi="eventi.js", mostre="mostre.js", dice="bologna", nome="Bologna", arte="bologna", tm="Bologna"),
       "mi": dict(eventi="milano/eventi.js", mostre="milano/mostre.js", dice="milan", nome="Milano", arte="milano", tm="Milano")}[CITTA]
UA = "Mozilla/5.0 (compatible; AchEventsGuide/1.0; +https://achevents.com)"
OGGI = datetime.date.today().isoformat()
LIMITE = (datetime.date.today() + datetime.timedelta(days=365)).isoformat()
COMUNI = set(A.COMUNE)
ALIAS_C = {"milan": "Milano", "milano": "Milano", "bologna": "Bologna", **{k: v for k, v in A.ALIAS.items()}}
STOP = set("e and the di il la lo i gli le de del della dei in a al alla live tour concerto teatro milano bologna milan 2026 2027 show con feat ft x special guest guests ospiti presenta in tickets".split())
R = {"aggiunti": [], "link_biglietti": 0, "fonti": {}, "errori": []}


def get(u, tipo="text", tent=3):
    for i in range(tent):
        try:
            r = urllib.request.Request(u, headers={"User-Agent": UA, "Accept-Language": "it-IT,it;q=0.9"})
            b = urllib.request.urlopen(r, timeout=30).read().decode("utf-8", "ignore")
            return json.loads(b) if tipo == "json" else b
        except Exception as ex:
            if i == tent - 1:
                R["errori"].append(f"{u[:90]}: {ex}")
                return None
            time.sleep(3 * (i + 1))


def tok(s):
    s = unicodedata.normalize("NFD", (s or "").lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return {w for w in re.findall(r"[a-z0-9]+", s) if w not in STOP and len(w) > 1}


VTOGLI = r"(?i)\b(teatro|club|circolo|arci|spazio|sala|auditorium|live|milano|bologna|music|the|di|del|della)\b"
def vtok(s): return tok(re.sub(VTOGLI, " ", s or "")) or tok(s)


def comune(nome, indirizzo=""):
    c = ALIAS_C.get((nome or "").strip().lower(), (nome or "").strip())
    if c in COMUNI: return c
    m = [x for x in COMUNI if A.norm(x) == A.norm(c)]
    if m: return m[0]
    for x in sorted(COMUNI, key=len, reverse=True):  # comune scritto nell'indirizzo
        if re.search(r"\b%s\b" % re.escape(x), indirizzo or ""): return x
    return ""


# ---------- dati esistenti ----------
ev = A.leggi(os.path.join(RADICE, CFG["eventi"]))
mo = A.leggi_mostre(os.path.join(RADICE, CFG["mostre"]))
LUOGHI = {}
for e in ev: LUOGHI.setdefault(e["luogo"], e.get("citta"))
VEN = getattr(A, "VEN", []) if CITTA == "mi" else []


def luogo_guida(nome):
    """Usa il nome del luogo già scritto nella guida, se è lo stesso posto."""
    for rx, n in VEN:
        if re.search(rx, nome.lower()): return n
    tv = vtok(nome)
    cand = [l for l in LUOGHI if tv and vtok(l) and (tv <= vtok(l) or vtok(l) <= tv)]
    return min(cand, key=len) if cand else nome.strip()


def gia(x):
    """Evento già in guida? Restituisce l'evento esistente."""
    tx, vx = tok(x["artista"]), vtok(x["luogo"])
    for e in ev:
        if not (e["data"] <= x["fino"] and x["data"] <= (e.get("fino") or e["data"])): continue
        te = tok(e["artista"])
        stesso_luogo = e["luogo"] == x["luogo"] or bool(vx & vtok(e["luogo"]))
        q = len(tx & te) / max(1, min(len(tx), len(te))) if tx and te else 0
        if stesso_luogo and q > 0: return e
        if q >= 0.8 and e["data"] == x["data"]: return e
    return None


# ---------- generi (MusicBrainz, con memoria in dati/generi_artisti.json) ----------
GFILE = os.path.join(RADICE, "dati", "generi_artisti.json")
GEN = json.load(open(GFILE)) if os.path.exists(GFILE) else {}
GEN_NUOVI = [0]
ROCK = ("rock", "metal", "punk", "indie", "alternative", "hardcore", "grunge", "shoegaze", "post-punk", "garage", "emo", "prog", "stoner", "doom", "noise", "new wave", "blues", "folk", "country", "psychedelic")
JAZZ = ("jazz", "soul", "funk", "bossa", "swing", "fusion", "gospel")
CLAS = ("classical", "opera", "baroque", "orchestral", "chamber", "neoclassical")


def genere_mb(nome):
    n = re.split(r"\s+(?:\+|&|e|and|with|w/|-|–|\|)\s+|,|:| @ ", nome)[0].strip()
    if n in GEN: return GEN[n].get("genere", "")
    if GEN_NUOVI[0] >= 60: return ""
    GEN_NUOVI[0] += 1
    time.sleep(1.1)  # regola di MusicBrainz: una richiesta al secondo
    try:
        r = urllib.request.Request("https://musicbrainz.org/ws/2/artist/?fmt=json&limit=1&query=" + urllib.parse.quote('artist:"%s"' % n),
                                   headers={"User-Agent": "AchEventsGuide/1.0 ( https://achevents.com )", "Accept": "application/json"})
        a = (json.load(urllib.request.urlopen(r, timeout=10)).get("artists") or [None])[0]
    except Exception:
        return ""
    g, tags = "", []
    if a and a.get("score", 0) >= 90:
        tags = [t["name"] for t in sorted(a.get("tags", []), key=lambda t: -t.get("count", 0))]
        for t in tags:
            if any(k in t for k in CLAS): g = "Classica"; break
            if any(k in t for k in JAZZ): g = "Jazz"; break
            if any(k in t for k in ROCK): g = "Rock"; break
        if tags and not g: g = "Pop e altra musica"
    GEN[n] = {"genere": g, "tag": tags[:6], "mbid": (a or {}).get("id", "")}
    return g


TIPO_G = {"Rock": "Concerto rock", "Jazz": "Concerto jazz", "Classica": "Concerto di musica classica", "Pop e altra musica": "Concerto"}


CITTA_RX = r"(?:Bologna|Milano|Milan)(?:,?\s*(?:Italy|Italia|IT))?"
def pulisci_titolo(t, luogo):
    t = re.sub(r"\s+", " ", t).strip()
    t = re.sub(r"(?i)\s*@\s*%s\b.*$" % re.escape(luogo.split()[0]) if luogo else r"$^", "", t)  # «@Teatro Testoni …»
    t = re.sub(r"\s*@\s*[^@]{3,40}$", "", t)                                # «… @ luogo»
    t = re.sub(r"\s*[:\-–|]\s*\?+\s*$", "", t)
    for _ in range(2):
        t = re.sub(r"(?i)\s*[-–|•:,]\s*%s\s*$" % CITTA_RX, "", t)       # «… - Bologna», «| Milano»
        t = re.sub(r"(?i)\s*\(\s*%s\s*\)\s*$" % CITTA_RX, "", t)       # «(Bologna)»
        t = re.sub(r"(?i)\s+(?:a|in|at)\s+%s\s*$" % CITTA_RX, "", t)     # «… a Bologna»
        t = re.sub(r"(?i)\s*[-–|•:]\s*$", "", t)
    return t.strip() or luogo


def nuovo(artista, d, fino, ora, luogo, citta, genere, tipo, url, disp, fonte):
    al = "all'" if re.match(r"(?i)[aeiou]", luogo) else "al "
    desc = {"Serate e club": f"Serata nel club {luogo}.", "Teatro": f"{tipo or 'Spettacolo'} {al}{luogo}."}.get(genere, f"{tipo or 'Concerto'} dal vivo {al}{luogo}.")
    artista = pulisci_titolo(artista, luogo)
    return {"id": "", "data": d, "fino": fino, "ora": ora, "artista": artista, "luogo": luogo, "citta": citta, "genere": genere,
            "tipo": tipo, "rassegna": "", "descrizione": desc, "fonte": fonte, "biglietti": url, "biglietti_tipo": "Acquista" if url else "",
            "disp": disp, "disp_nota": "", "disp_verificata": OGGI if disp != "da verificare" else "", "sito_luogo": ""}


def aggiungi(x, fonte_nome):
    e = gia(x)
    if e:
        if not re.match(r"^https://", e.get("biglietti") or "") and x["biglietti"]:
            e["biglietti"], e["biglietti_tipo"] = x["biglietti"], "Acquista"
            R["link_biglietti"] += 1
        return False
    ev.append(x)
    R["aggiunti"].append(f'{x["data"]} {x["artista"]} – {x["luogo"]} ({fonte_nome})')
    return True


# ---------- DICE ----------
def dice():
    base = "https://dice.fm/browse/" + CFG["dice"]
    pag = get(base)
    if not pag: return
    def dati(s):
        m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', s or "", re.S)
        return json.loads(m.group(1))["props"]["pageProps"] if m else {}
    p0 = dati(pag)
    viste = {"": p0}
    for f in p0.get("primaryFilters") or []:
        time.sleep(1.5)
        viste[f["id"]] = dati(get("https://dice.fm" + f["activateLink"]))
    visti, n = set(), 0
    ordine = [c for c in viste if c not in ("", "music:gig")] + ["music:gig"]  # prima le categorie più precise
    for cat in ordine:
        for x in (viste.get(cat) or {}).get("events") or []:
            if x["id"] in visti: continue
            visti.add(x["id"])
            v = (x.get("venues") or [{}])[0]
            c = comune((v.get("city") or {}).get("name", ""), v.get("address", ""))
            if not c: continue
            dt = x["dates"]["event_start_date"]; d = dt[:10]
            fe = (x["dates"].get("event_end_date") or dt)[:10]
            if d < OGGI or d > LIMITE: continue
            fino = fe if x["dates"].get("is_multi_days_event") and fe >= d else d
            ora = dt[11:16]
            luogo = luogo_guida(v.get("name") or "")
            if not luogo: continue
            if cat in ("music:party", "music:dj"): g, t = "Serate e club", "Serata"
            elif cat == "culture:comedy": g, t = "Teatro", "Comicità"
            elif cat == "culture:theatre": g, t = "Teatro", "Spettacolo"
            elif cat == "music:gig":
                g = genere_mb(x["name"]) or "Pop e altra musica"; t = TIPO_G[g]
            else: continue
            st = (x.get("status") or "").lower()
            disp = "sold out" if "sold" in st else "disponibile" if st == "on-sale" else "da verificare"
            url = "https://dice.fm/event/" + x["id"]
            n += aggiungi(nuovo(x["name"].strip(), d, fino, ora, luogo, c, g, t, url, disp, url), "DICE")
    R["fonti"]["DICE"] = {"letti": len(visti), "aggiunti": n}


# ---------- Ticketmaster (solo con chiave) ----------
def ticketmaster():
    k = os.environ.get("TICKETMASTER_KEY", "").strip()
    if not k:
        R["fonti"]["Ticketmaster"] = "manca la chiave TICKETMASTER_KEY"; return
    letti, n = 0, 0
    for pg in range(5):
        u = ("https://app.ticketmaster.com/discovery/v2/events.json?" + urllib.parse.urlencode(
            {"apikey": k, "countryCode": "IT", "city": CFG["tm"], "size": 200, "page": pg, "sort": "date,asc", "locale": "*"}))
        d = get(u, "json")
        if not d: break
        evs = (d.get("_embedded") or {}).get("events") or []
        for x in evs:
            letti += 1
            v = ((x.get("_embedded") or {}).get("venues") or [{}])[0]
            c = comune((v.get("city") or {}).get("name", ""), (v.get("address") or {}).get("line1", ""))
            s = (x.get("dates") or {}).get("start") or {}
            d0 = s.get("localDate") or ""
            if not c or not d0 or d0 < OGGI or d0 > LIMITE: continue
            cl = (x.get("classifications") or [{}])[0]
            seg = (cl.get("segment") or {}).get("name", ""); gn = (cl.get("genre") or {}).get("name", "")
            if seg == "Music":
                g = "Classica" if re.search(r"(?i)classical|opera", gn) else "Jazz" if re.search(r"(?i)jazz|blues|soul", gn) else \
                    "Rock" if re.search(r"(?i)rock|metal|punk|alternative", gn) else (genere_mb(x["name"]) or "Pop e altra musica")
                t = TIPO_G[g]
            elif seg == "Arts & Theatre": g, t = "Teatro", "Spettacolo"
            else: continue
            st = ((x.get("dates") or {}).get("status") or {}).get("code", "")
            disp = {"onsale": "disponibile", "offsale": "non disponibile", "cancelled": "non disponibile"}.get(st, "da verificare")
            if st in ("cancelled", "postponed"): continue
            n += aggiungi(nuovo(x["name"].strip(), d0, d0, (s.get("localTime") or "")[:5] or "n.d.", luogo_guida(v.get("name", "")), c, g, t,
                                x.get("url", ""), disp, x.get("url", "")), "Ticketmaster")
        if (d.get("page") or {}).get("totalPages", 1) <= pg + 1: break
        time.sleep(0.6)
    R["fonti"]["Ticketmaster"] = {"letti": letti, "aggiunti": n}


# ---------- mostre da arte.it ----------
MESI = {m: i for i, m in enumerate("gennaio febbraio marzo aprile maggio giugno luglio agosto settembre ottobre novembre dicembre".split(), 1)}
def data_it(s):
    m = re.match(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", s.strip())
    return f"{int(m.group(3)):04d}-{MESI[m.group(2).lower()]:02d}-{int(m.group(1)):02d}" if m and m.group(2).lower() in MESI else ""

CAT = [(r"fotograf", "Fotografia"), (r"scultur|scultor", "Scultura"), (r"\bdesign|moda|fashion|tessil", "Design e moda"),
       (r"cinema|film|fumett", "Cinema e spettacolo"), (r"archeolog|egizi|etrusc|romani|storia|storic", "Storia e archeologia"),
       (r"immersiv|experience|multimedial", "Esperienze immersive"), (r"scienz|tecnolog|leonardo", "Scienza e tecnica"),
       (r"disegn|grafic|illustr|stamp|incision|carta", "Disegno, grafica e illustrazione"),
       (r"contemporane|installazion|video", "Arte contemporanea e installazioni"), (r"pittur|pittor|dipint|tele|capolavor", "Pittura")]


def arte():
    oggi = datetime.date.today(); mesi = [(oggi.year, oggi.month)]
    mesi.append((oggi.year + (oggi.month == 12), 1 if oggi.month == 12 else oggi.month + 1))
    letti, n, visti = 0, 0, set()
    for y, m in mesi:
        s = get(f"https://www.arte.it/calendario-arte/{CFG['arte']}/{y}/{m:02d}/")
        if not s: continue
        for blocco in re.findall(r'<a href="(/calendario-arte/[^"]+)" class="link_mostre_list">(.*?)</a>', s, re.S):
            href, b = blocco
            if href in visti: continue
            visti.add(href); letti += 1
            def campo(c):
                x = re.search(r'<span class="%s">(.*?)</span>' % c, b, re.S)
                return html.unescape(re.sub(r"<[^>]+>|\s+", " ", x.group(1))).strip() if x else ""
            tit = html.unescape(re.sub(r"<[^>]+>|\s+", " ", (re.search(r"<h2>(.*?)</h2>", b, re.S) or [None, ""])[1])).strip()
            dd = re.match(r"Dal (.+?) al (.+)$", campo("data"))
            occ = campo("occhiello").split("|")
            if not (tit and dd and len(occ) >= 2): continue
            ini, fin = data_it(dd.group(1)), data_it(dd.group(2))
            c = comune(occ[0].strip()); sede = occ[1].strip()
            if not (ini and fin and c and sede) or fin < OGGI or ini > LIMITE: continue
            tt = tok(tit)
            if any((len(tt & tok(x["titolo"])) / max(1, min(len(tt), len(tok(x["titolo"])))) >= 0.6) for x in mo if tok(x["titolo"])):
                continue
            testo = (tit + " " + campo("sommario")).lower()
            cat = next((v for rx, v in CAT if re.search(rx, testo)), "Pittura")
            al = "all'" if re.match(r"(?i)[aeiou]", sede) else "a "
            mo.append({"id": "", "titolo": tit, "sede": sede, "citta": c, "inizio": ini, "fine": fin, "categoria": cat,
                       "descrizione": f"Mostra {al}{sede}.", "ingresso": "da verificare", "orari": "",
                       "fonte": "https://www.arte.it" + urllib.parse.quote(href, safe="/-"), "sito": ""})
            R["aggiunti"].append(f"mostra {ini}→{fin} {tit} – {sede} (arte.it)"); n += 1
        time.sleep(1.5)
    R["fonti"]["arte.it"] = {"letti": letti, "aggiunti": n}


# ---------- Galleria Wikiarte (Bologna, Galleria Falcone e Borsellino 2/D): una mostra personale ogni 2 settimane ----------
MESI_EN = {m: i for i, m in enumerate("january february march april may june july august september october november december".split(), 1)}


def wikiarte():
    if CITTA != "bo": return
    rob = get("https://www.wikiarte.com/robots.txt", tent=1) or ""
    if re.search(r"(?im)^user-agent:\s*\*\s*$(?:\n(?!user-agent).*)*?\n\s*disallow:\s*/\s*$", rob):
        R["fonti"]["wikiarte"] = {"letti": 0, "aggiunti": 0, "nota": "robots.txt vieta"}; return
    s = get("https://www.wikiarte.com/")
    if not s: return
    links = []
    for u in re.findall(r'href="(https://www\.wikiarte\.com/20\d\d/\d\d/\d\d/[^"#?]+/)"', s):
        if u not in links and not re.search(r"fiera|baf-|arte-fiera|asta", u): links.append(u)
    letti = n = 0; trovate = []
    for u in links[:6]:
        time.sleep(1.5)
        h = get(u)
        if not h: continue
        letti += 1
        og = lambda k: html.unescape((re.search(r'<meta property="og:%s" content="([^"]*)"' % k, h) or [None, ""])[1]).strip()
        tit = re.sub(r"\s*[-–]\s*Galleria Wikiarte\s*$", "", og("title")).strip()
        testo = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", re.sub(r"(?s)<script.*?</script>|<style.*?</style>", " ", h))))
        mesi = "|".join(list(MESI) + list(MESI_EN))
        def d(g, m, y): 
            k = m.lower(); return f"{int(y):04d}-{(MESI.get(k) or MESI_EN.get(k)):02d}-{int(g):02d}"
        dd = re.search(r"(?i)(?:durata|duration)[^0-9]{0,40}(\d{1,2})\s+(%s)(?:\s+(\d{4}))?\s+(?:al|a|to|-|–)\s+(\d{1,2})\s+(%s)\s+(\d{4})" % (mesi, mesi), testo) \
            or re.search(r"(?i)\bdal\s+(\d{1,2})\s+(%s)(?:\s+(\d{4}))?\s+al\s+(\d{1,2})\s+(%s)\s+(\d{4})" % (mesi, mesi), testo)
        if dd:
            ini, fin = d(dd.group(1), dd.group(2), dd.group(3) or dd.group(6)), d(dd.group(4), dd.group(5), dd.group(6))
        else:
            dd = re.search(r"(?i)\bdal\s+(\d{1,2})\s+al\s+(\d{1,2})\s+(%s)\s+(\d{4})" % mesi, testo)
            if not dd: continue
            ini, fin = d(dd.group(1), dd.group(3), dd.group(4)), d(dd.group(2), dd.group(3), dd.group(4))
        trovate.append(f"{ini}→{fin} {tit}")
        if not tit or fin < OGGI or ini > LIMITE or ini > fin: continue
        tit = tit.title() if tit.isupper() else tit
        tt = tok(tit)
        if any(x["sede"] == "Galleria Wikiarte" and x["inizio"] == ini for x in mo) or \
           any((len(tt & tok(x["titolo"])) / max(1, min(len(tt), len(tok(x["titolo"])))) >= 0.6) for x in mo if tok(x["titolo"])):
            continue
        desc = og("description")
        desc = " ".join(re.split(r"(?<=[.!?])\s", desc)[0].split()[:25]).rstrip(" …[") if desc else ""
        cat = next((v for rx, v in CAT if re.search(rx, (tit + " " + desc).lower())), "Arte contemporanea e installazioni")
        mo.append({"id": "", "titolo": f"{tit}. Mostre personali", "sede": "Galleria Wikiarte", "citta": "Bologna", "inizio": ini, "fine": fin,
                   "categoria": cat, "descrizione": desc or "Mostre personali alla Galleria Wikiarte, Galleria Falcone e Borsellino 2/D.",
                   "ingresso": "gratuito", "orari": "mar–sab 15–18", "fonte": u, "sito": "https://www.wikiarte.com/", "biglietti": "", "biglietti_tipo": ""})
        R["aggiunti"].append(f"mostra {ini}→{fin} {tit} – Galleria Wikiarte"); n += 1
    R["fonti"]["wikiarte"] = {"letti": letti, "aggiunti": n, "trovate": trovate}


# ---------- calendari dei locali sul loro sito (dal 14/11/2026, richiesta di Stefano) ----------
# DICE dà a GitHub solo la prima pagina per città (circa 70 eventi): i locali con molte date restano scoperti.
# Per questi si legge il calendario sul sito del locale (elenco → pagina di ogni evento: data, ora, link d'acquisto).
LOCALI_SITO = {"bo": [("Locomotiv Club", "https://www.locomotivclub.it", "/eventtype/calendario/")]}
MESI_IT = {m: i for i, m in enumerate("gennaio febbraio marzo aprile maggio giugno luglio agosto settembre ottobre novembre dicembre".split(), 1)}


def locali_sito():
    import urllib.robotparser
    for nome, sito, cal in LOCALI_SITO.get(CITTA, []):
        rp = urllib.robotparser.RobotFileParser(); rp.parse((get(sito + "/robots.txt", tent=1) or "").splitlines())
        if not rp.can_fetch("*", sito + cal):
            R["fonti"][nome] = {"letti": 0, "aggiunti": 0, "nota": "robots.txt vieta"}; continue
        links = []
        for p in range(1, 15):
            h = get(sito + cal + ("" if p == 1 else f"page/{p}/"), tent=1)
            if not h: break
            nuovi = [u for u in re.findall(r'href="(%s/event/[^"#?]+/)"' % re.escape(sito), h) if u not in links]
            if not nuovi: break
            links += nuovi; time.sleep(1.5)
        letti = n = 0; ultima = ""
        for u in links:
            time.sleep(1.5)
            h = get(u, tent=1)
            if not h: continue
            letti += 1
            testo = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", re.sub(r"(?s)<script.*?</script>|<style.*?</style>", " ", h))))
            m = re.search(r"(?i)Data:\s*(?:Data:\s*)?(\d{1,2})\s+(%s)\s+(\d{4})" % "|".join(MESI_IT), testo)
            if not m: continue
            d = f"{int(m.group(3)):04d}-{MESI_IT[m.group(2).lower()]:02d}-{int(m.group(1)):02d}"
            ultima = max(ultima, d)
            if d < OGGI or d > LIMITE: continue
            ora = "n.d."
            mo = re.search(r"(?i)Inizio ore:?\s*(\d{1,2})[:.](\d{2})\s*(am|pm)?", testo) or re.search(r"(?i)Ora:\s*(?:Ora:\s*)?(\d{1,2})[:.](\d{2})\s*(am|pm)?", testo)
            if mo:
                hh = int(mo.group(1)) % 12 + (12 if (mo.group(3) or "").lower() == "pm" else 0) if mo.group(3) else int(mo.group(1))
                ora = f"{hh:02d}:{mo.group(2)}"
            tit = html.unescape((re.search(r"<title>(.*?)</title>", h, re.S) or [None, ""])[1])
            tit = re.split(r"\s+[–-]\s+%s" % re.escape(nome.split()[0]), tit)[0].strip()
            tit = tit.split(" | ")[0].strip()
            esaurito = bool(re.match(r"(?i)\s*sold\s*out\s*/+\s*", tit))
            tit = re.sub(r"(?i)^\s*sold\s*out\s*/+\s*", "", tit)
            tit = re.sub(r"(?i)\s+[–-]\s+(ingresso|free entry|ingresso libero|up to you).*$", "", tit).strip()
            if not tit: continue
            SIGLE = {"DJ", "MC", "CCCP", "AC/DC", "USA", "UK", "EP", "LP"}
            tit = " ".join(w.capitalize() if w.isupper() and len(re.sub(r"\W", "", w)) > 2 and w not in SIGLE else w for w in tit.split())
            # link d'acquisto: il primo dopo «Acquista biglietto» che non sia la tessera del circolo
            bl = ""
            ia = h.find("Acquista biglietto")
            if ia > 0:
                for x in re.findall(r'href="(https://[^"]+)"', h[ia:ia + 4000]):
                    x = html.unescape(x)
                    if re.search(r"locomotivclub\.it|portal\.|facebook|fb\.me|instagram|awin1\.com", x): continue
                    bl = re.sub(r"[?&](fbclid|utm_[a-z]+)=[^&]*", "", x).rstrip("?&"); break
            low = tit.lower()
            if re.search(r"stand[- ]?up|comedy|comic", low): g, t = "Teatro", "Comicità"
            elif re.search(r"balera|party|\bdj\b|disco|dance|night", low) or ora >= "23:00": g, t = "Serate e club", "Serata"
            else: g = genere_mb(tit) or "Pop e altra musica"; t = TIPO_G[g]
            x = nuovo(tit, d, d, ora, luogo_guida(nome), "Bologna" if CITTA == "bo" else CFG["nome"], g, t, bl,
                      "sold out" if esaurito else "disponibile" if bl else "da verificare", u)
            det = testo.split("Dettagli", 1)[1] if "Dettagli" in testo else ""
            frase = re.split(r"(?<=[.!?])\s", det.strip())[0] if det.strip() else ""
            if 30 <= len(frase) <= 260: x["descrizione"] = " ".join(frase.split()[:25]).rstrip(",;:") + ("" if frase.rstrip().endswith((".", "!", "?")) else "…")
            n += aggiungi(x, nome)
        R["fonti"][nome] = {"letti": letti, "aggiunti": n, "pagine_evento": len(links), "ultima_data": ultima}


for f in (dice, ticketmaster, arte, wikiarte, locali_sito):
    try: f()
    except Exception as ex: R["errori"].append(f"{f.__name__}: {type(ex).__name__}: {ex}")

# ---------- convalida e scrittura ----------
os.makedirs(os.path.join(RADICE, "dati"), exist_ok=True)
tmp_e, tmp_m = f"/tmp/auto_{CITTA}_eventi.json", f"/tmp/auto_{CITTA}_mostre.json"
json.dump(ev, open(tmp_e, "w"), ensure_ascii=False)
json.dump(mo, open(tmp_m, "w"), ensure_ascii=False)
cc = ["--citta", "mi"] if CITTA == "mi" else []
ok = True
if not PROVA:
    os.chdir("/tmp")  # aggiorna.py scrive i suoi .json di servizio nella cartella corrente
    for args in ([tmp_e, "--out", os.path.join(RADICE, CFG["eventi"])], [tmp_m, "--mostre", "--out", os.path.join(RADICE, CFG["mostre"])]):
        p = subprocess.run([sys.executable, os.path.join(QUI, "aggiorna.py")] + args + cc, capture_output=True, text=True)
        print(p.stdout[-1500:])
        if p.returncode: ok = False; R["errori"].append("convalida: " + p.stdout[-600:])
    os.chdir(RADICE)
    if GEN_NUOVI[0]: json.dump(GEN, open(GFILE, "w"), ensure_ascii=False, indent=1)
R["data"] = datetime.datetime.now().isoformat(timespec="minutes")
R["eventi_totali"], R["mostre_totali"] = len(ev), len([m for m in mo if m["fine"] >= OGGI])
json.dump(R, open(os.path.join(RADICE, "dati", f"auto_{CITTA}.json"), "w"), ensure_ascii=False, indent=1)
print(json.dumps({k: R[k] for k in ("fonti", "link_biglietti", "errori")}, ensure_ascii=False, indent=1))
print(f"aggiunti {len(R['aggiunti'])}:"); [print("  +", a) for a in R["aggiunti"]]
sys.exit(0 if ok else 1)
