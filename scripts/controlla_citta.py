"""Controllo delle città di Events: ogni città accesa è collegata dappertutto? (18/11/2026)

Uso: python3 scripts/controlla_citta.py [CARTELLA_DEL_REPOSITORY]
Esce con 1 se una città accesa non funzionerebbe (errore); gli avvisi (fonti che mancano) non fermano.

Perché: una città nuova si accende in un punto solo (CITTA_ATTIVE in index.html), ma per funzionare deve essere
scritta in una dozzina di file. Se se ne dimentica uno la città compare nel selettore e resta vuota, o non si
aggiorna più, senza che nessuno se ne accorga. Questo controllo gira:
  - nel flusso «Pagine delle città» (citta.yml) a ogni modifica di index.html: se fallisce GitHub manda un'email;
  - nella «Verifica delle guide» di ogni mattina (scripts/verifica.py, vista «Città di Events»).
Le prove che prenda davvero gli errori sono in scripts/prova_verifica.py.
L'elenco dei passi per aprire una provincia è in coordinamento/eventi/PROCEDURA.md (repository privato),
sezione «Aprire una provincia nuova».
"""
import json
import os
import re
import sys

# file di dati che la pagina di ogni città carica: se mancano la pagina resta bianca
DATI_PAGINA = ["index.html", "eventi.js", "eventi-presto.js", "eventi-resto.js", "mostre.js", "cinema.js", "incontri.js", "sport.js", "serate.js", "versioni.js"]
# flussi che salvano i dati della città: se la città non c'è, i suoi dati non si aggiornano più
FLUSSI_DATI = {"eventi_auto.yml": "eventi e mostre automatici", "incontri.yml": "incontri", "cinema.yml": "cinema",
               "protagonisti.yml": "protagonisti"}
MINIMO = 5   # eventi sotto i quali una città accesa è da considerare vuota (come «minimo» in citta_cfg.py)


def _leggi(rad, *p):
    f = os.path.join(rad, *p)
    return open(f, encoding="utf-8").read() if os.path.exists(f) else ""


def citta_attive(index):
    m = re.search(r"const CITTA_ATTIVE=\[([^\]]*)\]", index)
    return re.findall(r'"([a-z]{2})"', m.group(1)) if m else []


def cartella_di(index, k):
    m = re.search(r"\b" + k + r':\{k:"' + k + r'"[^}]*?path:"/([a-z-]+)/"', index)
    return m.group(1) if m else None


def controlla(rad="."):
    """Restituisce [(livello, città, che cosa)]; livello «errore» o «avviso». Lista vuota = tutto a posto."""
    out = []
    index = _leggi(rad, "index.html")
    att = citta_attive(index)
    if not att:
        return [("errore", "-", "index.html: CITTA_ATTIVE non trovato")]
    if "bo" not in att:
        out.append(("errore", "bo", "Bologna non è fra le città attive"))
    citta_py = _leggi(rad, "scripts", "citta.py")
    cfg = _leggi(rad, "scripts", "citta_cfg.py")
    versioni = _leggi(rad, "scripts", "versioni.py")
    salva = _leggi(rad, "scripts", "salva.sh")
    cartelloni = _leggi(rad, "scripts", "cartelloni.py")
    verifica = _leggi(rad, "scripts", "verifica.py")
    wf = {f: _leggi(rad, ".github", "workflows", f) for f in ["citta.yml", "versioni.yml", *FLUSSI_DATI]}
    try:
        sent = json.loads(_leggi(rad, "dati", "sentinella.json") or "{}").get("pagine", [])
    except ValueError:
        sent = []
        out.append(("errore", "-", "dati/sentinella.json non si legge"))
    m = re.search(r"var P=\{([^}]*)\}", index)
    cookie = re.findall(r"([a-z]{2}):\"/", m.group(1)) if m else []

    for k in att:
        if k == "bo":
            continue
        c = cartella_di(index, k)
        if not c:
            out.append(("errore", k, "index.html: manca la città in CITTA_CFG (con path)"))
            continue
        nome = c.capitalize()

        def err(cosa): out.append(("errore", nome, cosa))
        def avv(cosa): out.append(("avviso", nome, cosa))

        if k not in cookie:
            err("index.html: manca nel ritorno all'ultima città scelta (var P in testa alla pagina)")
        if f'"{c}"' not in citta_py:
            err("scripts/citta.py: manca in CITTA (la pagina della città non viene rigenerata)")
        if k != "mi" and f'"{k}"' not in cfg:
            err("scripts/citta_cfg.py: manca il perimetro (zone e comuni)")
        if f'"{c}"' not in versioni:
            err("scripts/versioni.py: manca in CARTELLE (i dati nuovi non arrivano a chi ha già aperto la pagina)")
        if f"{c}/index.html" not in salva:
            err("scripts/salva.sh: manca fra i file fissi")
        if f"git add" not in wf["citta.yml"] or not re.search(r"git add[^\n]*\b" + c + r"\b", wf["citta.yml"]):
            err("citta.yml: la pagina della città non viene salvata")
        if f"{c}/*.js" not in wf["versioni.yml"] and f"{c}/eventi.js" not in wf["versioni.yml"]:
            err("versioni.yml: manca il percorso dei dati della città")
        for f, cosa in FLUSSI_DATI.items():
            if f"{c}/" not in wf[f]:
                err(f"{f}: {cosa} della città non vengono salvati")
        for f in DATI_PAGINA:
            if not os.path.exists(os.path.join(rad, c, f)):
                err(f"manca il file {c}/{f}")
        ev = _leggi(rad, c, "eventi.js")
        if ev:
            try:
                n = len(json.loads(ev[ev.index("=") + 1:].rstrip().rstrip(";")).get("eventi", []))
                if n < MINIMO:
                    err(f"{c}/eventi.js ha {n} eventi: la città è accesa ma vuota")
            except ValueError:
                err(f"{c}/eventi.js non si legge")
        if not re.search(r'"' + nome + r'"', verifica):
            err("scripts/verifica.py: la città non è nei controlli dei dati di ogni mattina")
        # fonti: senza, la città va avanti solo con i flussi automatici (DICE, arte.it, Ticketmaster, portali)
        if f'"{k}"' not in cartelloni:
            avv("scripts/cartelloni.py: manca in CITTA (niente TicketOne né cartelloni dei teatri la domenica)")
        car = _leggi(rad, ".github", "workflows", "cartelloni.yml")
        if not re.search(r"inputs\.citta \|\| '[^']*\b" + k + r"\b", car) or f"{c}/eventi.js" not in car:
            avv("cartelloni.yml: la città non è nel giro della domenica (o i suoi link TicketOne non vengono salvati)")
        if not any(p.get("citta") == k for p in sent):
            avv("dati/sentinella.json: nessuna pagina di teatri o locali da sorvegliare")

    # al contrario: città preparate ma non accese (normale mentre si prepara, da non dimenticare)
    for c in re.findall(r'^    "([a-z-]+)": \{', citta_py, re.M):
        if not any(cartella_di(index, k) == c for k in att):
            out.append(("avviso", c.capitalize(), "preparata in scripts/citta.py ma non accesa in CITTA_ATTIVE"))
    return out


def main():
    rad = sys.argv[1] if len(sys.argv) > 1 else "."
    r = controlla(rad)
    att = citta_attive(_leggi(rad, "index.html"))
    print("Città attive:", ", ".join(att))
    for liv, c, cosa in r:
        print(f"{liv.upper():7} {c}: {cosa}")
    if not r:
        print("Tutte le città attive sono collegate dappertutto.")
    sys.exit(1 if any(liv == "errore" for liv, _, _ in r) else 0)


if __name__ == "__main__":
    main()
