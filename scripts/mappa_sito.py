"""robots.txt e sitemap.xml di achevents.com (18/11/2026, lavoro SEO approvato da Stefano).

Uso: python3 scripts/mappa_sito.py   (lo lancia il flusso «Pagine delle città» dopo scripts/citta.py)
La mappa elenca la pagina di Bologna, le pagine delle città accese (CITTA_ATTIVE in index.html) e le pagine fisse.
Non ci vanno le pagine di servizio (statistiche, velocità: hanno noindex) né la pagina per l'app.
Riscrive i file solo se il contenuto cambia, così una pubblicazione normale non li tocca.
"""
import json
import os
import re
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import citta_cfg as _CC  # noqa: E402  (28/11/2026: elenco unico delle città)

SITO = "https://achevents.com/"
CARTELLE = {k: (c + "/" if c else "") for k, (n, c) in _CC.TUTTE.items()}
FISSE = ["collaborano/", "chi-siamo/", "privacy/"]


def scrivi(nome, testo):
    if os.path.exists(nome) and open(nome, encoding="utf-8").read() == testo:
        return False
    open(nome, "w", encoding="utf-8").write(testo)
    return True


def main():
    pagina = open("index.html", encoding="utf-8").read()
    m = re.search(r"CITTA_ATTIVE=\[([^\]]*)\]", pagina)
    attive = re.findall(r'"([a-z]+)"', m.group(1)) if m else ["bo"]
    indirizzi = [SITO + CARTELLE[k] for k in attive if k in CARTELLE and os.path.exists(os.path.join(CARTELLE[k] or ".", "index.html"))]
    indirizzi += [SITO + p for p in FISSE if os.path.exists(os.path.join(p, "index.html"))]
    # 18/11/2026: le pagine dei singoli spettacoli (scripts/pagine_eventi.py), dall'elenco che il generatore lascia
    if os.path.exists(os.path.join("evento", "elenco.json")):
        indirizzi += [f"{SITO}evento/{v['nome']}/" for v in json.load(open(os.path.join("evento", "elenco.json"), encoding="utf-8"))
                      if os.path.exists(os.path.join("evento", v["nome"], "index.html"))]
    mappa = ('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
             + "".join(f"<url><loc>{u}</loc></url>\n" for u in indirizzi) + "</urlset>\n")
    robots = f"User-agent: *\nAllow: /\n\nSitemap: {SITO}sitemap.xml\n"
    a, b = scrivi("sitemap.xml", mappa), scrivi("robots.txt", robots)
    print(f"mappa del sito: {len(indirizzi)} pagine ({'riscritta' if a else 'invariata'}); robots.txt {'riscritto' if b else 'invariato'}")


if __name__ == "__main__":
    main()
