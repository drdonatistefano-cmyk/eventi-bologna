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

FILE = ["eventi", "serate", "mostre", "cinema", "incontri", "sport"]
PRIMA = ["eventi", "serate", "mostre"]   # dal 14/11/2026 le loro impronte stanno anche in index.html (marcatore /*V0*/…/*V0*/)
CARTELLE = [".", "milano"]


def impronta(percorso):
    with open(percorso, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()[:10]


def main():
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for c in CARTELLE:
        d = os.path.join(base, c)
        if not os.path.isdir(d):
            continue
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
