"""Genera le pagine delle altre città dall'unico index.html (Bologna).

Uso: python3 scripts/citta.py
Copia index.html in milano/index.html cambiando solo i testi statici (titolo, anteprima
per WhatsApp e motori di ricerca, titolo e sottotitolo). Tutto il resto (grafica, filtri,
funzioni) è identico: la città la sceglie la pagina stessa leggendo l'indirizzo.
I dati di ogni città stanno nella sua cartella: milano/eventi.js, milano/mostre.js, milano/cinema.js, milano/incontri.js.
"""
import os

CITTA = {
    "milano": {
        "nome": "Milano",
        "area": "a Milano e nei grandi luoghi dell’area metropolitana",
        "meta": "Milano e area metropolitana",
        "url": "https://achevents.com/milano/",
    },
}
VUOTI = {
    "eventi.js": 'window.EVENTI_DATA={"aggiornato":"","eventi":[]};\n',
    "mostre.js": 'window.MOSTRE_DATA={"aggiornato":"","mostre":[]};\n',
    "cinema.js": 'window.CINEMA_DATA={"aggiornato":"","giorno_orari":"","sale":[]};\n',
    "incontri.js": 'window.INCONTRI_DATA={"aggiornato":"","incontri":[]};\n',
}


def main():
    base = open("index.html", encoding="utf-8").read()
    for cartella, c in CITTA.items():
        s = base
        for a, b in [
            ("concerti, teatro, mostre e cinema a Bologna", f"concerti, teatro, mostre e cinema a {c['nome']}"),
            ("a Bologna e nella Città metropolitana", f"a {c['meta']}"),
            ('<meta property="og:url" content="https://achevents.com/">', f'<meta property="og:url" content="{c["url"]}">'),
            ("<h1>Eventi Bologna,", f"<h1>Eventi {c['nome']},"),
            ("a Bologna e nei comuni della Città metropolitana, nei prossimi 12 mesi.</p>", f"{c['area']}, nei prossimi 12 mesi.</p>"),
        ]:
            if a not in s:
                raise SystemExit(f"ERRORE: testo non trovato in index.html: {a}")
            s = s.replace(a, b)
        os.makedirs(cartella, exist_ok=True)
        open(os.path.join(cartella, "index.html"), "w", encoding="utf-8").write(s)
        for f, v in VUOTI.items():  # dati vuoti finché la città non è caricata
            p = os.path.join(cartella, f)
            if not os.path.exists(p):
                open(p, "w", encoding="utf-8").write(v)
        print(f"Scritta {cartella}/index.html")


if __name__ == "__main__":
    main()
