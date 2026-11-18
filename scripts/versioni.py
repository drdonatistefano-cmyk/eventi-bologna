"""Impronte dei file dei dati, per far scaricare al telefono solo i file cambiati (8/11/2026).

Uso: python3 scripts/versioni.py
Scrive versioni.js nella cartella principale (Bologna) e in ogni cartella di città (milano/):
window.ACH_VERSIONI={"eventi":"<impronta>","serate":"…","mostre":"…","cinema":"…"}
La pagina carica versioni.js sempre fresco (è piccolissimo) e poi i file dei dati con ?h=<impronta>:
finché un file non cambia, il telefono usa la copia che ha già, senza riscaricarla.
Se versioni.js manca o è incompleto, la pagina torna al metodo di prima (numero che cambia ogni 10 minuti).
Dal 14/11/2026 scrive le impronte di eventi, serate e mostre anche dentro index.html e milano/index.html (marcatore /*V0*/):
il telefono chiede subito quei file senza aspettare versioni.js. Chi salva deve aggiungere anche i due index.html.
Lo lanciano i flussi che scrivono i dati (cinema, serate) e il flusso «Versioni dei dati» a ogni push.
"""
import hashlib
import json
import os
import re

FILE = ["eventi", "eventi-presto", "eventi-resto", "serate", "mostre", "cinema", "incontri", "sport"]
PRIMA = ["eventi", "eventi-presto", "serate", "mostre"]
GIORNI_PRESTO = 14   # 18/11/2026: all'apertura arrivano solo i prossimi 14 giorni (eventi-presto.js), il resto dopo   # dal 14/11/2026 le loro impronte stanno anche in index.html (marcatore /*V0*/…/*V0*/)
CARTELLE = [".", "milano", "ravenna", "ferrara"]


def impronta(percorso):
    with open(percorso, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()[:10]


def dividi_eventi(d):
    """18/11/2026: eventi.js resta il file vero (lo scrivono i flussi e il giro del lunedì). Da lì si ricavano
    eventi-presto.js (quello che si vede nei prossimi 14 giorni, arriva all'apertura) ed eventi-resto.js (tutto il
    resto, arriva a pagina già visibile). I due file insieme sono sempre esattamente eventi.js, qualunque giorno li si
    apra: la divisione cambia solo che cosa arriva prima. Riscritti solo se cambiano."""
    import datetime
    from zoneinfo import ZoneInfo
    src = os.path.join(d, "eventi.js")
    if not os.path.exists(src):
        return
    t = open(src, encoding="utf-8").read()
    try:
        dati = json.loads(t[t.index("{"):t.rindex("}") + 1])
    except Exception as e:
        print("eventi.js non leggibile, non divido:", d, e)
        return
    oggi = datetime.datetime.now(ZoneInfo("Europe/Rome")).date()
    a, b = oggi.isoformat(), (oggi + datetime.timedelta(days=GIORNI_PRESTO - 1)).isoformat()
    tutti = dati.get("eventi") or []
    presto = [e for e in tutti if isinstance(e, dict) and (e.get("data") or "") <= b and (e.get("fino") or e.get("data") or "") >= a]
    ids = {id(e) for e in presto}
    resto = [e for e in tutti if id(e) not in ids]
    testa = {k: v for k, v in dati.items() if k != "eventi"}
    uscite = {
        "eventi-presto.js": "window.EVENTI_DATA=" + json.dumps({**testa, "parziale": True, "fino_a": b, "eventi": presto},
                                                               ensure_ascii=False, separators=(",", ":")) + ";\n",
        "eventi-resto.js": "window.EVENTI_RESTO=" + json.dumps({**testa, "dal": a, "eventi": resto},
                                                               ensure_ascii=False, separators=(",", ":")) + ";\n",
    }
    for nome, testo in uscite.items():
        dest = os.path.join(d, nome)
        if not os.path.exists(dest) or open(dest, encoding="utf-8").read() != testo:
            with open(dest, "w", encoding="utf-8") as f:
                f.write(testo)
            print("diviso", os.path.relpath(dest, os.path.dirname(d)) if d != "." else nome, len(presto) if "presto" in nome else len(resto), "eventi")


def main():
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for c in CARTELLE:
        d = os.path.join(base, c)
        if not os.path.isdir(d):
            continue
        dividi_eventi(d)
        v = {f: impronta(os.path.join(d, f + ".js")) for f in FILE if os.path.exists(os.path.join(d, f + ".js"))}
        testo = "window.ACH_VERSIONI=" + json.dumps(v, separators=(",", ":")) + ";\n"
        dest = os.path.join(d, "versioni.js")
        vecchio = open(dest, encoding="utf-8").read() if os.path.exists(dest) else ""
        if testo != vecchio:
            with open(dest, "w", encoding="utf-8") as f:
                f.write(testo)
            print("aggiornato", os.path.relpath(dest, base), v)
        else:
            print("invariato", os.path.relpath(dest, base))
        pag = os.path.join(d, "index.html")
        if os.path.exists(pag):
            h = open(pag, encoding="utf-8").read()
            v0 = json.dumps({f: v[f] for f in PRIMA if f in v}, separators=(",", ":"))
            nuovo = re.sub(r"/\*V0\*/.*?/\*V0\*/", lambda m: "/*V0*/" + v0 + "/*V0*/", h, count=1)
            if nuovo != h:
                with open(pag, "w", encoding="utf-8") as f:
                    f.write(nuovo)
                print("impronte in pagina", os.path.relpath(pag, base), v0)


if __name__ == "__main__":
    main()
