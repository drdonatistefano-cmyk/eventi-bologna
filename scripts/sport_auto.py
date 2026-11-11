"""Scheda «Sport»: le partite in casa delle squadre di Bologna e Milano (gira su GitHub Actions, senza Claude).
uso: python3 scripts/sport_auto.py bo|mi [--prova]

Fonti (dati pubblici, letti una volta per giro):
  Calcio  - Serie A: openfootball/football.json su GitHub (calendario con orari quando la Lega li fissa)
          - coppe europee: API pubblica UEFA (match.uefa.com) per Champions, Europa e Conference League
  Basket  - Serie A: API del sito legabasket.it (calendario per squadra, con link ai biglietti Vivaticket)
          - EuroLeague: API pubblica api-live.euroleague.net
          - Serie A2: calendario sul sito della Fortitudo (fortitudobologna.it/calendario)
  Volley  - SuperLega maschile: calendario di legavolley.it (andata e ritorno)
          - Serie A1/A2 femminile: calendario di legavolleyfemminile.it
Altro   - dati/sport_extra.json: eventi singoli scritti a mano (tennis: Coppa Davis; finali e tornei), campo "guida" bo|mi.
Prende solo le partite in casa da oggi a 12 mesi. Se una fonte non risponde, restano le sue partite della volta prima.
Scrive sport.js (Bologna) o milano/sport.js (window.SPORT_DATA, stesso formato degli eventi) e dati/sport_<città>.json.
Campi: genere = Calcio | Basket | Volley; tipo = competizione; rassegna = squadra di casa."""
import json, re, sys, os, time, datetime, html, urllib.request

QUI = os.path.dirname(os.path.abspath(__file__))
RADICE = os.path.dirname(QUI)
CITTA = sys.argv[1] if len(sys.argv) > 1 else "bo"
PROVA = "--prova" in sys.argv
FILE = {"bo": "sport.js", "mi": "milano/sport.js"}[CITTA]
UA = "Mozilla/5.0 (compatible; AchEventsGuide/1.0; +https://achevents.com)"
OGGI = datetime.date.today()
FINE = OGGI + datetime.timedelta(days=366)
R = {"fonti": {}, "errori": [], "per_sport": {}}
_ult = [0.0]

# squadre seguite: nomi come compaiono nelle fonti
SQUADRE = {
    "bo": [
        {"nome": "Bologna FC", "sport": "Calcio", "of": "Bologna FC 1909", "uefa": "Bologna",
         "stadio": "Stadio Renato Dall'Ara", "citta": "Bologna", "sito": "https://www.bolognafc.it/", "biglietti": "https://www.bolognafc.it/biglietti/"},
        {"nome": "Virtus Bologna", "sport": "Basket", "lba": 1750, "el": "VIR", "sito": "https://www.virtus.it/"},
        {"nome": "Fortitudo Bologna", "sport": "Basket", "fortitudo": True, "sito": "https://fortitudobologna.it/", "biglietti": "https://fortitudobologna.vivaticket.it/"},
        {"nome": "Clai Imola Volley", "sport": "Volley", "lvf": "Clai Imola Volley", "sito": "https://www.imolavolley.it/"},
    ],
    "mi": [
        {"nome": "Inter", "sport": "Calcio", "of": "FC Internazionale Milano", "uefa": "Inter",
         "stadio": "Stadio San Siro", "citta": "Milano", "sito": "https://www.inter.it/", "biglietti": "https://www.inter.it/it/biglietti"},
        {"nome": "Milan", "sport": "Calcio", "of": "AC Milan", "uefa": "Milan",
         "stadio": "Stadio San Siro", "citta": "Milano", "sito": "https://www.acmilan.com/", "biglietti": "https://www.acmilan.com/it/biglietti"},
        {"nome": "Olimpia Milano", "sport": "Basket", "lba": 1751, "el": "MIL", "sito": "https://www.olimpiamilano.com/"},
        {"nome": "Allianz Milano", "sport": "Volley", "lvm": "Allianz Milano", "sito": "https://www.powervolleymilano.it/"},
        {"nome": "Vero Volley Milano", "sport": "Volley", "lvf": "Numia Vero Volley Milano", "sito": "https://www.verovolley.com/",
         "biglietti": "https://www.verovolley.com/biglietteria/"},
    ],
}[CITTA]

# nomi degli impianti come li scrivono le fonti → nome e comune per la guida
IMPIANTI = {
    "PALADOZZA": ("PalaDozza", "Bologna"), "VIRTUS ARENA": ("Virtus Arena", "Bologna"),
    "UNIPOL FORUM": ("Unipol Forum", "Assago"), "ALLIANZ CLOUD": ("Allianz Cloud", "Milano"),
    "SEGAFREDO ARENA": ("Virtus Arena", "Bologna"), "PALARUGGI": ("PalaRuggi", "Imola"), "PALA RUGGI": ("PalaRuggi", "Imola"),
}
MESI = {m: i + 1 for i, m in enumerate("gennaio febbraio marzo aprile maggio giugno luglio agosto settembre ottobre novembre dicembre".split())}
GIORNATA = lambda n: f"{n}ª giornata" if n else ""


def get(u, tent=3, js=False):
    for i in range(tent):
        try:
            att = 1.0 - (time.time() - _ult[0])
            if att > 0: time.sleep(att)
            _ult[0] = time.time()
            r = urllib.request.Request(u, headers={"User-Agent": UA, "Accept-Language": "it-IT,it;q=0.9", "Accept": "application/json" if js else "text/html,*/*"})
            t = urllib.request.urlopen(r, timeout=40).read().decode("utf-8", "ignore")
            return json.loads(t) if js else t
        except Exception as ex:
            if i == tent - 1:
                R["errori"].append(f"{u[:90]}: {ex}")
                return None
            time.sleep(3 * (i + 1))


def norm(s): return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def impianto(nome, comune=""):
    k = re.sub(r"\s*\(.*?\)\s*", " ", nome or "").strip().upper()
    for a, v in IMPIANTI.items():
        if k.startswith(a): return v
    n = " ".join(w if w.isupper() and len(w) <= 4 else w.capitalize() if w.isupper() else w for w in re.sub(r"\s+", " ", nome or "").split())
    return n, comune


def partita(fonte, sq, d, ora, casa, ospite, luogo, citta, comp, descr, url, big=""):
    return {"data": d.isoformat(), "fino": d.isoformat(), "ora": ora or "", "artista": f"{casa} – {ospite}", "luogo": luogo, "citta": citta,
            "genere": sq["sport"], "tipo": comp, "rassegna": sq["nome"], "descrizione": descr, "fonte": url or sq["sito"],
            "biglietti": big or sq.get("biglietti", ""), "biglietti_tipo": "Acquista" if (big or sq.get("biglietti")) else "",
            "disp": "", "sito_luogo": sq["sito"], "_f": fonte}


def dentro(d): return d and OGGI <= d <= FINE


# ---------------- calcio ----------------
NOMI_BREVI = {"FC Internazionale Milano": "Inter", "AC Milan": "Milan", "Bologna FC 1909": "Bologna", "Juventus FC": "Juventus", "SS Lazio": "Lazio",
              "AS Roma": "Roma", "SSC Napoli": "Napoli", "ACF Fiorentina": "Fiorentina", "Atalanta BC": "Atalanta", "Torino FC": "Torino", "Genoa CFC": "Genoa",
              "Udinese Calcio": "Udinese", "US Lecce": "Lecce", "Cagliari Calcio": "Cagliari", "Hellas Verona FC": "Verona", "Parma Calcio 1913": "Parma",
              "Como 1907": "Como", "US Sassuolo Calcio": "Sassuolo", "AC Monza": "Monza", "Venezia FC": "Venezia", "Frosinone Calcio": "Frosinone",
              "US Cremonese": "Cremonese", "AC Pisa 1909": "Pisa", "Empoli FC": "Empoli", "Palermo FC": "Palermo", "Spezia Calcio": "Spezia"}


def breve(n):
    if n in NOMI_BREVI: return NOMI_BREVI[n]
    return re.sub(r"^(AC|AS|SS|SSC|US|ACF|FC|UC)\s+|\s+(FC|Calcio|BC|CFC|1909|1913|1907)$", "", n).strip()


def serie_a():
    out = []
    anno = OGGI.year if OGGI.month >= 7 else OGGI.year - 1
    for stag in (f"{anno}-{str(anno + 1)[2:]}", f"{anno + 1}-{str(anno + 2)[2:]}"):
        d = get(f"https://raw.githubusercontent.com/openfootball/football.json/master/{stag}/it.1.json", js=True)
        if not d: continue
        for m in d.get("matches", []):
            for sq in SQUADRE:
                if sq.get("of") != m.get("team1"): continue
                try: g = datetime.date.fromisoformat(m["date"])
                except Exception: continue
                if not dentro(g): continue
                n = re.search(r"\d+", m.get("round", ""))
                out.append(partita("seriea", sq, g, m.get("time", ""), breve(m["team1"]), breve(m["team2"]), sq["stadio"], sq["citta"],
                                   "Serie A", f"Serie A, {GIORNATA(n.group(0) if n else '')}." + ("" if m.get("time") else " Orario ancora da fissare."), sq["sito"]))
    R["fonti"]["seriea"] = len(out)
    return out


def uefa():
    out = []
    anno = OGGI.year + (1 if OGGI.month >= 7 else 0)
    nomi = {"1": "Champions League", "14": "Europa League", "2019": "Conference League"}
    for cid, comp in nomi.items():
        for off in range(0, 1200, 200):
            d = get(f"https://match.uefa.com/v5/matches?competitionId={cid}&seasonYear={anno}&limit=200&offset={off}&order=ASC", js=True)
            if not d: break
            for m in d:
                casa = (m.get("homeTeam") or {}).get("internationalName", "")
                for sq in SQUADRE:
                    if not sq.get("uefa") or casa != sq["uefa"]: continue
                    if m.get("status") not in ("UPCOMING", "LIVE"): continue
                    k = (m.get("kickOffTime") or {}).get("dateTime", "")
                    try: dt = datetime.datetime.fromisoformat(k.replace("Z", "+00:00")).astimezone(ROMA)
                    except Exception: continue
                    if not dentro(dt.date()): continue
                    fase = ((m.get("round") or {}).get("translations") or {}).get("name", {}).get("IT") or (m.get("round") or {}).get("metaData", {}).get("name", "")
                    osp = (m.get("awayTeam") or {}).get("translations", {}).get("displayName", {}).get("IT") or (m.get("awayTeam") or {}).get("internationalName", "")
                    st = ((m.get("stadium") or {}).get("translations") or {}).get("name", {})
                    luogo = sq["stadio"] if not st else (sq["stadio"] if "Siro" in (st.get("IT") or st.get("EN") or "") or "Dall" in (st.get("IT") or st.get("EN") or "") else (st.get("IT") or st.get("EN")))
                    ora = "" if (m.get("kickOffTime") or {}).get("dateTimeType") == "DATE" else dt.strftime("%H:%M")
                    url = f"https://it.uefa.com/{ {'1': 'uefachampionsleague', '14': 'uefaeuropaleague', '2019': 'uefaconferenceleague'}[cid] }/match/{m.get('id')}/"
                    out.append(partita("uefa", sq, dt.date(), ora, sq["uefa"], osp, luogo, sq["citta"], comp, f"{comp}" + (f", {fase}." if fase else "."), url))
            if len(d) < 200: break
    R["fonti"]["uefa"] = len(out)
    return out


# ---------------- basket ----------------
def ora_roma(s):
    try:
        dt = datetime.datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo: dt = dt.astimezone(ROMA)
        return dt
    except Exception: return None


def lba():
    out, big = [], {}
    comp = None
    # il campionato in corso si legge dai dati della pagina calendario (campo focus_on della stagione regolare)
    h = get("https://www.legabasket.it/calendario") or ""
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', h, re.S)
    try: lista = json.loads(m.group(1))["props"]["pageProps"]["allCompetitionsBySeriesId"]["competitions"]
    except Exception: lista = []
    att = [c for c in lista if c.get("status") == 1 and c.get("ctype_code") == "RS"] or [c for c in lista if c.get("focus_on")]
    comp = (att or [{"id": 602}])[-1]["id"]
    for sq in SQUADRE:
        if not sq.get("lba"): continue
        d = get(f"https://www.legabasket.it/api/championships/get-championships-calendar-by-id?id={comp}&t_id={sq['lba']}", js=True) or {}
        for m in d.get("matches", []):
            if m.get("h_team_id") != sq["lba"]: continue
            if str(m.get("ticketing_url") or "").startswith("https://"): big.setdefault(sq["nome"], m["ticketing_url"])
            dt = ora_roma(m.get("match_datetime", ""))
            if not dt or not dentro(dt.date()) or str(m.get("game_status")) == "2": continue
            luogo, citta = impianto(m.get("plant_name", ""), m.get("town_name", ""))
            tk = m.get("ticketing_url") or ""
            out.append(partita("lba", sq, dt.date(), dt.strftime("%H:%M"), sq["nome"], m.get("v_team_name", ""), luogo, citta or "",
                               "Serie A basket", f"Serie A di basket, {m.get('day_name', '').lower()}.", f"https://www.legabasket.it/game/{m.get('id')}",
                               tk if tk.startswith("https://") else ""))
    R["fonti"]["lba"] = len(out)
    return out, big


def euroleague(big):
    out = []
    anno = OGGI.year if OGGI.month >= 7 else OGGI.year - 1
    d = get(f"https://api-live.euroleague.net/v2/competitions/E/seasons/E{anno}/games", js=True) or {}
    for m in d.get("data", []):
        loc = ((m.get("local") or {}).get("club") or {})
        for sq in SQUADRE:
            if sq.get("el") != loc.get("code") or m.get("played"): continue
            dt = ora_roma(m.get("utcDate", "")) or ora_roma(m.get("date", ""))
            if not dt or not dentro(dt.date()): continue
            osp = (((m.get("road") or {}).get("club")) or {}).get("name", "")
            luogo, citta = impianto((m.get("venue") or {}).get("name", ""), "")
            if not citta: luogo, citta = luogo or "", "Bologna" if CITTA == "bo" else "Milano"
            ora = dt.strftime("%H:%M") if m.get("confirmedHour", True) else ""
            out.append(partita("euroleague", sq, dt.date(), ora, sq["nome"], osp, luogo, citta, "EuroLeague",
                               f"EuroLeague, {m.get('roundName', '').replace('Round', 'turno')}.",
                               f"https://www.euroleaguebasketball.net/it/euroleague/game-center/{anno}-{anno + 1 - 2000}/{m.get('gameCode')}/", big.get(sq["nome"], "")))
    R["fonti"]["euroleague"] = len(out)
    return out


MESI3 = {m[:3]: i + 1 for i, m in enumerate("gennaio febbraio marzo aprile maggio giugno luglio agosto settembre ottobre novembre dicembre".split())}


def fortitudo():
    """Serie A2: calendario sul sito della Fortitudo (fortitudobologna.it/calendario, robots.txt lo permette)."""
    out = []
    sq = next((s for s in SQUADRE if s.get("fortitudo")), None)
    if not sq: return out
    h = get("https://fortitudobologna.it/calendario") or ""
    for li in re.findall(r'(?s)<li class="grid gap-3 p-5.*?</li>', h):
        testa = re.search(r'(?s)tracking-\[0\.14em\] text-muted-foreground">\s*\w+ (\d{1,2}) (\w{3}) (\d{4})(?:<span[^>]*>(\d{1,2}):(\d{2})</span>)?.*?<div[^>]*>(\d+)ª giornata', li)
        nomi = [cl(x) for x in re.findall(r'line-clamp-1 font-semibold sm:truncate">(.*?)</span>', li)]
        imp = re.search(r'(?s)<p class="mt-1[^"]*">(.*?)</p>', li)
        if not testa or len(nomi) < 2 or not re.search(r"Fortitudo", nomi[0]): continue
        try: d = datetime.date(int(testa.group(3)), MESI3[testa.group(2).lower()], int(testa.group(1)))
        except Exception: continue
        if not dentro(d) or re.search(r">\s*\d+\s*<[^>]*>\s*-\s*<", li): continue
        luogo, citta = impianto(cl(imp.group(1)) if imp else "PalaDozza", "Bologna")
        tk = re.search(r'href="(https://[^"]*vivaticket[^"]*)"', li)
        ora = f"{int(testa.group(4)):02d}:{testa.group(5)}" if testa.group(4) else ""
        out.append(partita("fortitudo", sq, d, ora, sq["nome"], nomi[1], luogo, citta or "Bologna", "Serie A2 basket",
                           f"Serie A2 di basket, {GIORNATA(testa.group(6))}.", "https://fortitudobologna.it/calendario", tk.group(1) if tk else ""))
    R["fonti"]["fortitudo"] = len(out)
    return out


def extra():
    """Eventi singoli (tornei di tennis, finali, grandi eventi) scritti a mano in dati/sport_extra.json."""
    p = os.path.join(RADICE, "dati", "sport_extra.json")
    out = []
    if not os.path.exists(p): return out
    for v in json.load(open(p, encoding="utf-8")).get("eventi", []):
        if v.get("guida") != CITTA: continue
        try: d = datetime.date.fromisoformat(v["data"])
        except Exception: continue
        if not dentro(d): continue
        e = {k: v.get(k, "") for k in ("data", "fino", "ora", "artista", "luogo", "citta", "genere", "tipo", "rassegna", "descrizione", "fonte", "biglietti", "biglietti_tipo", "disp", "sito_luogo")}
        e["fino"] = e["fino"] or e["data"]; e["_f"] = "extra"
        if e["biglietti"] and not e["biglietti_tipo"]: e["biglietti_tipo"] = "Acquista"
        out.append(e)
    R["fonti"]["extra"] = len(out)
    return out


# ---------------- volley ----------------
def cl(x): return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", x or ""))).strip()


def superlega():
    out = []
    sqs = [s for s in SQUADRE if s.get("lvm")]
    if not sqs: return out
    for fase in (1, 2):
        h = get(f"https://www.legavolley.it/calendario/?IdCampionato=999&IdFase={fase}") or ""
        m0 = re.search(r'<option selected value=(\d+)>Regular Season', h)
        giornata, gdata, gora = "", None, ""
        for r in re.findall(r"(?s)<tr.*?</tr>", h[h.find('id="GareGiornata"'):]):
            t = cl(r)
            g = re.match(r"(\d+)ª Giornata \w+ - \w+ (\d{1,2}) ([A-Za-z]+) (\d{4})(?: Ore (\d{1,2}):(\d{2}))?", t)
            if g:
                giornata = g.group(1)
                try: gdata = datetime.date(int(g.group(4)), MESI[g.group(3).lower()], int(g.group(2)))
                except Exception: gdata = None
                gora = f"{int(g.group(5)):02d}:{g.group(6)}" if g.group(5) else ""
                continue
            tds = [cl(x) for x in re.findall(r"(?s)<td.*?</td>", r)]
            if len(tds) < 7 or not tds[0].isdigit(): continue
            for sq in sqs:
                if tds[2] != sq["lvm"]: continue
                m = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})(?: Ore (\d{1,2}):(\d{2}))?", tds[1])
                d = datetime.date(int(m.group(3)), int(m.group(2)), int(m.group(1))) if m else gdata
                ora = f"{int(m.group(4)):02d}:{m.group(5)}" if m and m.group(4) else ("" if m else gora)
                if not dentro(d): continue
                imp = tds[6]
                mm = re.match(r"(.+?)\s+([A-ZÀ-Ü][\w' ]+?)\s+\(([A-Z]{2})\)$", imp)
                luogo, citta = impianto(mm.group(1) if mm else imp, mm.group(2) if mm else "Milano")
                if re.search(r"(?i)allianz cloud", imp): luogo, citta = "Allianz Cloud", "Milano"
                out.append(partita("superlega", sq, d, ora, sq["nome"], tds[4], luogo, citta,
                                   "SuperLega", f"SuperLega di volley maschile, {GIORNATA(giornata)} ({'andata' if fase == 1 else 'ritorno'})." + ("" if m else " Data ufficiale da confermare."),
                                   "https://www.legavolley.it/calendario/"))
    R["fonti"]["superlega"] = len(out)
    return out


def volley_femminile():
    out = []
    sqs = [s for s in SQUADRE if s.get("lvf")]
    if not sqs: return out
    h = get("https://www.legavolleyfemminile.it/calendario/") or ""
    for t in re.findall(r'(?s)<table class="table risultati">.*?</table>', h):
        th = [cl(x) for x in re.findall(r"(?s)<th[^>]*>(.*?)</th>", t)]
        squadre = [cl(x) for x in re.findall(r'(?s)<a href="/club/club/\d+/">(.*?)</a>', t)]
        if len(th) < 5 or len(squadre) < 2: continue
        for sq in sqs:
            if squadre[0] != sq["lvf"]: continue
            try: d = datetime.datetime.strptime(th[1], "%d/%m/%Y").date()
            except Exception: continue
            if not dentro(d): continue
            lega = re.match(r"LVF (A\d)", th[3])
            gm = re.search(r"(\d+)\s*a?\s*Giornata\s*-\s*(Andata|Ritorno)", th[3])
            imp = th[4]
            mm = re.match(r"(.+?)\s+-\s+(.+)$", imp)
            luogo, citta = impianto(mm.group(1) if mm else imp, mm.group(2) if mm else "")
            if citta == "Milano" and re.search(r"(?i)allianz cloud", luogo): luogo = "Allianz Cloud"
            url = re.search(r'href="(https://www\.legavolleyfemminile\.it/match-center/\d+/)"', t)
            comp = f"Serie {lega.group(1) if lega else 'A1'} femminile"
            out.append(partita("volleyf", sq, d, th[2] if re.match(r"\d{1,2}:\d{2}$", th[2]) else "", sq["nome"], squadre[1], luogo, citta, comp,
                               f"{comp} di volley" + (f", {GIORNATA(gm.group(1))} ({gm.group(2).lower()})." if gm else "."), url.group(1) if url else ""))
    R["fonti"]["volleyf"] = len(out)
    return out


# ---------------- scrittura ----------------
try:
    from zoneinfo import ZoneInfo
    ROMA = ZoneInfo("Europe/Rome")
except Exception:
    ROMA = datetime.timezone(datetime.timedelta(hours=1))


def leggi_vecchio():
    p = os.path.join(RADICE, FILE)
    if not os.path.exists(p): return []
    s = open(p, encoding="utf-8").read()
    try: return json.loads(s[s.index("=") + 1:].rstrip().rstrip(";"))["eventi"]
    except Exception: return []


def main():
    nuovi = []
    for f in (serie_a, uefa, superlega, volley_femminile, fortitudo, extra):
        try: nuovi += f()
        except Exception as ex: R["errori"].append(f"{f.__name__}: {ex}")
    try:
        l, big = lba(); nuovi += l
        nuovi += euroleague(big)
    except Exception as ex: R["errori"].append(f"basket: {ex}")
    fonti_ok = {v["_f"] for v in nuovi}
    for v in leggi_vecchio():
        if v.get("_f") and v["_f"] not in fonti_ok and v["data"] >= OGGI.isoformat(): nuovi.append(v)
    ok, visti = [], set()
    for v in sorted(nuovi, key=lambda v: (v["data"], v["ora"] or "99", v["artista"])):
        k = (v["data"], v["rassegna"], norm(v["artista"]))
        if k in visti or not (v["luogo"] and v["citta"] and v["fonte"].startswith("https://")): continue
        visti.add(k); ok.append(v)
    for i, v in enumerate(ok): v["id"] = f"p{i + 1:03d}"
    for v in ok: R["per_sport"][v["genere"]] = R["per_sport"].get(v["genere"], 0) + 1
    R["totale"] = len(ok); R["giorno"] = OGGI.isoformat()
    print(json.dumps(R, ensure_ascii=False, indent=1))
    if PROVA:
        for v in ok[:60]: print(v["data"], v["ora"], v["genere"], v["tipo"], "|", v["artista"], "|", v["luogo"], v["citta"], "|", v["descrizione"][:60], "|", v["biglietti"][:50])
        return
    if not ok:
        print("nessuna partita: file lasciato com'era"); sys.exit(1)
    dati = {"aggiornato": OGGI.isoformat(), "eventi": [{k: v[k] for k in ["id"] + [x for x in v if x != "id"]} for v in ok]}
    open(os.path.join(RADICE, FILE), "w", encoding="utf-8").write("window.SPORT_DATA=" + json.dumps(dati, ensure_ascii=False, separators=(",", ":")) + ";\n")
    json.dump(R, open(os.path.join(RADICE, "dati", f"sport_{CITTA}.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
