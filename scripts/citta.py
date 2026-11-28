"""Genera le pagine delle altre città dall'unico index.html (Bologna).

Uso: python3 scripts/citta.py
Copia index.html in milano/index.html cambiando solo i testi statici (titolo, anteprima
per WhatsApp e motori di ricerca, titolo e sottotitolo). Tutto il resto (grafica, filtri,
funzioni) è identico: la città la sceglie la pagina stessa leggendo l'indirizzo.
I dati di ogni città stanno nella sua cartella: milano/eventi.js, milano/mostre.js, milano/cinema.js, milano/incontri.js.
"""
import os
import re

CITTA = {
    "milano": {
        "nome": "Milano",
        "area": "a Milano e nei grandi luoghi dell’area metropolitana",
        "meta": "Milano e area metropolitana",
        "url": "https://achevents.com/milano/",
    },
    "ravenna": {
        "nome": "Ravenna",
        "area": "a Ravenna e in tutta la provincia",
        "meta": "Ravenna e provincia",
        "url": "https://achevents.com/ravenna/",
    },
    "ferrara": {
        "nome": "Ferrara",
        "area": "a Ferrara e in tutta la provincia",
        "meta": "Ferrara e provincia",
        "url": "https://achevents.com/ferrara/",
    },
    # 28/11/2026: preparate (Stefano: «Preparati per inserire Modena Forlì e Firenze»); finché non sono in CITTA_ATTIVE
    # la pagina c'è ma non compare nel selettore né nella mappa del sito e dice ai motori di ricerca di non indicizzarla
    "modena": {
        "nome": "Modena",
        "area": "a Modena e in tutta la provincia",
        "meta": "Modena e provincia",
        "url": "https://achevents.com/modena/",
    },
    "forli-cesena": {
        "nome": "Forlì-Cesena",
        "area": "a Forlì, a Cesena e in tutta la provincia",
        "meta": "Forlì, Cesena e provincia",
        "url": "https://achevents.com/forli-cesena/",
    },
    "firenze": {
        "nome": "Firenze",
        "area": "a Firenze e in tutta la Città metropolitana",
        "meta": "Firenze e Città metropolitana",
        "url": "https://achevents.com/firenze/",
    },
}
VUOTI = {
    "eventi.js": 'window.EVENTI_DATA={"aggiornato":"","eventi":[]};\n',
    "mostre.js": 'window.MOSTRE_DATA={"aggiornato":"","mostre":[]};\n',
    "cinema.js": 'window.CINEMA_DATA={"aggiornato":"","giorno_orari":"","sale":[]};\n',
    "incontri.js": 'window.INCONTRI_DATA={"aggiornato":"","incontri":[]};\n',
    "sport.js": 'window.SPORT_DATA={"aggiornato":"","eventi":[]};\n',
    "serate.js": 'window.SERATE_DATA={"aggiornato":"","serate":[]};\n',
}


def main():
    base = open("index.html", encoding="utf-8").read()
    m = re.search(r"const CITTA_ATTIVE=\[([^\]]*)\]", base)
    attive_path = set(re.findall(r'"([a-z]{2})"', m.group(1))) if m else set()
    cartelle_attive = {p for k, p in re.findall(r'\b([a-z]{2}):\{k:"[a-z]{2}"[^}]*?path:"/([a-z-]+)/"', base) if k in attive_path}
    for cartella, c in CITTA.items():
        s = base
        for a, b in [
            ("concerti, teatro, mostre e cinema a Bologna", f"concerti, teatro, mostre e cinema a {c['nome']}"),
            ("a Bologna e nella Città metropolitana", f"a {c['meta']}"),
            ('<meta property="og:url" content="https://achevents.com/">', f'<meta property="og:url" content="{c["url"]}">'),
            # 18/11/2026: ogni città dice a Google qual è il suo indirizzo (i link delle lettere aggiungono ?ref=...)
            ('<link rel="canonical" href="https://achevents.com/">', f'<link rel="canonical" href="{c["url"]}">'),
            ("<h1>Eventi Bologna,", f"<h1>Eventi {c['nome']},"),
            ("a Bologna e nei comuni della Città metropolitana, nei prossimi 12 mesi.</p>", f"{c['area']}, nei prossimi 12 mesi.</p>"),
        ]:
            if a not in s:
                raise SystemExit(f"ERRORE: testo non trovato in index.html: {a}")
            s = s.replace(a, b)
        if cartella not in cartelle_attive:   # città preparata ma spenta: niente motori di ricerca
            s = s.replace("<head>", '<head>\n<meta name="robots" content="noindex">', 1)
        os.makedirs(cartella, exist_ok=True)
        open(os.path.join(cartella, "index.html"), "w", encoding="utf-8").write(s)
        for f, v in VUOTI.items():  # dati vuoti finché la città non è caricata
            p = os.path.join(cartella, f)
            if not os.path.exists(p):
                open(p, "w", encoding="utf-8").write(v)
        print(f"Scritta {cartella}/index.html")


if __name__ == "__main__":
    main()
