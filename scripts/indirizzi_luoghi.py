"""Indirizzi dei luoghi di Events da OpenStreetMap (18/11/2026, per le pagine dei singoli eventi).

Google mostra un evento nei suoi risultati «Eventi» solo se la pagina dice l'indirizzo del luogo (via e numero).
I file degli eventi hanno il nome del luogo e la città, non l'indirizzo: questo programma lo prende da OpenStreetMap
(dati aperti, licenza ODbL: nelle pagine si cita «© OpenStreetMap contributors»), mai da Google.

Uso:  python3 scripts/indirizzi_luoghi.py            legge OpenStreetMap (Overpass) e abbina
      python3 scripts/indirizzi_luoghi.py --abbina   abbina soltanto, con i file già salvati (nessuna rete)

Scrive:
  dati/osm_luoghi_<città>.json   i luoghi di spettacolo di OpenStreetMap nella provincia (teatri, sale, club, cinema...)
  dati/indirizzi_luoghi.json     per ogni luogo di Events abbinato: via, numero, CAP, comune, coordinate, id OSM, punteggio
  dati/indirizzi_da_vedere.json  i luoghi non abbinati o abbinati con dubbio: li guarda Claude (o Stefano) e, se serve,
                                 li scrive a mano in dati/indirizzi_manuali.json, che vale sopra tutto il resto
Gira su GitHub (flusso «Indirizzi dei luoghi», il 2 del mese): Claude non apre pagine (REGOLE punto 1).
"""
import difflib
import json
import os
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request

RADICE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATI = os.path.join(RADICE, "dati")
OVERPASS = ["https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter"]
# provincia (nome dell'area amministrativa di livello 6 in OpenStreetMap) e cartella dei dati di ogni città
CITTA = {"bo": ("Bologna", "."), "mi": ("Milano", "milano"), "ra": ("Ravenna", "ravenna"), "fe": ("Ferrara", "ferrara")}
TIPI = ("theatre|arts_centre|cinema|nightclub|music_venue|concert_hall|events_venue|community_centre|social_centre|"
        "conference_centre|library|place_of_worship|bar|pub|restaurant|cafe|stadium|exhibition_centre")
SOGLIA = 0.80      # sopra: abbinato; fra DUBBIO e SOGLIA: da vedere
DUBBIO = 0.62
PAROLE_VUOTE = {"teatro", "il", "lo", "la", "i", "gli", "le", "di", "del", "della", "dei", "degli", "delle", "e", "ed",
                "sala", "club", "circolo", "arci", "auditorium", "spazio", "centro", "the", "a", "al", "alla", "da"}


def norma(s):
    s = unicodedata.normalize("NFD", str(s or "").lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def parole(s):
    return {w for w in norma(s).split() if w not in PAROLE_VUOTE and len(w) > 1}


def somiglianza(a, b):
    """Fra 0 e 1: parole importanti in comune e somiglianza del testo intero."""
    pa, pb = parole(a), parole(b)
    if not pa or not pb:
        return 0.0
    comuni = len(pa & pb) / min(len(pa), len(pb))
    testo = difflib.SequenceMatcher(None, norma(a), norma(b)).ratio()
    return round(max(comuni * 0.85 + testo * 0.15, testo), 3)


def leggi_overpass(provincia):
    q = (f'[out:json][timeout:120];area["name"="{provincia}"]["admin_level"="6"]->.a;'
         f'(nwr["amenity"~"^({TIPI})$"]["name"](area.a);nwr["leisure"~"^(stadium|sports_centre)$"]["name"](area.a););'
         'out center tags;')
    dati = urllib.parse.urlencode({"data": q}).encode()
    ultimo = None
    for url in OVERPASS:
        for tentativo in range(3):
            try:
                req = urllib.request.Request(url, data=dati, headers={"User-Agent": "achevents-indirizzi/1.0 (+https://achevents.com)"})
                with urllib.request.urlopen(req, timeout=180) as r:
                    return json.load(r).get("elements", [])
            except Exception as e:  # noqa: BLE001
                ultimo = e
                time.sleep(20 * (tentativo + 1))
    raise RuntimeError(f"Overpass non risponde per {provincia}: {ultimo}")


def riduci(el):
    t = el.get("tags", {})
    lat = el.get("lat") or (el.get("center") or {}).get("lat")
    lon = el.get("lon") or (el.get("center") or {}).get("lon")
    return {"nome": t.get("name", ""), "altri_nomi": [t[k] for k in ("alt_name", "official_name", "short_name", "old_name") if t.get(k)],
            "via": t.get("addr:street", ""), "civico": t.get("addr:housenumber", ""), "cap": t.get("addr:postcode", ""),
            "comune": t.get("addr:city", ""), "tipo": t.get("amenity") or t.get("leisure", ""),
            "lat": lat, "lon": lon, "osm": f"{el.get('type')}/{el.get('id')}", "sito": t.get("website") or t.get("contact:website", "")}


def luoghi_di_events(cart):
    p = os.path.join(RADICE, cart, "eventi.js")
    if not os.path.exists(p):
        return {}
    t = open(p, encoding="utf-8").read()
    out = {}
    for e in json.loads(t[t.index("{"):t.rindex("}") + 1]).get("eventi", []):
        if e.get("luogo"):
            k = (e["luogo"], e.get("citta") or "")
            out[k] = out.get(k, 0) + 1
    return out


def abbina(k, osm, venues):
    risultati, da_vedere = {}, []
    for (luogo, citta), n in sorted(venues.items(), key=lambda x: -x[1]):
        migliori = []
        for o in osm:
            if not o["via"] or not o["civico"]:
                continue
            s = max([somiglianza(luogo, o["nome"])] + [somiglianza(luogo, x) for x in o["altri_nomi"]])
            # stesso comune: piccolo aiuto; comune diverso dichiarato: penalità
            if o["comune"] and citta:
                s = s + 0.05 if norma(o["comune"]) == norma(citta) else s - 0.10
            migliori.append((round(s, 3), o))
        migliori.sort(key=lambda x: -x[0])
        chiave = f"{luogo}|{citta}"
        if migliori and migliori[0][0] >= SOGLIA and (len(migliori) == 1 or migliori[0][0] - migliori[1][0] >= 0.05
                                                       or migliori[0][1]["via"] == migliori[1][1]["via"]):
            s, o = migliori[0]
            risultati[chiave] = {**{x: o[x] for x in ("via", "civico", "cap", "comune", "lat", "lon", "osm", "nome")},
                                 "comune": o["comune"] or citta, "punteggio": s, "fonte": "OpenStreetMap"}
        else:
            da_vedere.append({"luogo": luogo, "citta": citta, "eventi": n, "citta_guida": k,
                              "candidati": [{"punteggio": s, "nome": o["nome"], "indirizzo": f"{o['via']} {o['civico']}, {o['comune']}",
                                             "osm": o["osm"]} for s, o in migliori[:3] if s >= DUBBIO - 0.1]})
    return risultati, da_vedere


def main():
    os.makedirs(DATI, exist_ok=True)
    solo_abbina = "--abbina" in sys.argv
    tutti, vedere = {}, []
    for k, (provincia, cart) in CITTA.items():
        f = os.path.join(DATI, f"osm_luoghi_{k}.json")
        if not solo_abbina:
            try:
                osm = [riduci(x) for x in leggi_overpass(provincia)]
                osm = [o for o in osm if o["nome"]]
                json.dump(osm, open(f, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
                print(f"{provincia}: {len(osm)} luoghi da OpenStreetMap ({sum(1 for o in osm if o['via'] and o['civico'])} con via e numero)")
            except Exception as e:  # noqa: BLE001  «non sono riuscito a guardare» non è «non c'è» (REGOLE 8 bis.6)
                print(f"{provincia}: OpenStreetMap non letto ({e}); uso il file salvato, se c'è")
            time.sleep(5)
        if not os.path.exists(f):
            continue
        osm = json.load(open(f, encoding="utf-8"))
        r, v = abbina(k, osm, luoghi_di_events(cart))
        tutti.update(r)
        vedere += v
        print(f"{provincia}: {len(r)} luoghi abbinati, {len(v)} da vedere")
    manuali_p = os.path.join(DATI, "indirizzi_manuali.json")
    manuali = json.load(open(manuali_p, encoding="utf-8")) if os.path.exists(manuali_p) else {}
    for chiave, ind in manuali.items():
        if chiave.startswith("_"):
            continue
        tutti[chiave] = {**ind, "fonte": ind.get("fonte", "scritto a mano")}
        vedere = [x for x in vedere if f"{x['luogo']}|{x['citta']}" != chiave]
    json.dump(dict(sorted(tutti.items())), open(os.path.join(DATI, "indirizzi_luoghi.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    json.dump(vedere, open(os.path.join(DATI, "indirizzi_da_vedere.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"in tutto {len(tutti)} indirizzi, {len(vedere)} luoghi da vedere")


if __name__ == "__main__":
    main()
