"""Da dove arrivano i visitatori delle tre guide Ach's (11/11/2026), per il cruscotto delle visite.

Uso: GOATCOUNTER_TOKEN=... python3 scripts/visite_dettagli.py [dati/visite_dettagli.json]

Per ogni guida, dal lancio a oggi, legge da GoatCounter:
  Paese, Regione italiana (solo per l'Italia), Provenienza (sito da cui si arriva),
  Dispositivo (dimensione dello schermo), Sistema, Browser, Pagina (le più viste, senza clic e filtri),
  Ora (ora italiana del giorno, somma su tutti i giorni).
Scrive una riga per guida, tipo e voce: {"guida", "tipo", "voce", "visite", "letto"}.
Un tipo che GoatCounter non dà resta senza righe: lo script non si ferma mai per una sola lettura.
GoatCounter non salva indirizzi IP né cookie: i paesi e le regioni vengono dall'IP al momento della visita.
"""
import datetime
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from visite_guide import GUIDE, chiedi  # stesse guide e stessa chiamata

NOMI_SCHERMO = {"phone": "Telefono", "largephone": "Telefono grande", "tablet": "Tablet",
                "desktop": "Computer", "desktophd": "Computer grande", "unknown": "Sconosciuto"}
PAESI = {"IT": "Italia", "US": "Stati Uniti", "DE": "Germania", "FR": "Francia", "GB": "Regno Unito",
         "ES": "Spagna", "CH": "Svizzera", "NL": "Paesi Bassi", "BE": "Belgio", "AT": "Austria",
         "IE": "Irlanda", "SE": "Svezia", "PL": "Polonia", "RO": "Romania", "CA": "Canada",
         "BR": "Brasile", "CN": "Cina", "JP": "Giappone", "IN": "India", "RU": "Russia", "SG": "Singapore",
         "FI": "Finlandia", "DK": "Danimarca", "NO": "Norvegia", "PT": "Portogallo", "GR": "Grecia",
         "SM": "San Marino", "VA": "Città del Vaticano", "AU": "Australia", "": "Sconosciuto"}


def elenco(contatore, token, percorso, inizio, fine, limite=50):
    par = dict(start=inizio, end=fine, limit=limite)
    r = chiedi(contatore, token, percorso, **par)
    return r.get("stats", []) or []


def dettagli(contatore, token, dal):
    adesso = datetime.datetime.now(datetime.timezone.utc).replace(minute=0, second=0, microsecond=0)
    inizio = dal + "T00:00:00Z"
    fine = (adesso + datetime.timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    righe = []
    def metti(tipo, voce, n):
        if n:
            righe.append((tipo, voce, int(n)))
    for tipo, percorso in (("Provenienza", "/stats/toprefs"), ("Browser", "/stats/browsers"),
                           ("Sistema", "/stats/systems"), ("Dispositivo", "/stats/sizes"),
                           ("Paese", "/stats/locations")):
        try:
            for s in elenco(contatore, token, percorso, inizio, fine):
                nome = s.get("name") or ""
                if tipo == "Provenienza" and not nome:
                    nome = "Diretto o non indicato"
                if tipo == "Dispositivo":
                    nome = NOMI_SCHERMO.get(s.get("id") or nome, nome or "Sconosciuto")
                if tipo == "Paese":
                    cod = (s.get("id") or "").upper()
                    nome = PAESI.get(cod, nome or cod or "Sconosciuto")
                metti(tipo, nome, s.get("count"))
        except Exception as e:
            print(f"  {tipo}: non letto ({e})")
    try:  # regioni italiane
        r = chiedi(contatore, token, "/stats/locations/IT", start=inizio, end=fine, limit=30)
        for s in r.get("stats", []) or []:
            metti("Regione italiana", s.get("name") or "Non indicata", s.get("count"))
    except Exception as e:
        print(f"  regioni: non lette ({e})")
    try:  # pagine più viste e ora del giorno
        r = chiedi(contatore, token, "/stats/hits", start=inizio, end=fine, limit=100, daily="false")
        ore = [0] * 24
        roma = ZoneInfo("Europe/Rome")
        for h in r.get("hits", []) or []:
            if h.get("event"):
                continue
            metti("Pagina", h.get("path") or "/", h.get("count"))
            for s in h.get("stats", []) or []:
                g = datetime.date.fromisoformat(s["day"][:10])
                for i, n in enumerate(s.get("hourly") or []):
                    if n:
                        t = datetime.datetime(g.year, g.month, g.day, i, tzinfo=datetime.timezone.utc).astimezone(roma)
                        ore[t.hour] += int(n)
        for i, n in enumerate(ore):
            righe.append(("Ora", f"{i:02d}", n))
    except Exception as e:
        print(f"  pagine e ore: non lette ({e})")
    return righe


def main():
    dest = sys.argv[1] if len(sys.argv) > 1 else "dati/visite_dettagli.json"
    letto = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    out = []
    for guida, sito, contatore, dal in GUIDE:
        token = os.environ.get("GOATCOUNTER_TOKEN_" + contatore.upper()) or os.environ.get("GOATCOUNTER_TOKEN")
        if not token:
            continue
        print(guida)
        for tipo, voce, n in dettagli(contatore, token, dal):
            out.append({"guida": guida, "tipo": tipo, "voce": voce, "visite": n, "letto": letto})
    os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
    with open(dest, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=0)
    print(len(out), "righe")


if __name__ == "__main__":
    main()
