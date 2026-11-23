"""Una pagina per ogni spettacolo di Events, con i dati strutturati «Event» per Google (18/11/2026, prototipo).

Google mostra gli eventi nei suoi risultati «Eventi» solo se ogni evento ha una pagina sua («a unique URL, a leaf
page») con nome, data d'inizio e luogo con indirizzo. La guida è una pagina sola: queste pagine la affiancano, non la
sostituiscono, e portano alla guida.

Uso: python3 scripts/pagine_eventi.py [--prova DIR]   (--prova scrive in un'altra cartella, per le anteprime)
Legge eventi.js delle città accese (CITTA_ATTIVE in index.html) e dati/indirizzi_luoghi.json (OpenStreetMap).
Scrive evento/<città>-<id>-<nome>/index.html e evento/elenco.json (l'elenco che usa la mappa del sito).
Riscrive una pagina solo se cambia; toglie le pagine degli eventi finiti da più di 3 giorni o spariti dai dati.
Regole: mai dati Google; i link partner si dichiarano (REGOLE 8 ter); testi presi dai dati della guida, nient'altro.
"""
import datetime
import html
import json
import os
import re
import shutil
import sys
import unicodedata
import urllib.parse
from zoneinfo import ZoneInfo

RADICE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITO = "https://achevents.com"
ROMA = ZoneInfo("Europe/Rome")
CARTELLE = {"bo": "", "mi": "milano", "ra": "ravenna", "fe": "ferrara"}
NOMI = {"bo": "Bologna", "mi": "Milano", "ra": "Ravenna", "fe": "Ferrara"}
# stesse affiliazioni della guida (index.html, AFF): 0 = programma non approvato, link invariato
AWIN, MID = "3146807", {"ticketone.it": 9567, "tiqets.com": 12427}
MARGINE_GIORNI = 3
e = lambda s: html.escape(str(s or ""), quote=True)  # noqa: E731


def slug(s, n=60):
    s = unicodedata.normalize("NFD", str(s or "").lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:n].strip("-") or "evento"


def leggi_js(p):
    t = open(p, encoding="utf-8").read()
    return json.loads(t[t.index("{"):t.rindex("}") + 1])


def citta_attive():
    m = re.search(r"CITTA_ATTIVE=\[([^\]]*)\]", open(os.path.join(RADICE, "index.html"), encoding="utf-8").read())
    return re.findall(r'"([a-z]+)"', m.group(1)) if m else ["bo"]


def aff(u):
    try:
        h = urllib.parse.urlparse(u).hostname or ""
    except ValueError:
        return u, False
    h = h[4:] if h.startswith("www.") else h
    for d, mid in MID.items():
        if mid and (h == d or h.endswith("." + d)):
            return f"https://www.awin1.com/cread.php?awinmid={mid}&awinaffid={AWIN}&ued={urllib.parse.quote(u, safe='')}", True
    return u, False


ORA = re.compile(r"^\s*(\d{1,2})[:.](\d{2})\s*$")


def inizio(ev):
    """ISO-8601 con fuso orario se c'è un solo orario certo; solo la data se gli orari sono più d'uno o mancano
    (Google: «Don't indicate the time if you don't know the time»)."""
    m = ORA.match(ev.get("ora") or "")
    if not m:
        return ev["data"]
    d = datetime.datetime.fromisoformat(f"{ev['data']}T{int(m[1]):02d}:{m[2]}:00").replace(tzinfo=ROMA)
    return d.isoformat()


def prezzo(ev):
    m = re.search(r"da\s+(\d+(?:[.,]\d+)?)\s*€", ev.get("disp_nota") or "")
    return float(m[1].replace(",", ".")) if m else None


def data_it(s):
    mesi = "gennaio febbraio marzo aprile maggio giugno luglio agosto settembre ottobre novembre dicembre".split()
    giorni = "lunedì martedì mercoledì giovedì venerdì sabato domenica".split()
    d = datetime.date.fromisoformat(s)
    return f"{giorni[d.weekday()]} {d.day} {mesi[d.month - 1]} {d.year}"


CSS = (":root{--bg:#f6efe4;--ink:#231d18;--mute:#7a6f63;--line:#e8ddcc;--acc:#2f4d68}*{box-sizing:border-box}"
       "body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.65 Georgia,'Iowan Old Style',serif}"
       ".w{max-width:760px;margin:0 auto;padding:0 20px}header.top{border-bottom:1px solid var(--line);padding:14px 0;margin-bottom:28px}"
       "header.top .w{display:flex;flex-wrap:wrap;gap:10px 18px;align-items:baseline}.marchio{font-weight:700;color:var(--ink);text-decoration:none}"
       "nav.guide{margin-left:auto;display:flex;gap:14px;font-size:14px}nav.guide a{color:var(--mute);text-decoration:none}"
       ".briciole{font-size:14px;color:var(--mute)}.briciole a{color:var(--mute)}h1{font-size:30px;line-height:1.25;margin:0 0 6px}"
       "h2{font-size:21px;margin:30px 0 6px}.quando{font-size:19px;margin:0 0 4px}.dove{margin:0 0 18px;color:#3b3833}"
       ".tag{display:inline-block;font:13px system-ui,sans-serif;border:1px solid var(--line);border-radius:999px;padding:2px 10px;margin:0 6px 6px 0;color:var(--mute)}"
       ".btn{display:inline-block;background:var(--acc);color:#fff;text-decoration:none;border-radius:10px;padding:11px 18px;"
       "font:600 16px system-ui,sans-serif;margin:10px 10px 4px 0}.btn.sec{background:transparent;color:var(--acc);border:1px solid var(--acc)}"
       ".nota{font-size:13px;color:var(--mute)}ul.altri{padding-left:18px}a{color:var(--acc)}"
       "footer{border-top:1px solid var(--line);margin-top:40px;padding:18px 0;font-size:14px;color:var(--mute)}footer a{color:var(--mute)}")


def pagina(k, ev, ind, altri, url):
    citta = ev.get("citta") or NOMI[k]
    titolo = f"{ev['artista']} a {citta}, {data_it(ev['data'])}"
    if len(titolo) > 62:
        titolo = f"{ev['artista']} a {citta}"
    descr = (ev.get("descrizione") or f"{ev['artista']} al {ev.get('luogo', '')}, {citta}.").strip()
    descr = descr if len(descr) <= 160 else descr[:157].rsplit(" ", 1)[0] + "…"
    guida = f"{SITO}/{CARTELLE[k] + '/' if CARTELLE[k] else ''}?cerca={urllib.parse.quote(ev['artista'][:60])}"
    quando = data_it(ev["data"]) + (f" – {data_it(ev['fino'])}" if ev.get("fino") and ev["fino"] != ev["data"] else "")
    indirizzo = f"{ind['via']} {ind['civico']}, {ind.get('cap', '')} {ind['comune']}".replace("  ", " ") if ind else ""
    corpo = [f'<p class="briciole"><a href="/">Ach\'s Events Guide</a> › <a href="/{CARTELLE[k] + "/" if CARTELLE[k] else ""}">{e(NOMI[k])}</a> › {e(ev.get("genere") or "Spettacoli")}</p>',
             f"<h1>{e(ev['artista'])}</h1>",
             f'<p class="quando">{e(quando)}{" · ore " + e(ev["ora"]) if re.search(r"\\d", ev.get("ora") or "") else ""}</p>',
             f'<p class="dove"><b>{e(ev.get("luogo"))}</b>, {e(citta)}' + (f"<br>{e(indirizzo)}" if indirizzo else "") + "</p>"]
    corpo.append("<p>" + "".join(f'<span class="tag">{e(x)}</span>' for x in (ev.get("genere"), ev.get("tipo"), ev.get("rassegna")) if x) + "</p>")
    if ev.get("descrizione"):
        corpo.append(f"<p>{e(ev['descrizione'])}</p>")
    if ev.get("chi"):
        corpo.append(f"<p>Con {e(ev['chi'])}.</p>")
    bt, partner = (aff(ev["biglietti"]) if ev.get("biglietti") else ("", False))
    if bt and ev.get("disp") != "esaurito":
        dom = (urllib.parse.urlparse(ev["biglietti"]).hostname or "").replace("www.", "")
        corpo.append(f'<p><a class="btn" href="{e(bt)}" rel="{"sponsored noopener" if partner else "noopener"}" target="_blank">🎟️ Biglietti</a>'
                     f'<a class="btn sec" href="{e(guida)}">Vedi nella guida</a></p>'
                     f'<p class="nota">Biglietti su {e(dom)}' + (" · partner: la guida riceve una piccola commissione, il prezzo per te non cambia" if partner else "")
                     + (f" · {e(ev['disp_nota'])}" if ev.get("disp_nota") else "") + "</p>")
    else:
        corpo.append(f'<p>{"<b>Esaurito.</b> " if ev.get("disp") == "esaurito" else ""}<a class="btn sec" href="{e(guida)}">Vedi nella guida</a></p>')
    if ind and ind.get("lat"):
        corpo.append(f'<p><a href="https://www.openstreetmap.org/?mlat={ind["lat"]}&amp;mlon={ind["lon"]}#map=17/{ind["lat"]}/{ind["lon"]}" rel="noopener" target="_blank">Come arrivare (mappa)</a></p>')
    if altri:
        corpo.append(f"<h2>Dopo, nello stesso luogo</h2><ul class=\"altri\">" + "".join(
            f'<li><a href="/evento/{e(a_url)}/">{e(a["artista"])}</a> · {e(data_it(a["data"]))}</li>' for a, a_url in altri[:8]) + "</ul>")
    ld = None
    if ind:
        ld = {"@context": "https://schema.org", "@type": "Event", "name": ev["artista"], "startDate": inizio(ev),
              "eventStatus": "https://schema.org/EventScheduled", "eventAttendanceMode": "https://schema.org/OfflineEventAttendanceMode",
              "location": {"@type": "Place", "name": ev.get("luogo"),
                           "address": {"@type": "PostalAddress", "streetAddress": f"{ind['via']} {ind['civico']}",
                                       "addressLocality": ind["comune"], "postalCode": ind.get("cap") or None, "addressCountry": "IT"}},
              "description": ev.get("descrizione") or None, "url": url}
        if ev.get("fino") and ev["fino"] != ev["data"]:
            ld["endDate"] = ev["fino"]
        if ev.get("chi"):
            ld["performer"] = {"@type": "PerformingGroup", "name": ev["chi"]}
        if ev.get("biglietti"):
            of = {"@type": "Offer", "url": ev["biglietti"],
                  "availability": "https://schema.org/SoldOut" if ev.get("disp") == "esaurito" else "https://schema.org/InStock"}
            p = prezzo(ev)
            if p is not None:
                of.update(price=p, priceCurrency="EUR")
            ld["offers"] = of
        ld = {a: b for a, b in ld.items() if b is not None}
        ld["location"]["address"] = {a: b for a, b in ld["location"]["address"].items() if b}
    piede = ('<footer><div class="w"><p>Le informazioni vengono dai programmi ufficiali dei luoghi e degli organizzatori: '
             'prima di andare conviene controllare sul sito del luogo.'
             + (" Indirizzo © <a href=\"https://www.openstreetmap.org/copyright\">OpenStreetMap contributors</a>." if ind and str(ind.get("fonte", "")).startswith("OpenStreetMap") else "")
             + '</p><p><a href="/">Tutti gli spettacoli nella guida</a> · <a href="/chi-siamo/">Chi siamo</a> · <a href="/privacy/">Privacy</a></p></div></footer>')
    script_ld = f'<script type="application/ld+json">{json.dumps(ld, ensure_ascii=False, separators=(",", ":"))}</script>' if ld else ""
    return ("<!doctype html><html lang=\"it\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
            f"<title>{e(titolo)}</title><meta name=\"description\" content=\"{e(descr)}\"><link rel=\"canonical\" href=\"{e(url)}\">"
            f"<meta property=\"og:title\" content=\"{e(titolo)}\"><meta property=\"og:description\" content=\"{e(descr)}\">"
            f"<meta property=\"og:url\" content=\"{e(url)}\"><meta property=\"og:type\" content=\"website\"><meta property=\"og:site_name\" content=\"Ach's Events Guide\">"
            f"<meta property=\"og:image\" content=\"{SITO}/anteprima.png\"><link rel=\"stylesheet\" href=\"/evento/pagine.css\">{script_ld}"
            '<script data-goatcounter="https://eventibologna.goatcounter.com/count" async src="//gc.zgo.at/count.js"></script></head>'
            '<body><header class="top"><div class="w"><a class="marchio" href="/">Ach\'s Events Guide</a><nav class="guide" aria-label="Le guide di Ach">'
            '<a href="https://achplaces.com">Luoghi</a><a href="https://achdinners.com">Ristoranti</a><a href="https://achevents.com">Eventi</a><a href="https://achdishes.com">Ricette</a></nav></div></header>'
            '<main class="w">' + "".join(corpo) + "</main>" + piede + "</body></html>\n")


def main():
    base = sys.argv[sys.argv.index("--prova") + 1] if "--prova" in sys.argv else RADICE
    oggi = datetime.datetime.now(ROMA).date()
    limite = (oggi - datetime.timedelta(days=MARGINE_GIORNI)).isoformat()
    ip = os.path.join(RADICE, "dati", "indirizzi_luoghi.json")
    indirizzi = json.load(open(ip, encoding="utf-8")) if os.path.exists(ip) else {}
    voci, scritte, con_dati = [], 0, 0
    for k in citta_attive():
        if k not in CARTELLE:
            continue
        p = os.path.join(RADICE, CARTELLE[k], "eventi.js")
        if not os.path.exists(p):
            continue
        evs = [x for x in leggi_js(p).get("eventi", []) if x.get("id") and x.get("artista") and re.match(r"\d{4}-\d\d-\d\d$", x.get("data") or "")
               and (x.get("fino") or x["data"]) >= limite]
        evs.sort(key=lambda x: (x["data"], x.get("ora") or ""))
        nomi = {id(x): f"{k}-{slug(x['id'], 12)}-{slug(x['artista'])}" for x in evs}
        per_luogo = {}
        for x in evs:
            per_luogo.setdefault(x.get("luogo"), []).append(x)
        for x in evs:
            nome = nomi[id(x)]
            url = f"{SITO}/evento/{nome}/"
            ind = indirizzi.get(f"{x.get('luogo')}|{x.get('citta') or ''}")
            # gli spettacoli che vengono DOPO questo, nello stesso luogo: l'elenco non cambia col passare dei giorni,
            # così una pagina si riscrive solo quando cambiano i dati (la storia del repository non cresce ogni notte)
            altri = [(a, nomi[id(a)]) for a in per_luogo.get(x.get("luogo"), []) if a is not x and (a["data"], a.get("ora") or "") > (x["data"], x.get("ora") or "")]
            testo = pagina(k, x, ind, altri, url)
            dest = os.path.join(base, "evento", nome, "index.html")
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            if not os.path.exists(dest) or open(dest, encoding="utf-8").read() != testo:
                open(dest, "w", encoding="utf-8").write(testo)
                scritte += 1
            con_dati += bool(ind)
            voci.append({"nome": nome, "citta": k, "fino": x.get("fino") or x["data"], "dati_event": bool(ind)})
    validi = {v["nome"] for v in voci}
    tolte = 0
    cart = os.path.join(base, "evento")
    for d in (os.listdir(cart) if os.path.isdir(cart) else []):
        if os.path.isdir(os.path.join(cart, d)) and d not in validi and re.match(r"^[a-z]{2}-", d):
            shutil.rmtree(os.path.join(cart, d))
            tolte += 1
    css = os.path.join(cart, "pagine.css")
    if not os.path.exists(css) or open(css, encoding="utf-8").read() != CSS + "\n":
        open(css, "w", encoding="utf-8").write(CSS + "\n")
    elenco = json.dumps(sorted(voci, key=lambda v: v["nome"]), ensure_ascii=False, indent=0)
    ep = os.path.join(cart, "elenco.json")
    if not os.path.exists(ep) or open(ep, encoding="utf-8").read() != elenco:
        open(ep, "w", encoding="utf-8").write(elenco)
    print(f"pagine per evento: {len(voci)} ({con_dati} con indirizzo e dati «Event»), {scritte} riscritte, {tolte} tolte")


if __name__ == "__main__":
    main()
