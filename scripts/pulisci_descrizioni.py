"""Ripulisce le descrizioni sporche già in guida (23/11/2026).

Stefano alla chat di Events: «usa cobra per cercare descrizioni, link sbagliati da correggere ed ogni azione necessaria
per migliorare il sito». Nelle schede c'erano pezzi di pagina presi così com'erano (il menu dell'Ecoteatro, intestazioni
«TITOLO | LOCALE | DATA | ORE», telefoni ed email, frasi tagliate a metà). La regola è regole_auto.pulisci_descrizione,
la stessa che dal 23/11 usa il giro automatico: qui si applica una volta alle schede già in guida.
Se della descrizione non resta una frase vera si scrive la frase generica del giro automatico («Spettacolo al …»).

Uso: python3 scripts/pulisci_descrizioni.py            mostra che cosa cambierebbe
     python3 scripts/pulisci_descrizioni.py --applica  scrive eventi.js delle quattro città (poi: python3 scripts/versioni.py)
"""
import json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import citta_cfg as _CC  # noqa: E402  (28/11/2026: elenco unico delle città)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import regole_auto as RA  # noqa: E402

RADICE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CITTA = [c for n, c in _CC.TUTTE.values()]   # 28/11/2026: tutte le città
GENERICA = {"Serate e club": "Serata nel club {l}.", "Teatro": "{t} {al}{l}.", "Classica": "Concerto di musica classica {al}{l}.",
            "Jazz": "Concerto jazz {al}{l}.", "Rock": "Concerto rock {al}{l}."}


def generica(e):
    l = e.get("luogo") or ""
    al = "all'" if re.match(r"(?i)[aeiou]", l) else "al "
    return GENERICA.get(e.get("genere"), "Concerto dal vivo {al}{l}.").format(l=l, al=al, t=e.get("tipo") or "Spettacolo")


def pulisci(eventi):
    cambiate = []
    for e in eventi:
        t = e.get("descrizione") or ""
        if not t or not RA.sporca(t):
            continue
        n = RA.pulisci_descrizione(t, e.get("artista", ""), e.get("luogo", "")) or generica(e)
        if n != t:
            cambiate.append((e["id"], t, n))
            e["descrizione"] = n
    return cambiate


def main(a):
    tot = 0
    for c in CITTA:
        p = os.path.join(RADICE, c, "eventi.js")
        if not os.path.exists(p):
            continue
        s = open(p, encoding="utf-8").read()
        dati = json.loads(s[s.index("=") + 1:].rstrip().rstrip(";"))
        ch = pulisci(dati["eventi"])
        tot += len(ch)
        for i, t, n in ch:
            print(f"{c or 'bologna'} {i}: {t[:90]!r}\n    → {n!r}")
        if "--applica" in a and ch:
            blob = json.dumps(dati, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
            open(p, "w", encoding="utf-8").write("window.EVENTI_DATA=" + blob + ";\n")
    print(f"descrizioni {'ripulite' if '--applica' in a else 'da ripulire'}: {tot}")


if __name__ == "__main__":
    main(sys.argv[1:])
