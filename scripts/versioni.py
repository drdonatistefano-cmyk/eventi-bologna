"""Impronte dei file dei dati, per far scaricare al telefono solo i file cambiati (8/11/2026).

Uso: python3 scripts/versioni.py
Scrive versioni.js nella cartella principale (Bologna) e in ogni cartella di città (milano/):
window.ACH_VERSIONI={"eventi":"<impronta>","serate":"…","mostre":"…","cinema":"…"}
La pagina carica versioni.js sempre fresco (è piccolissimo) e poi i file dei dati con ?h=<impronta>:
finché un file non cambia, il telefono usa la copia che ha già, senza riscaricarla.
Se versioni.js manca o è incompleto, la pagina torna al metodo di prima (numero che cambia ogni 10 minuti).
Lo lanciano i flussi che scrivono i dati (cinema, serate) e il flusso «Versioni dei dati» a ogni push.
"""
import hashlib
import json
import os

FILE = ["eventi", "serate", "mostre", "cinema", "incontri", "sport"]
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


if __name__ == "__main__":
    main()
