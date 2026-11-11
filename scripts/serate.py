"""Serate nei club (Bologna e Milano) dai calendari mensili di technoairlines.com.

Uso: python3 scripts/serate.py            (scarica e scrive serate.js e milano/serate.js)
     python3 scripts/serate.py --file X.html bo   (prova su una pagina già scaricata)

Fonte: https://www.technoairlines.com/events/<bologna|milan>/AAAA-MM (permesse dal robots.txt,
che consente esplicitamente anche ClaudeBot/Claude-User). Ogni pagina ha l'elenco completo in HTML
(titolo, locale, ora; la data è in fondo all'indirizzo della serata) e i dati strutturati
(schema.org MusicEvent) per una parte delle serate: da questi prendiamo artisti e link ai biglietti
(Resident Advisor). Si leggono il mese in corso e i due successivi, una pagina ogni 2 secondi.

Scrive window.SERATE_DATA={"aggiornato","fonte","serate":[...]} con lo stesso formato degli
eventi (genere "Serate e club"): la pagina le unisce agli spettacoli e salta quelle già presenti
(stesso giorno e stesso locale). Non tocca eventi.js.
"""
import datetime, html, json, re, sys, time, urllib.request

UA = "AchEventsGuide/1.0 (+https://achevents.com)"
CITTA = {"bo": ("bologna", "Bologna", "serate.js"), "mi": ("milan", "Milano", "milano/serate.js")}
SCARTA_LUOGHI = re.compile(r"^(tba|secret location.*|unnamed.*|location segreta.*)$", re.I)
# nomi dei locali come li scriviamo già nel sito
RINOMINA = {"Dumbo": "DumBO", "DURO": "Duro", "Apollo Club": "Apollo Milano", "BIKO": "Biko", "Tunnel": "Tunnel Club",
            "Kindergarten": "Kindergarten Club", "Alcatraz Milano": "Alcatraz", "Circolo Masada + Circolo Amelia": "Masada"}
# locali fuori città che conosciamo (il resto della pagina "milan" è Milano città)
COMUNE = {"Circolo Magnolia": "Segrate", "Bagno Mundial": "Bologna"}


def scarica(url):
    r = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html"})
    return urllib.request.urlopen(r, timeout=30).read().decode("utf-8", "replace")


def dati_strutturati(t):
    """url della serata -> MusicEvent dei dati schema.org della pagina."""
    out = {}
    for m in re.finditer(r'<script type="application/ld\+json"[^>]*>(.*?)</script>', t, re.S):
        try:
            d = json.loads(m.group(1))
        except Exception:
            continue
        if isinstance(d, dict) and d.get("@type") == "ItemList":
            for x in d.get("itemListElement", []):
                it = x.get("item") or {}
                if it.get("url"): out[it["url"]] = it
    return out


def leggi_pagina(t, chiave):
    _, capo, _ = CITTA[chiave]
    ld = dati_strutturati(t)
    righe = []
    for url, titolo, small in re.findall(r'<a class="tev-tt" href="(https://www\.technoairlines\.com/event/[^"]+)">(.*?)</a><small>(.*?)</small>', t):
        m = re.search(r"(\d{4}-\d{2}-\d{2})/?$", url)
        if not m: continue
        data = m.group(1)
        small = html.unescape(re.sub(r"<[^>]+>", "", small)).strip()
        mo = re.match(r"^(.*?)(?: · (\d{2}:\d{2}))?$", small)
        luogo, ora = (mo.group(1).strip(), mo.group(2) or "n.d.") if mo else (small, "n.d.")
        if not luogo or SCARTA_LUOGHI.match(luogo): continue
        titolo = html.unescape(re.sub(r"<[^>]+>", "", titolo)).strip()
        if not titolo or SCARTA_LUOGHI.match(titolo): continue  # titolo ancora "TBA"
        luogo = RINOMINA.get(luogo, luogo)
        e = ld.get(url, {})
        artisti = [p.get("name", "").strip() for p in (e.get("performer") or []) if isinstance(p, dict) and p.get("name")]
        artisti = [a for a in artisti if a.lower() not in titolo.lower()][:4]
        bigl = (e.get("offers") or {}).get("url", "") if isinstance(e.get("offers"), dict) else ""
        if "awin1.com/" in bigl or re.match(r"^https?://[^/]+/?$", bigl):   # link affiliato di altri o pagina iniziale: non porta alla serata
            bigl = ""
        loc = ((e.get("location") or {}).get("address") or {}).get("addressLocality", "")
        citta = COMUNE.get(luogo) or (capo if loc in ("", "Bologna", "Milan", "Milano") else loc)
        desc = "Serata di musica elettronica" + (f" con {', '.join(artisti)}" if artisti else "") + "."
        if ora != "n.d." and ora < "17:00" and ora >= "05:00": desc = desc.replace("Serata", "Evento diurno", 1)
        righe.append({"id": "", "data": data, "fino": data, "ora": ora, "artista": titolo, "luogo": luogo, "citta": citta,
                      "genere": "Serate e club", "tipo": "", "rassegna": "", "descrizione": desc,
                      "fonte": url, "biglietti": bigl or url, "biglietti_tipo": "Acquista" if bigl else "Info",
                      "disp": "da verificare", "disp_nota": "", "disp_verificata": "", "sito_luogo": ""})
    return righe


def mesi(n=3):
    d = datetime.date.today().replace(day=1)
    for _ in range(n):
        yield d.strftime("%Y-%m")
        d = (d + datetime.timedelta(days=32)).replace(day=1)


def scrivi(chiave, righe):
    _, capo, file = CITTA[chiave]
    oggi = datetime.date.today().isoformat()
    vis, out = set(), []
    for r in sorted(righe, key=lambda r: (r["data"], r["ora"], r["luogo"])):
        k = r["fonte"]
        if k in vis or r["data"] < oggi: continue
        vis.add(k); out.append(r)
    pref = "s" + chiave
    for i, r in enumerate(out, 1): r["id"] = f"{pref}{i:03d}"
    d = {"aggiornato": oggi, "fonte": "technoairlines.com", "serate": out}
    open(file, "w", encoding="utf-8").write("window.SERATE_DATA=" + json.dumps(d, ensure_ascii=False, separators=(",", ":")) + ";\n")
    luoghi = len({r["luogo"] for r in out})
    print(f"{capo}: {len(out)} serate in {luoghi} locali -> {file}")
    return out


def main():
    if "--file" in sys.argv:
        i = sys.argv.index("--file"); t = open(sys.argv[i + 1], encoding="utf-8").read(); ch = sys.argv[i + 2]
        for r in leggi_pagina(t, ch)[:5]: print(r)
        print(len(leggi_pagina(t, ch)), "serate"); return
    errori = 0
    for ch, (slug, capo, file) in CITTA.items():
        righe, lette = [], 0
        for m in mesi():
            url = f"https://www.technoairlines.com/events/{slug}/{m}"
            try:
                righe += leggi_pagina(scarica(url), ch); lette += 1
            except Exception as ex:
                print("errore", url, ex); errori += 1
            time.sleep(2)
        if lette == 0:
            print(f"{capo}: nessuna pagina letta, lascio il file com'è"); continue
        if not righe:
            print(f"{capo}: zero serate (pagina cambiata?), lascio il file com'è"); errori += 1; continue
        scrivi(ch, righe)
    sys.exit(1 if errori else 0)


if __name__ == "__main__":
    main()
