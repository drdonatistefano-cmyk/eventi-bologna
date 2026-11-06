# Abbina gli eventi della guida ai gruppi TicketOne (API Eventim) e aggiunge quelli mancanti.
# Gruppi: API pubblica Eventim, es. https://public-api.eventim.com/websearch/search/api/exploration/v2/productGroups?webId=web__ticketone-it&language=it&city_ids=218&page=1&sort=DateAsc&in_stock=true&categories=Concerti
# city_ids: Milano 215, Bologna 218. Categorie: Concerti, Teatro, Mostre%20e%20Musei (max 8 pagine da 20 per categoria). Salvare la lista unita di productGroups in un file json.
# uso: python3 abbina.py <cartella-dati> <gruppi.json> <citta-default> [--aggiungi]
import json, re, sys, unicodedata, collections
cart, gfile, CAPO = sys.argv[1], sys.argv[2], sys.argv[3]
AGG = "--aggiungi" in sys.argv
STOP = set("e and the di il la lo i gli le de del della dei in a al live tour concerto teatro milano bologna 2026 2027 show con feat ft x".split())

def tok(s):
    s = unicodedata.normalize("NFD", (s or "").lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return {w for w in re.findall(r"[a-z0-9]+", s) if w not in STOP and len(w) > 1}

def vtok(s):
    return tok(re.sub(r"(?i)\b(teatro|tam|club|milano|ing|arena|unipol|snai|kozel|circolo|toscana|31|spazio)\b", " ", s or "")) or tok(s)

ev = json.load(open(cart + "/eventi.json"))
G = json.load(open(gfile))
prod = []  # (gruppo, prodotto, data, luogo)
for g in G:
    for p in g["products"]:
        le = p["typeAttributes"]["liveEntertainment"]
        prod.append((g, p, le["startDate"][:10], le["location"]["name"], le["location"].get("city", "")))
gr_luogo = {g["productGroupId"]: g["products"][0]["typeAttributes"]["liveEntertainment"]["location"]["name"] for g in G}

def url(x): return x["url"]["domain"] + x["url"]["path"]

# link già presenti → gruppo già coperto
u2g = {}
for g in G:
    u2g[url(g)] = g["productGroupId"]
    for p in g["products"]: u2g[url(p)] = g["productGroupId"]
usati, fatti = set(), 0
for e in ev:
    if re.search(r"ticketone\.it/(event|artist)/", e.get("biglietti") or ""):
        if e["biglietti"] in u2g: usati.add(u2g[e["biglietti"]])
        fatti += 1; continue
    te, tv = tok(e["artista"]), vtok(e["luogo"])
    best = None
    for g in G:
        tg = tok(g["name"]) | tok(g.get("mainAttraction",{}).get("name",""))
        if not (te & tg): continue
        # quota di parole del titolo dell'evento ritrovate nel gruppo
        q = len(te & tg) / max(1, min(len(te), len(tg)))
        if q < 0.5: continue
        gs, gf = g["startDate"][:10], (g.get("endDate") or g["startDate"])[:10]
        if not (gs <= e["fino"] and e["data"] <= gf): continue
        vl = vtok(gr_luogo[g["productGroupId"]])
        if tv and vl and not (tv & vl): continue
        # prodotto della stessa data, se c'è
        p = next((p for p in g["products"] if p["typeAttributes"]["liveEntertainment"]["startDate"][:10] == e["data"]), None)
        sc = q + (1 if p else 0)
        if not best or sc > best[0]: best = (sc, g, p)
    if best:
        _, g, p = best
        e["biglietti"] = url(p) if p else url(g)
        e["biglietti_tipo"] = "Acquista"
        usati.add(g["productGroupId"]); fatti += 1
print("eventi con TicketOne:", fatti, "su", len(ev))

# gruppi non abbinati → eventi nuovi
CAT = {"Pop & Rock": ("Pop e altra musica", ""), "Night life": ("Pop e altra musica", ""), "Jazz": ("Jazz", ""), "Metal": ("Rock", ""),
       "Festival": ("Pop e altra musica", "Festival"), "Altri eventi musicali": ("Pop e altra musica", ""),
       "Prosa": ("Teatro", "Prosa"), "Musical e varietà": ("Teatro", "Musical"), "Cabaret": ("Teatro", "Comicità"),
       "Stand Up Comedy": ("Teatro", "Comicità"), "Talk e Creator": ("Teatro", "Incontro"), "Balletto classico e moderno": ("Teatro", "Danza"),
       "Concerti di musica classica": ("Classica", ""), "Teatro lirico": ("Classica", "Opera"), "Altri eventi teatrali": ("Teatro", "")}
nuovi = []
if AGG:
    for g in G:
        if g["productGroupId"] in usati: continue
        sub = [c["name"] for c in g["categories"] if "parentCategory" in c]
        k = next((s for s in sub if s in CAT), None)
        if not k: continue
        gen, tipo = CAT[k]
        P = sorted(g["products"], key=lambda p: p["typeAttributes"]["liveEntertainment"]["startDate"])
        P = [p for p in P if p["typeAttributes"]["liveEntertainment"]["startDate"][:10] >= "2026-11-06"]
        if not P: continue
        d = (g.get("description") or "").split(". ")[0].strip()
        d = re.sub(r"(?i)\s*(acquista|scopri)[^.]*$", "", d).strip()
        if not d or len(d) > 160: d = {"Prosa": "Spettacolo di prosa", "Musical": "Musical", "Comicità": "Spettacolo comico", "Danza": "Spettacolo di danza", "Incontro": "Incontro dal vivo"}.get(tipo, "Concerto")
        # elenco prodotti completo (meno di 4 mostrati = tutte le date in città): un evento per data
        singole = g["productCount"] <= len(g["products"])
        if singole:
            vis, gruppi = set(), []
            for p in P:
                dd = p["typeAttributes"]["liveEntertainment"]["startDate"][:10]
                if dd not in vis: vis.add(dd); gruppi.append([p])
        else:
            gruppi = [P]
        for pp in gruppi:
            le0x = pp[0]["typeAttributes"]["liveEntertainment"]
            dx, vx, tx = le0x["startDate"][:10], vtok(le0x["location"]["name"]), tok(g["name"]) | tok(g.get("mainAttraction",{}).get("name",""))
            gem = next((e for e in ev if e["data"] <= dx <= e["fino"] and (vtok(e["luogo"]) & vx) and (tok(e["artista"]) & tx)), None)
            if gem:
                if not re.search(r"ticketone\.it/(event|artist)/", gem.get("biglietti") or ""):
                    gem["biglietti"] = url(pp[0]) if len(pp) == 1 else url(g); gem["biglietti_tipo"] = "Acquista"; fatti += 1
                continue
            le0, le1 = pp[0]["typeAttributes"]["liveEntertainment"], pp[-1]["typeAttributes"]["liveEntertainment"]
            s, f = le0["startDate"][:10], le1["startDate"][:10]
            luogo = re.sub(r"^TAM - ", "", le0["location"]["name"]).replace(" - ING", "").replace(" (Arena Milano)", "")
            luogo = {"Teatro Arcimboldi Milano": "Teatro Arcimboldi", "Allo Sbagliato - Teatro Principe": "Teatro Principe",
                     "Ippodromo Snai - San Siro": "Ippodromo SNAI San Siro", "Kozel Carroponte": "Carroponte", "teatro oscar": "Teatro Oscar",
                     "Blue Note": "Blue Note Milano", "Stadio DallAra": "Stadio Dall'Ara"}.get(luogo, luogo)
            citta = {"Unipol Forum": "Assago", "Circolo Magnolia": "Segrate", "Carroponte": "Sesto San Giovanni", "Fiera Milano Live": "Rho"}.get(luogo, le0["location"].get("city") or CAPO)
            ora = le0["startDate"][11:16] if len(pp) == 1 else "n.d."
            if ora == "00:00": ora = "n.d."
            nuovi.append({"id": "", "data": s, "fino": f, "ora": ora, "artista": g["name"], "luogo": luogo, "citta": citta,
                          "genere": gen, "tipo": tipo, "rassegna": "", "descrizione": d.rstrip(".") + ".", "fonte": url(g),
                          "biglietti": url(pp[0]) if len(pp) == 1 else url(g), "biglietti_tipo": "Acquista",
                          "disp": "disponibile", "disp_nota": "", "disp_verificata": "2026-11-06", "sito_luogo": ""})
    print("eventi con TicketOne dopo i controlli:", fatti)
    print("nuovi da TicketOne:", len(nuovi), collections.Counter(x["genere"] + "/" + x["tipo"] for x in nuovi))
json.dump(ev + nuovi, open(cart + "/eventi.json", "w"), ensure_ascii=False, indent=1)
