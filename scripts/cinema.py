#!/usr/bin/env python3
"""Controlla dati/cinema.json e scrive cinema.js per la scheda Cinema.
Uso: python3 scripts/cinema.py [dati/cinema.json] [cinema.js]
Schema: {aggiornato, giorno_orari (AAAA-MM-GG), sale:[{id,nome,citta,indirizzo,tipo,sito,fonte,
         film:[{titolo,orari:["HH:MM"],versione,genere,regia}]}]}
tipo ammessi: Multisala, D'essai, Cineteca, Sala di comunità, Arena."""
import json, re, sys, datetime
src = sys.argv[1] if len(sys.argv) > 1 else "dati/cinema.json"
out = sys.argv[2] if len(sys.argv) > 2 else "cinema.js"
d = json.load(open(src, encoding="utf-8"))
ERR, AVV = [], []
ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")
TIPI = {"Multisala", "D'essai", "Cineteca", "Sala di comunità", "Arena"}
for k in ("aggiornato", "giorno_orari"):
    if not ISO.match(d.get(k, "")): ERR.append(f"{k} mancante o non AAAA-MM-GG")
ids = set()
for s in d.get("sale", []):
    n = s.get("nome") or "?"
    if not s.get("nome"): ERR.append("sala senza nome")
    if s.get("id") in ids: ERR.append(f"id ripetuto {s.get('id')}")
    ids.add(s.get("id"))
    if s.get("tipo") not in TIPI: ERR.append(f"{n}: tipo «{s.get('tipo')}» non ammesso")
    for u in (s.get("sito"), s.get("fonte")):
        if u and not u.startswith("https://"): ERR.append(f"{n}: link non https {u}")
    if not (s.get("sito") or s.get("fonte")): AVV.append(f"{n}: nessun link al programma")
    for f in s.get("film", []):
        if not f.get("titolo"): ERR.append(f"{n}: film senza titolo")
        o = f.get("orari", [])
        bad = [x for x in o if not re.match(r"^\d{1,2}:\d{2}$", x)]
        if bad: ERR.append(f"{n} / {f.get('titolo')}: orari non validi {bad}")
        f["orari"] = sorted(set(x for x in o if x not in bad), key=lambda x: (int(x.split(':')[0]), x))
        g = f.get("giorni") or {}
        if not isinstance(g, dict): ERR.append(f"{n} / {f.get('titolo')}: giorni deve essere un oggetto data → orari")
        else:
            for k, v in list(g.items()):
                if not ISO.match(k) or not isinstance(v, list) or any(not re.match(r"^\d{1,2}:\d{2}$", x) for x in v):
                    ERR.append(f"{n} / {f.get('titolo')}: giorno non valido {k}: {v}")
                else: g[k] = sorted(set(v), key=lambda x: (int(x.split(':')[0]), x))
try:
    g = datetime.date.fromisoformat(d.get("giorno_orari", ""))
    if (datetime.date.today() - g).days > 7: AVV.append(f"orari vecchi di {(datetime.date.today()-g).days} giorni")
except ValueError: pass
con = [s for s in d.get("sale", []) if s.get("film")]
print(f"{len(d.get('sale', []))} sale, {len(con)} con film, "
      f"{len({f['titolo'].lower() for s in con for f in s['film']})} film distinti")
for a in AVV: print("AVVISO:", a)
if ERR:
    for e in ERR: print("ERRORE:", e)
    sys.exit(1)
open(out, "w", encoding="utf-8").write("/* Programmazione dei cinema: generato da scripts/cinema.py */\nwindow.CINEMA_DATA="
    + json.dumps(d, ensure_ascii=False, separators=(",", ":")) + ";\n")
print("scritto", out)
