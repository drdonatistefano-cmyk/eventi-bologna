"""Scheda «Incontri»: presentazioni di libri, incontri, conferenze e visite guidate (gira su GitHub Actions, senza Claude).
uso: python3 scripts/incontri_auto.py bo|mi [--prova]

Fonti (tutte lette nel rispetto dei robots.txt, una pagina al secondo):
  Bologna - culturabologna.it, agenda del Comune: categorie «incontri» e «visite-guidate».
            Di ogni appuntamento nuovo legge la scheda una volta sola (comune e ingresso gratuito),
            poi la tiene in dati/incontri_schede.json e non la richiede più.
  Milano  - Casa della Cultura (appuntamenti dei prossimi giorni in prima pagina)
          - BookCity Milano (novembre): programma giorno per giorno, senza gli eventi fuori provincia e riservati alle classi
          - Fondazione Feltrinelli (calendario eventi: solo quelli in Viale Pasubio / in Fondazione)
Il file viene riscritto da zero a ogni giro con i prossimi 45 giorni (gli incontri passano in fretta);
se una fonte non risponde, restano quelli della volta prima per quella fonte.
Scrive incontri.js (Bologna) o milano/incontri.js e il riepilogo dati/incontri_<città>.json.
Generi: «Libri» (presentazioni, letture, gruppi di lettura), «Incontri e conferenze», «Visite guidate».
Ingresso nel campo disp: «gratuito», «a pagamento» oppure vuoto (da verificare)."""
import json, re, sys, os, time, datetime, html, urllib.request

QUI = os.path.dirname(os.path.abspath(__file__))
RADICE = os.path.dirname(QUI)
CITTA = sys.argv[1] if len(sys.argv) > 1 else "bo"
PROVA = "--prova" in sys.argv
sys.argv = [sys.argv[0]] + (["--citta", "mi"] if CITTA == "mi" else [])
sys.path.insert(0, QUI)
import aggiorna as A  # elenco dei comuni della città

FILE = {"bo": "incontri.js", "mi": "milano/incontri.js"}[CITTA]
CAPO = {"bo": "Bologna", "mi": "Milano"}[CITTA]
UA = "Mozilla/5.0 (compatible; AchEventsGuide/1.0; +https://achevents.com)"
OGGI = datetime.date.today()
FINE = OGGI + datetime.timedelta(days=45)
MESI = {m: i + 1 for i, m in enumerate("gennaio febbraio marzo aprile maggio giugno luglio agosto settembre ottobre novembre dicembre".split())}
MESI.update({m[:3]: v for m, v in list(MESI.items())})
COMUNI = sorted(set(A.COMUNE), key=len, reverse=True)
R = {"fonti": {}, "errori": [], "per_genere": {}}
_ult = [0.0]


def get(u, tent=3):
    for i in range(tent):
        try:
            att = 1.0 - (time.time() - _ult[0])
            if att > 0: time.sleep(att)
            _ult[0] = time.time()
            r = urllib.request.Request(u, headers={"User-Agent": UA, "Accept-Language": "it-IT,it;q=0.9"})
            return urllib.request.urlopen(r, timeout=30).read().decode("utf-8", "ignore")
        except Exception as ex:
            if getattr(ex, "code", 0) == 404: return None
            if i == tent - 1:
                R["errori"].append(f"{u[:90]}: {ex}")
                return None
            time.sleep(3 * (i + 1))


def testo(h):
    h = re.sub(r"(?is)<(script|style|noscript)\b.*?</\1>", " ", h or "")
    h = re.sub(r"(?i)<br\s*/?>|</(p|div|li|h\d|tr|td)>", "\n", h)
    t = html.unescape(re.sub(r"<[^>]+>", " ", h)).replace("\xa0", " ")
    return "\n".join(x for x in (re.sub(r"[ \t]+", " ", r).strip() for r in t.split("\n")) if x)


def pulito(s, n=0):
    s = re.sub(r"\s+", " ", html.unescape(s or "")).strip(" -–|·")
    if n and len(s) > n: s = s[:n].rsplit(" ", 1)[0].rstrip(",;:.") + "…"
    return s


def gma(g, m, a):
    try: return datetime.date(int(a), MESI[m.lower()[:3]] if m.lower() not in MESI else MESI[m.lower()], int(g))
    except Exception: return None


def leggi_data(s):
    """«10 novembre 2026, 17:00» / «11 novembre 2026, dalle 15:30 alle 18:30» / «dal 9 al 15 novembre 2026» / «dal 11 apr al 19 dic 2026»"""
    s = pulito(s).lower()
    ora = ""
    m = re.search(r"(\d{1,2})[:.](\d{2})", s)
    if m: ora = f"{int(m.group(1)):02d}:{m.group(2)}"
    m = re.match(r"dal (\d{1,2})(?: ([a-z]+))?(?: (\d{4}))? al (\d{1,2}) ([a-z]+) (\d{4})", s)
    if m:
        b = gma(m.group(4), m.group(5), m.group(6))
        a = gma(m.group(1), m.group(2) or m.group(5), m.group(3) or m.group(6))
        return (a, b, ora) if a and b else (None, None, "")
    m = re.match(r"(\d{1,2}) ([a-z]+) (\d{4})", s)
    if m:
        d = gma(*m.groups())
        return d, d, ora
    return None, None, ""


def genere(cat, titolo, sotto, luogo, extra=""):
    t = " ".join([titolo, sotto, extra]).lower()
    if "visite-guidate" in cat or re.search(r"\bvisit[ae] guidat", t): return "Visite guidate"
    if re.search(r"presentazione (del|di|dell'|della|dei|delle|in anteprima)? ?(nuovo |suo |ultimo )?(libro|volume|romanzo|saggio|raccolta|graphic novel|fumetto|antologia|meridiano)|"
                 r"presenta (il|la) (suo |sua |nuovo |nuova )?(libro|romanzo|saggio|raccolta)|\b(libro|romanzo|saggio) di\b|reading|letture? (ad alta voce|animat)|"
                 r"gruppo di lettura|\bgdl\b|scrittor[ei]|scrittrice|poesi[ae]|poet[ai]|bookcity|\(\s*[a-z]+ ?editore", t) \
            or re.search(r"librer|libreria|book ?shop|bookstore", luogo.lower()):
        return "Libri"
    return "Incontri e conferenze"


def ingresso(t):
    t = (t or "").lower()
    if re.search(r"evento gratuito|ingresso (libero|gratuito)|ingresso a offerta libera|partecipazione (libera|gratuita)|gratuit[oa] (con|su|previa)", t): return "gratuito"
    if re.search(r"evento a pagamento|biglietto|€\s*\d|\d+([.,]\d+)?\s*(€|euro)\b|a pagamento", t): return "a pagamento"
    return ""


def comune_da(t):
    m = re.search(r"\b\d{5}\s+([A-ZÀ-Ü][\w'À-ü ]+?)(?:\s*\(|\n|$)", t or "")
    cand = [m.group(1).strip()] if m else []
    for c in cand:
        for x in COMUNI:
            if A.norm(x) == A.norm(c): return x
    return ""


def maiuscole(t):
    """«NAZIONALISMO E INTERNAZIONALISMO. Ragioni…» → «Nazionalismo e internazionalismo. Ragioni…»"""
    parti = re.split(r"(\.\s+|\s+[-–]\s+)", t)
    return "".join(x[:1].upper() + x[1:].lower() if x.isupper() and len(x) > 3 else x for x in parti)


def voce(fonte, data, fino, ora, titolo, luogo, citta, gen, descr, url, disp):
    return {"data": data.isoformat(), "fino": fino.isoformat(), "ora": ora, "artista": pulito(titolo, 140), "luogo": pulito(luogo, 90),
            "citta": citta or CAPO, "genere": gen, "tipo": "", "rassegna": "", "descrizione": pulito(descr, 230),
            "fonte": url, "biglietti": "", "biglietti_tipo": "", "disp": disp, "sito_luogo": "", "_f": fonte}


# ---------------- Bologna: culturabologna.it ----------------
CB = "https://www.culturabologna.it"
SCHEDE = os.path.join(RADICE, "dati", "incontri_schede.json")


def cb_carte(h):
    for c in re.findall(r'(?s)<a class="link link--block.*?</a>', h or ""):
        g = lambda rx: (re.search(rx, c, re.S) or [None, ""])[1]
        yield {"href": html.unescape(g(r'href="([^"]+)"')), "titolo": html.unescape(g(r'title="([^"]*)"')),
               "data": g(r'date-label"><span>\s*(.*?)\s*</span>'), "cat": g(r'title-category f-4 clamp-3 (.*?) title"'),
               "luogo": pulito(re.sub(r"<[^>]+>", " ", g(r"location-label\">(.*?)</div>"))).lstrip("@ "),
               "sotto": pulito(re.sub(r"<[^>]+>", " ", g(r'class="clamp-5 description">(.*?)</div>')))}


def bologna():
    schede = json.load(open(SCHEDE, encoding="utf-8")) if os.path.exists(SCHEDE) else {}
    visti, out = set(), []
    for cat, maxp in (("incontri", 16), ("visite-guidate", 6)):
        n = 0
        for p in range(1, maxp + 1):
            h = get(f"{CB}/agenda?categories%5B%5D={cat}" + (f"&page={p}" if p > 1 else ""))
            carte = list(cb_carte(h))
            if not carte: break
            oltre = 0
            for c in carte:
                a, b, ora = leggi_data(c["data"])
                if not a or not c["href"].startswith("/objects/"): continue
                if a > FINE: oltre += 1; continue
                if b < OGGI or (b - a).days > 10 or c["href"] in visti: continue
                if re.search(r"\bmostre\b", c["cat"]) and "visite-guidate" not in c["cat"]: continue
                visti.add(c["href"]); n += 1
                url = CB + c["href"]
                sc = schede.get(c["href"])
                if sc is None:
                    t = testo(get(url) or "")
                    dove = t.split("\nDove\n", 1)[1][:300] if "\nDove\n" in t else ""
                    corpo = t.split("\nDove\n", 1)[1] if "\nDove\n" in t else t
                    corpo = corpo.split("Contenuto inserito il")[0]
                    righe = [r for r in corpo.split("\n")[2:] if len(r) > 40]
                    sc = {"comune": comune_da(dove), "ingresso": ingresso(t), "testo": pulito(" ".join(righe), 400), "visto": OGGI.isoformat()}
                    if t: schede[c["href"]] = sc
                luogo = re.split(r"\s+\|\s+", c["luogo"])[0]
                if re.search(r"(?i)^(bologna[,\s-]*)?luoghi vari$", luogo): luogo = "Luoghi vari"
                if re.search(r"(?i)^punto di ritrovo:\s*", luogo): luogo = re.sub(r"(?i)^punto di ritrovo:\s*", "", luogo)
                st_ = sc.get("testo", "")
                if not st_ or len(c["sotto"]) >= 30: descr = c["sotto"] or st_
                elif A.norm(c["sotto"]) and A.norm(c["sotto"]) in A.norm(st_[:len(c["sotto"]) + 60]): descr = st_
                else: descr = (c["sotto"] + ". " if c["sotto"] else "") + st_
                g = genere(c["cat"], c["titolo"], c["sotto"], luogo, sc.get("testo", "")[:300])
                out.append(voce("culturabologna", max(a, OGGI) if b > a else a, b, ora, c["titolo"], luogo, sc.get("comune") or "Bologna", g, descr, url, sc.get("ingresso", "")))
            if oltre and oltre == len(carte): break
        R["fonti"][f"culturabologna/{cat}"] = n
    # tiene le schede degli ultimi 90 giorni
    lim = (OGGI - datetime.timedelta(days=90)).isoformat()
    schede = {k: v for k, v in schede.items() if v.get("visto", "") >= lim}
    if not PROVA:
        json.dump(schede, open(SCHEDE, "w", encoding="utf-8"), ensure_ascii=False, indent=0, sort_keys=True)
    return out


# ---------------- Milano ----------------
GIORNI = r"(?:luned[iì]|marted[iì]|mercoled[iì]|gioved[iì]|venerd[iì]|sabato|domenica)"


def casa_cultura():
    base = "https://www.casadellacultura.it/"
    h = get(base)
    out = []
    if not h: return out
    i = h.find("APPUNTAMENTI")
    blocco = h[i:] if i > 0 else h
    pezzi = re.split(r'<span class="data">', blocco)
    cur = None
    for p in pezzi[1:]:
        dt = pulito(re.sub(r"<[^>]+>", " ", p.split("</span>")[0]))
        m = re.match(GIORNI + r"\s+(\d{1,2}) ([a-z]+) (\d{4})(?: ore (\d{1,2})[.:](\d{2}))?", html.unescape(dt).lower())
        if m:
            d = gma(m.group(1), m.group(2), m.group(3))
            ora = f"{int(m.group(4)):02d}:{m.group(5)}" if m.group(4) else ""
            spans = [pulito(re.sub(r"<[^>]+>", " ", x)) for x in re.findall(r'class="(?:robotosx|roboto12left)">(.*?)(?:</span>|<span|<br)', p, re.S)]
            spans = [s for s in spans if s]
            cur = {"d": d, "ora": ora, "titolo": spans[0] if spans else "", "sotto": " · ".join(spans[1:3]), "p": p}
            continue
        if cur:
            idm = re.search(r"incontri-testo\.php\?id=(\d+)", p)
            url = base + f"casa-della-cultura-incontri-testo.php?id={idm.group(1)}" if idm else base
            d = cur["d"]
            if d and OGGI <= d <= FINE and cur["titolo"]:
                t = maiuscole(cur["titolo"])
                out.append(voce("casadellacultura", d, d, cur["ora"], t, "Casa della Cultura", "Milano",
                                genere("", cur["titolo"], cur["sotto"], "Casa della Cultura"), cur["sotto"], url, ""))
            cur = None
    R["fonti"]["casadellacultura"] = len(out)
    return out


def feltrinelli():
    out = []
    for u in ("https://fondazionefeltrinelli.it/eventi/", "https://fondazionefeltrinelli.it/eventi/page/2/"):
        h = get(u)
        if not h: continue
        pos = [(m.start(), m.group(0)) for m in re.finditer(r"\b\d{2}/\d{2}/\d{4}\b", h)]
        for k, (s, ds) in enumerate(pos):
            seg = h[s:pos[k + 1][0] if k + 1 < len(pos) else s + 4000]
            prima = h[max(0, s - 2500):s]
            t = testo(seg).replace("\\", " ")
            testa = "\n".join(t.split("\n")[:6])
            if not re.search(r"(?i)viale pasubio|in fondazione( giangiacomo)? feltrinelli", testa): continue
            if re.search(r"\b(Roma|Mantova|Pavia|Varese|Bergamo|Torino|Bologna|Napoli|Firenze|Brescia|Como|Venezia)\b", testa): continue
            g, mm, a = ds.split("/")
            try: d = datetime.date(int(a), int(mm), int(g))
            except Exception: continue
            if not (OGGI <= d <= FINE): continue
            righe = t.split("\n")[1:]
            titolo = righe[0] if righe else ""
            sotto = " ".join(r for r in righe[1:3] if not re.search(r"(?i)pasubio|in fondazione", r))
            om = re.search(r"\b(?:h\.?|ore)\s*(\d{1,2})[.:](\d{2})", t)
            links = re.findall(r'href="(https://fondazionefeltrinelli\.it/[^"#?]+)"', prima + seg)
            links = [x for x in links if not re.search(r"/(eventi|category|tag|calendario|page)/?", x[len("https://fondazionefeltrinelli.it"):])]
            url = links[-1] if links else u
            if not titolo: continue
            out.append(voce("feltrinelli", d, d, f"{int(om.group(1)):02d}:{om.group(2)}" if om else "", titolo, "Fondazione Feltrinelli", "Milano",
                            genere("", titolo, sotto, "Fondazione Feltrinelli"), sotto, url, ingresso(t)))
    vis, uniq = set(), []
    for v in out:
        k = (v["data"], v["artista"])
        if k not in vis: vis.add(k); uniq.append(v)
    R["fonti"]["feltrinelli"] = len(uniq)
    return uniq


BC = "https://www.bookcitymilano.it"
FUORI = r"(?i)^(cremona|lodi|como|monza|pavia|sondrio|varese|bergamo|brescia|lecco|mantova)\b"


def bookcity():
    """BookCity Milano (festival del libro, novembre): una pagina per giorno, /eventi?day=24-novembre."""
    out = []
    h = get(BC + "/eventi")
    giorni = list(dict.fromkeys(re.findall(r'class="event_date[^"]*" data-value="(\d{1,2}-[a-z]+)"', h or "")))
    anno = OGGI.year if OGGI.month <= 11 or "dicembre" in " ".join(giorni) else OGGI.year + 1
    cl = lambda x: pulito(re.sub(r"<[^>]+>", " ", x or ""))
    for gv in giorni:
        g, m = gv.split("-", 1)
        d = gma(g, m, anno)
        if not d or not (OGGI <= d <= FINE): continue
        hd = get(f"{BC}/eventi?day={gv}") or ""
        for b in re.split(r'<div class="row align-middle event-box', hd)[1:]:
            f = lambda rx: (re.search(rx, b, re.S) or [None, ""])[1]
            titolo, luogo = cl(f(r"<h3>(.*?)</h3>")), cl(f(r"<address>(.*?)</address>"))
            url = f(r'<h3>\s*<a href="([^"]+)"')
            tags = [cl(x) for x in re.findall(r'class="tag"[^>]*>(.*?)</a>', b, re.S)]
            if not titolo or not luogo or not url.startswith("https://"): continue
            if re.search(r"(?i)riservat[oa]|solo su invito|posti esauriti", titolo): continue
            if re.search(r"(?i)penitenziari|carcere|casa circondariale|policlinico|ospedale|reparti", luogo + " " + titolo): continue
            if re.search(FUORI, luogo) or any(t.startswith("BookCity Milano a ") for t in tags): continue
            citta = "Milano"
            mm = re.match(r"^([^-–]+?)\s+[-–]\s+(.+)$", luogo)
            if mm:
                c = [x for x in COMUNI if A.norm(x) == A.norm(mm.group(1))]
                if c: citta, luogo = c[0], mm.group(2)
            om = re.search(r"(\d{1,2})[:.](\d{2})", cl(f(r'date-time-hour">(.*?)<')))
            sotto = cl(f(r"</h3>\s*<p>(.*?)</p>"))
            descr = " · ".join(x for x in [sotto, ", ".join(t for t in tags[:2] if t not in ("Biblioteche",))] if x)
            v = voce("bookcity", d, d, f"{int(om.group(1)):02d}:{om.group(2)}" if om else "", titolo, luogo, citta, "Libri", descr, url, "")
            v["rassegna"] = "BookCity Milano"
            out.append(v)
    R["fonti"]["bookcity"] = len(out)
    return out


# ---------------- scrittura ----------------
def leggi_vecchio():
    p = os.path.join(RADICE, FILE)
    if not os.path.exists(p): return []
    s = open(p, encoding="utf-8").read()
    try: return json.loads(s[s.index("=") + 1:].rstrip().rstrip(";"))["incontri"]
    except Exception: return []


def main():
    nuovi = bologna() if CITTA == "bo" else casa_cultura() + feltrinelli() + bookcity()
    vecchi = leggi_vecchio()
    # fonte che stavolta non ha dato nulla: tiene i suoi incontri ancora futuri
    fonti_ok = {v["_f"] for v in nuovi}
    for v in vecchi:
        if v.get("_f") and v["_f"] not in fonti_ok and v.get("fino", v["data"]) >= OGGI.isoformat():
            nuovi.append(v)
    ok, doppi = [], set()
    for v in nuovi:
        k = (v["data"], v["ora"], A.norm(v["artista"]))
        if k in doppi: continue
        doppi.add(k)
        if not (re.match(r"^\d{4}-\d{2}-\d{2}$", v["data"]) and v["artista"] and v["luogo"] and v["fonte"].startswith("https://")): continue
        ok.append(v)
    ok.sort(key=lambda v: (v["data"], v["ora"] or "99", v["artista"]))
    for i, v in enumerate(ok): v["id"] = f"i{i + 1:03d}"
    for v in ok: R["per_genere"][v["genere"]] = R["per_genere"].get(v["genere"], 0) + 1
    R["totale"] = len(ok); R["gratuiti"] = sum(v["disp"] == "gratuito" for v in ok); R["giorno"] = OGGI.isoformat()
    print(json.dumps(R, ensure_ascii=False, indent=1))
    if PROVA:
        for v in ok[:40]: print(v["data"], v["ora"], v["genere"][:8], v["disp"][:4], "|", v["artista"][:50], "|", v["luogo"][:30], v["citta"], "|", v["descrizione"][:60])
        return
    if not ok:
        print("nessun incontro: file lasciato com'era"); sys.exit(1)
    dati = {"aggiornato": OGGI.isoformat(), "incontri": [{k: v[k] for k in ["id"] + [x for x in v if x != "id"]} for v in ok]}
    open(os.path.join(RADICE, FILE), "w", encoding="utf-8").write("window.INCONTRI_DATA=" + json.dumps(dati, ensure_ascii=False, separators=(",", ":")) + ";\n")
    json.dump(R, open(os.path.join(RADICE, "dati", f"incontri_{CITTA}.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
