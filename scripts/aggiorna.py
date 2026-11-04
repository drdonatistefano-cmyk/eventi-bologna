"""Eventi a Bologna – controllo e pubblicazione dei dati.

Uso:
  python3 aggiorna.py <eventi.json | eventi.js> [--oggi AAAA-MM-GG] [--out eventi.js]
  python3 aggiorna.py <mostre.json | mostre.js> --mostre [--oggi AAAA-MM-GG] [--out mostre.js]

Legge l'elenco eventi (JSON puro, oppure il file eventi.js pubblicato),
lo controlla, toglie gli eventi già finiti, unisce i doppioni,
assegna gli id mancanti, ordina e scrive eventi.js (più eventi.json di lavoro).
Se trova errori NON scrive nulla e termina con codice 1: correggi e rilancia.
"""
import json, re, sys, datetime, unicodedata, collections

GENERI = {"Rock", "Jazz", "Pop e altra musica", "Classica", "Teatro"}
DISP = {"disponibile", "pochi posti", "sold out", "non disponibile", "non ancora in vendita", "da verificare"}
BIG = {"Acquista", "Biglietteria", "Info", ""}
ZONE = {
 "Bologna": ["Bologna"],
 "Colli e Valsamoggia": ["Casalecchio di Reno","Zola Predosa","Sasso Marconi","Valsamoggia","Monte San Pietro"],
 "Terre d'Acqua": ["San Giovanni in Persiceto","Anzola dell'Emilia","Calderara di Reno","Crevalcore","Sala Bolognese","Sant'Agata Bolognese"],
 "Reno Galliera": ["Castel Maggiore","Argelato","Bentivoglio","Castello d'Argile","Galliera","Pieve di Cento","San Giorgio di Piano","San Pietro in Casale"],
 "Terre di Pianura": ["Budrio","Baricella","Granarolo dell'Emilia","Malalbergo","Minerbio","Molinella","Castenaso"],
 "Savena e Idice": ["San Lazzaro di Savena","Ozzano dell'Emilia","Pianoro","Loiano","Monghidoro","Monterenzio"],
 "Imolese": ["Imola","Castel San Pietro Terme","Medicina","Dozza","Castel Guelfo di Bologna","Mordano","Borgo Tossignano","Casalfiumanese","Fontanelice","Castel del Rio"],
 "Appennino": ["Alto Reno Terme","Camugnano","Castel d'Aiano","Castel di Casio","Castiglione dei Pepoli","Gaggio Montano","Grizzana Morandi","Lizzano in Belvedere","Marzabotto","Monzuno","San Benedetto Val di Sambro","Vergato"],
}
COMUNE = {c: z for z, cs in ZONE.items() for c in cs}
ALIAS = {"porretta terme": "Alto Reno Terme", "casalecchio": "Casalecchio di Reno", "san lazzaro": "San Lazzaro di Savena",
         "zola": "Zola Predosa", "persiceto": "San Giovanni in Persiceto", "castel san pietro": "Castel San Pietro Terme",
         "bazzano": "Valsamoggia", "crespellano": "Valsamoggia", "funo": "Argelato", "san marino di bentivoglio": "Bentivoglio"}
CAMPI = ["id","data","fino","ora","artista","luogo","citta","genere","tipo","rassegna","descrizione","fonte","biglietti",
         "biglietti_tipo","disp","disp_nota","disp_verificata","sito_luogo"]
DATA_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

def norm(s):
    s = unicodedata.normalize("NFD", str(s or "").lower())
    return re.sub(r"[^a-z0-9]+", " ", "".join(c for c in s if not unicodedata.combining(c))).strip()

def leggi(path):
    txt = open(path, encoding="utf-8").read().strip()
    if path.endswith(".js") or txt.startswith("window."):
        txt = txt[txt.index("{"): txt.rindex("}") + 1]
        obj = json.loads(txt.replace("<\\/", "</"))
        return obj.get("eventi", [])
    obj = json.loads(txt)
    return obj["eventi"] if isinstance(obj, dict) else obj

def valida_data(s):
    if not DATA_RE.match(s or ""): return False
    try: datetime.date.fromisoformat(s); return True
    except ValueError: return False

def pulisci_url(u):
    u = str(u or "").strip()
    u = re.sub(r"[?&]utm_[^#]*", "", u)
    return u if re.match(r"^https://", u) else ""

CATEGORIE = {"Arte antica e Ottocento", "Arte moderna e contemporanea", "Fotografia", "Cinema e design", "Storia e società", "Scienza e tecnica"}
CAMPI_M = ["id","titolo","sede","citta","inizio","fine","categoria","descrizione","ingresso","orari","fonte","sito"]

def leggi_mostre(path):
    txt = open(path, encoding="utf-8").read().strip()
    if path.endswith(".js") or txt.startswith("window."):
        txt = txt[txt.index("{"): txt.rindex("}") + 1]
        return json.loads(txt.replace("<\\/", "</")).get("mostre", [])
    obj = json.loads(txt)
    return obj["mostre"] if isinstance(obj, dict) else obj

def mostre(src, oggi, out):
    ev = leggi_mostre(src); errori, avvisi, ok, finite = [], [], [], 0
    for i, m in enumerate(ev):
        m = {k: (v.strip() if isinstance(v, str) else v) for k, v in m.items() if k in CAMPI_M}
        rif = f"{m.get('id') or '#'+str(i)} «{m.get('titolo','?')}»"
        if not m.get("titolo"): errori.append(f"{rif}: manca il titolo")
        if not m.get("sede"): errori.append(f"{rif}: manca la sede")
        if not (valida_data(m.get("inizio")) and valida_data(m.get("fine"))): errori.append(f"{rif}: date non valide"); continue
        if m["fine"] < m["inizio"]: errori.append(f"{rif}: la fine precede l'inizio")
        if m["fine"] < oggi: finite += 1; continue
        c = ALIAS.get((m.get("citta") or "Bologna").lower(), m.get("citta") or "Bologna")
        if c not in COMUNE: errori.append(f"{rif}: comune sconosciuto '{c}'")
        m["citta"] = c
        if m.get("categoria") not in CATEGORIE: errori.append(f"{rif}: categoria '{m.get('categoria')}' non ammessa {sorted(CATEGORIE)}")
        m["ingresso"] = (m.get("ingresso") or "da verificare").lower()
        if m["ingresso"] not in ("gratuito", "a pagamento", "da verificare"): avvisi.append(f"{rif}: ingresso '{m['ingresso']}' → da verificare"); m["ingresso"] = "da verificare"
        for k in ("fonte", "sito"):
            v = pulisci_url(m.get(k))
            if m.get(k) and not v: avvisi.append(f"{rif}: link {k} scartato (non https)")
            m[k] = v
        if not m.get("descrizione"): avvisi.append(f"{rif}: senza descrizione")
        for k in CAMPI_M: m.setdefault(k, "")
        ok.append({k: m[k] for k in CAMPI_M})
    visti, unici = set(), []
    for m in ok:
        k = (norm(m["titolo"]), norm(m["sede"]))
        if k in visti: continue
        visti.add(k); unici.append(m)
    mx = max([int(x["id"][1:]) for x in unici if re.match(r"^m\d+$", x["id"] or "")] or [0]); usati = set()
    for m in unici:
        if not re.match(r"^m\d+$", m["id"] or "") or m["id"] in usati: mx += 1; m["id"] = f"m{mx:03d}"
        usati.add(m["id"])
    unici.sort(key=lambda m: (m["inizio"] > oggi, m["fine"] if m["inizio"] <= oggi else m["inizio"]))
    print(f"Mostre valide: {len(unici)} · tolte perché chiuse: {finite} · doppioni tolti: {len(ok)-len(unici)}")
    for x in avvisi[:40]: print("  avviso:", x)
    if errori:
        print(f"\n{len(errori)} ERRORI – niente è stato scritto:"); [print("  errore:", x) for x in errori]; sys.exit(1)
    if len(unici) < 5: print("\nERRORE: meno di 5 mostre, elenco probabilmente incompleto – niente è stato scritto."); sys.exit(1)
    blob = json.dumps({"aggiornato": oggi, "mostre": unici}, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    open(out, "w", encoding="utf-8").write("window.MOSTRE_DATA=" + blob + ";\n")
    json.dump(unici, open("mostre.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"Scritto {out} ({len(blob)//1024} KB) e mostre.json")

def main():
    a = sys.argv[1:]
    if not a: print(__doc__); sys.exit(2)
    if "--mostre" in a:
        oggi = a[a.index("--oggi") + 1] if "--oggi" in a else datetime.date.today().isoformat()
        out = a[a.index("--out") + 1] if "--out" in a else "mostre.js"
        return mostre(a[0], oggi, out)
    src = a[0]
    oggi = a[a.index("--oggi") + 1] if "--oggi" in a else datetime.date.today().isoformat()
    out = a[a.index("--out") + 1] if "--out" in a else "eventi.js"
    ev = leggi(src)
    errori, avvisi = [], []
    puliti, passati = [], 0
    for i, e in enumerate(ev):
        if not isinstance(e, dict): errori.append(f"riga {i}: non è un oggetto"); continue
        e = {k: (v.strip() if isinstance(v, str) else v) for k, v in e.items() if k in CAMPI or k == "giorno"}
        e.pop("giorno", None)
        rif = f"{e.get('id') or '#'+str(i)} «{e.get('artista','?')}»"
        if not e.get("artista"): errori.append(f"{rif}: manca il titolo (artista)")
        if not valida_data(e.get("data")): errori.append(f"{rif}: data non valida '{e.get('data')}'"); continue
        e["fino"] = e.get("fino") or e["data"]
        if not valida_data(e["fino"]): errori.append(f"{rif}: data fine non valida '{e['fino']}'"); continue
        if e["fino"] < e["data"]: errori.append(f"{rif}: la data fine precede l'inizio")
        if e["fino"] < oggi: passati += 1; continue
        if not re.match(r"^\d{1,2}[:.]\d{2}", e.get("ora") or ""): e["ora"] = "n.d."
        c = e.get("citta") or "Bologna"
        c = ALIAS.get(c.lower(), c)
        if c not in COMUNE:
            m = [x for x in COMUNE if norm(x) == norm(c)]
            if m: c = m[0]
            else: errori.append(f"{rif}: comune sconosciuto '{c}' (deve essere uno dei 55 della Città metropolitana)")
        e["citta"] = c
        if e.get("genere") not in GENERI: errori.append(f"{rif}: genere '{e.get('genere')}' non ammesso {sorted(GENERI)}")
        if not e.get("luogo"): errori.append(f"{rif}: manca il luogo")
        e["disp"] = (e.get("disp") or "da verificare").lower()
        if e["disp"] not in DISP: avvisi.append(f"{rif}: disponibilità '{e['disp']}' → da verificare"); e["disp"] = "da verificare"
        for k in ("fonte", "biglietti", "sito_luogo"):
            v = pulisci_url(e.get(k))
            if e.get(k) and not v: avvisi.append(f"{rif}: link {k} scartato (non https)")
            e[k] = re.sub(r"[&?]?utm_content=claude", "", v)
        if e.get("biglietti_tipo") not in BIG: e["biglietti_tipo"] = "Info" if e.get("biglietti") else ""
        if not e.get("biglietti"): e["biglietti_tipo"] = ""
        if not e.get("descrizione"): avvisi.append(f"{rif}: senza descrizione")
        for k in CAMPI: e.setdefault(k, "")
        puliti.append({k: e[k] for k in CAMPI})
    # doppioni: stesso inizio + stesso titolo + stesso luogo
    visti, unici, doppi = {}, [], 0
    for e in puliti:
        k = (e["data"], norm(e["artista"]), norm(e["luogo"]))
        if k in visti:
            doppi += 1
            t = visti[k]
            for f in CAMPI:
                if not t[f] and e[f]: t[f] = e[f]
            continue
        visti[k] = e; unici.append(e)
    # id unici
    usati, mx = set(), 0
    for e in unici:
        m = re.match(r"^e(\d+)$", e["id"] or "")
        if m: mx = max(mx, int(m.group(1)))
    for e in unici:
        if not e["id"] or e["id"] in usati:
            mx += 1; e["id"] = f"e{mx:03d}"
        usati.add(e["id"])
    unici.sort(key=lambda e: (e["data"], e["ora"], norm(e["artista"])))
    print(f"Eventi validi: {len(unici)} · tolti perché finiti: {passati} · doppioni uniti: {doppi}")
    pz = collections.Counter(COMUNE.get(e["citta"], "?") for e in unici)
    print("Per zona: " + ", ".join(f"{z} {pz[z]}" for z in ZONE if pz[z]))
    print(f"Comuni con eventi: {len(set(e['citta'] for e in unici))}/55")
    for x in avvisi[:40]: print("  avviso:", x)
    if len(avvisi) > 40: print(f"  …altri {len(avvisi)-40} avvisi")
    if errori:
        print(f"\n{len(errori)} ERRORI – niente è stato scritto:")
        for x in errori: print("  errore:", x)
        sys.exit(1)
    if len(unici) < 50:
        print("\nERRORE: meno di 50 eventi, probabilmente l'elenco è incompleto – niente è stato scritto."); sys.exit(1)
    blob = json.dumps({"aggiornato": oggi, "eventi": unici}, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    open(out, "w", encoding="utf-8").write("window.EVENTI_DATA=" + blob + ";\n")
    json.dump(unici, open("eventi.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"Scritto {out} ({len(blob)//1024} KB) ed eventi.json")

if __name__ == "__main__":
    main()
