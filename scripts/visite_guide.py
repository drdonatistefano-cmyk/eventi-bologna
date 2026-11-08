"""Visite giornaliere delle tre guide Ach's per il cruscotto (8/11/2026).

Uso: GOATCOUNTER_TOKEN=... python3 scripts/visite_guide.py [dati/visite_guide.json]

Legge da GoatCounter le pagine viste per giorno (senza gli eventi: clic, filtri…) di:
  Ach's Events Guide   contatore eventibologna  (achevents.com)
  Ach's Dinners Guide  contatore achdinners     (achdinners.com)
  Ach's Places Guide   contatore achplaces      (achplaces.com)
Per ogni contatore usa GOATCOUNTER_TOKEN_<NOME> se c'è (es. GOATCOUNTER_TOKEN_ACHPLACES),
altrimenti GOATCOUNTER_TOKEN. Scrive una riga per guida e giorno dal lancio di quella guida:
  {"guida", "sito", "giorno", "visite", "stato", "letto"}
Un contatore che non risponde (chiave che non vale per quel sito, contatore non ancora creato)
esce con una sola riga senza giorno e "stato" che spiega perché: il cruscotto lo mostra così.
Il giorno è quello di GoatCounter (UTC). Non si ferma mai per un solo contatore.
"""
import datetime
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

GUIDE = [
    ("Ach's Events Guide", "achevents.com", "eventibologna", "2026-11-04"),
    ("Ach's Dinners Guide", "achdinners.com", "achdinners", "2026-11-08"),
    ("Ach's Places Guide", "achplaces.com", "achplaces", "2026-11-08"),
]


def chiedi(contatore, token, percorso, **param):
    url = f"https://{contatore}.goatcounter.com/api/v0{percorso}?" + urllib.parse.urlencode(param)
    req = urllib.request.Request(url, headers={"Authorization": "Bearer " + token, "Content-Type": "application/json",
                                               "User-Agent": "ach-guide-visite"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def visite_per_giorno(contatore, token, dal):
    adesso = datetime.datetime.now(datetime.timezone.utc).replace(minute=0, second=0, microsecond=0)
    inizio = datetime.datetime.fromisoformat(dal).replace(tzinfo=datetime.timezone.utc)
    fine = adesso + datetime.timedelta(hours=1)
    giorni, escludi = {}, []
    for _ in range(10):  # pagine da 100 percorsi
        par = dict(start=inizio.strftime("%Y-%m-%dT%H:%M:%SZ"), end=fine.strftime("%Y-%m-%dT%H:%M:%SZ"), limit=100, daily="true")
        if escludi:
            par["exclude_paths"] = ",".join(escludi)
        r = chiedi(contatore, token, "/stats/hits", **par)
        for h in r.get("hits", []):
            if "path_id" in h:
                escludi.append(str(h["path_id"]))
            if h.get("event"):
                continue
            for s in h.get("stats", []) or []:
                g = s["day"][:10]
                giorni[g] = giorni.get(g, 0) + int(s.get("daily", 0) or 0)
        if not r.get("more"):
            break
    oggi = adesso.date()
    d = datetime.date.fromisoformat(dal)
    while d <= oggi:  # anche i giorni senza visite, così il grafico non salta
        giorni.setdefault(d.isoformat(), 0)
        d += datetime.timedelta(days=1)
    return giorni


def main():
    dest = sys.argv[1] if len(sys.argv) > 1 else "dati/visite_guide.json"
    letto = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    righe = []
    for guida, sito, contatore, dal in GUIDE:
        token = os.environ.get("GOATCOUNTER_TOKEN_" + contatore.upper()) or os.environ.get("GOATCOUNTER_TOKEN")
        if not token:
            righe.append({"guida": guida, "sito": sito, "giorno": None, "visite": None, "stato": "chiave GoatCounter mancante", "letto": letto})
            continue
        try:
            g = visite_per_giorno(contatore, token, dal)
            for giorno in sorted(g):
                righe.append({"guida": guida, "sito": sito, "giorno": giorno, "visite": g[giorno], "stato": "ok", "letto": letto})
            print(f"{guida}: {sum(g.values())} visite dal {dal}")
        except urllib.error.HTTPError as e:
            motivo = {401: "la chiave non vale per questo contatore", 403: "la chiave non vale per questo contatore",
                      404: "contatore non trovato"}.get(e.code, f"errore {e.code} da GoatCounter")
            righe.append({"guida": guida, "sito": sito, "giorno": None, "visite": None, "stato": motivo, "letto": letto})
            print(f"{guida}: {motivo}")
        except Exception as e:  # rete, risposta strana: si riprova al giro dopo
            righe.append({"guida": guida, "sito": sito, "giorno": None, "visite": None, "stato": "lettura non riuscita", "letto": letto})
            print(f"{guida}: lettura non riuscita ({e})")
    os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
    with open(dest, "w", encoding="utf-8") as f:
        json.dump(righe, f, ensure_ascii=False, indent=0)


if __name__ == "__main__":
    main()
