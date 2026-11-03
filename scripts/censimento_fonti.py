#!/usr/bin/env python3
"""Censimento delle fonti per "Eventi a Bologna".

Per ogni sito prova le vie leggibili da un programma (feed RSS/Atom,
calendari ICS, API JSON di WordPress / The Events Calendar, sitemap)
e scrive censimento.md (tabella leggibile) e censimento.json (dettaglio).

Solo libreria standard: python3 censimento_fonti.py
"""
import json, re, ssl, sys, time, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor

FONTI = {
  # teatri
  "Teatro Duse": "teatroduse.it", "Teatro Celebrazioni": "teatrocelebrazioni.it",
  "Teatro EuropAuditorium": "teatroeuropa.it", "Arena del Sole / ERT (Moline, DAMSLab)": "bologna.emiliaromagnateatro.com",
  "Teatro Dehon": "teatrodehon.it", "Teatro Comunale (TCBO)": "tcbo.it", "TCBO stagione 2027": "stagione2027.tcbo.it",
  "Teatro Testoni Ragazzi": "testoniragazzi.it", "Teatri di Vita": "teatridivita.it", "ITC Teatro": "teatrodellargine.org",
  "Teatro Laura Betti": "teatrocasalecchio.it", "Teatro del Navile": "teatrodelnavile.org", "ATELIERsì": "ateliersi.it",
  "Teatro Mazzacorati": "teatromazzacorati1763.it", "ZolAuditorium": "zolauditorium.it", "Teatro Alemanni": "teatroalemanni.it",
  "Teatro Tivoli": "teatrotivoli.it", "Teatro Antoniano": "antoniano.it",
  # musica e club
  "Locomotiv Club": "locomotivclub.it", "Estragon Club": "estragon.it", "Covo Club": "covoclub.it",
  "Freakout Club": "freakoutclub.it", "Alchemica": "alchemicamusicclub.it", "Bravo Caffè": "bravocaffe.it",
  "Camera Jazz": "camerajazzclub.com", "Cantina Bentivoglio": "cantinabentivoglio.it", "Sghetto Club": "sghettoclub.it",
  "Unipol Arena": "unipolarena.it", "Oratorio San Filippo Neri": "oratoriosanfilipponeri.com", "DumBO": "dumbospace.it",
  "MAST": "mast.org",
  # rassegne e istituzioni
  "Bologna Festival": "bolognafestival.it", "Bologna Jazz Festival": "bolognajazzfestival.com",
  "Musica Insieme": "musicainsiemebologna.it", "AngelicA": "aaa-angelica.com", "Orchestra Mozart": "orchestramozart.com",
  "Accademia Filarmonica": "accademiafilarmonica.it", "Conoscere la Musica": "conoscerelamusica.it", "CantaBO": "cantabo.it",
  "Gender Bender": "genderbender.it", "Palazzo Pepoli": "palazzopepoli.it", "Genus Bononiae (San Colombano)": "genusbononiae.it",
  # aggregatori e biglietterie
  "Cultura Bologna (Comune)": "culturabologna.it", "Città della Musica (Comune)": "cittadellamusica.comune.bologna.it",
  "Bologna Welcome": "bolognawelcome.com", "Cartellone Emilia-Romagna": "cartellone.emiliaromagnacultura.it",
  "Concerti a Bologna": "concertiabologna.it", "Bologna da vivere": "bolognadavivere.com", "Zero Bologna": "zero.eu",
  "DICE": "dice.fm", "TicketOne": "ticketone.it", "Vivaticket": "vivaticket.com", "Fever": "feverup.com",
  "Open data Comune di Bologna": "opendata.comune.bologna.it",
}

PERCORSI = [
  ("rss", "/feed/"), ("rss", "/feed/?post_type=tribe_events"), ("rss", "/eventi/feed/"), ("rss", "/events/feed/"),
  ("rss", "/rss"), ("rss", "/rss.xml"), ("rss", "/feed.xml"), ("rss", "/atom.xml"), ("rss", "/?feed=rss2"),
  ("ics", "/?ical=1"), ("ics", "/eventi/?ical=1"), ("ics", "/events/?ical=1"), ("ics", "/?post_type=tribe_events&ical=1"),
  ("ics", "/calendario.ics"), ("ics", "/events.ics"),
  ("json", "/wp-json/tribe/events/v1/events?per_page=5"), ("json", "/wp-json/wp/v2/posts?per_page=1"),
  ("json", "/wp-json/wp/v2/types"), ("json", "/api/events"), ("json", "/api/eventi"),
  ("sitemap", "/sitemap.xml"), ("sitemap", "/sitemap_index.xml"), ("sitemap", "/wp-sitemap.xml"),
]
UA = "Mozilla/5.0 (compatible; censimento-eventi-bologna/1.0)"
ctx = ssl.create_default_context()

def get(url, timeout=12):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
            ct = r.headers.get("content-type", "")
            body = r.read(300_000)
            return r.status, ct, body.decode("utf-8", "replace"), r.geturl()
    except urllib.error.HTTPError as e:
        return e.code, "", "", url
    except Exception as e:
        return 0, type(e).__name__, "", url

def classifica(tipo, ct, body):
    b = body.lstrip()[:4000].lower()
    if tipo == "rss" and ("<rss" in b or "<feed" in b or "<rdf:rdf" in b):
        n = body.count("<item") + body.count("<entry")
        date_ev = len(re.findall(r"tribe_events|event|evento|spettacolo|concerto", body, re.I))
        return f"RSS ({n} voci{', con eventi' if date_ev > n else ''})"
    if tipo == "ics" and "begin:vcalendar" in b:
        return f"ICS ({body.upper().count('BEGIN:VEVENT')} eventi)"
    if tipo == "json" and (b.startswith("{") or b.startswith("[")):
        try:
            j = json.loads(body)
        except Exception:
            return None
        if isinstance(j, dict) and "events" in j: return f"JSON Events Calendar ({j.get('total', len(j['events']))} eventi)"
        if isinstance(j, dict) and "tribe_events" in j: return "WP con Events Calendar (tipo tribe_events)"
        if isinstance(j, list) and j and isinstance(j[0], dict) and "date" in j[0]: return "WP REST (articoli)"
        if isinstance(j, dict) and ("post" in j or "page" in j): return "WP REST (tipi: " + ", ".join(list(j)[:6]) + ")"
        return "JSON generico"
    if tipo == "sitemap" and ("<urlset" in b or "<sitemapindex" in b):
        return f"sitemap ({body.count('<loc>')} url)"
    return None

def analizza_home(dominio):
    st, ct, body, final = get(f"https://{dominio}/")
    if not body:
        st, ct, body, final = get(f"https://www.{dominio}/")
    info = {"raggiungibile": bool(body), "stato": st, "cms": "", "feed_dichiarati": [], "ics_link": [], "jsonld_eventi": 0}
    if not body: return info
    b = body.lower()
    if "wp-content" in b or "wp-json" in b: info["cms"] = "WordPress"
    if "tribe-events" in b or "tribe_events" in b: info["cms"] += " + The Events Calendar"
    if "drupal" in b: info["cms"] = info["cms"] or "Drupal"
    if "joomla" in b: info["cms"] = info["cms"] or "Joomla"
    info["feed_dichiarati"] = list(dict.fromkeys(re.findall(r'<link[^>]+type="application/(?:rss|atom)\+xml"[^>]+href="([^"]+)"', body, re.I)))[:5]
    info["ics_link"] = list(dict.fromkeys(re.findall(r'href="([^"]+\.ics[^"]*)"', body, re.I)))[:5]
    info["jsonld_eventi"] = len(re.findall(r'"@type"\s*:\s*"(?:Music|Theater)?Event"', body))
    return info

def censisci(nome, dominio):
    out = {"nome": nome, "dominio": dominio, "home": analizza_home(dominio), "trovati": []}
    base = f"https://{dominio}"
    for tipo, p in PERCORSI:
        st, ct, body, final = get(base + p)
        if st == 200 and body:
            c = classifica(tipo, ct, body)
            if c: out["trovati"].append({"tipo": tipo, "url": base + p, "cosa": c})
    for u in out["home"].get("feed_dichiarati", []):
        if u.startswith("/"): u = base + u
        if not any(t["url"] == u for t in out["trovati"]):
            st, ct, body, final = get(u)
            c = classifica("rss", ct, body) if body else None
            if c: out["trovati"].append({"tipo": "rss", "url": u, "cosa": c})
    # valutazione
    t = out["trovati"]; h = out["home"]
    if any(x["tipo"] == "ics" for x in t) or any("Events Calendar" in x["cosa"] for x in t):
        out["livello"] = "A – calendario strutturato (ICS/JSON eventi)"
    elif any("RSS" in x["cosa"] for x in t) or h.get("jsonld_eventi"):
        out["livello"] = "B – feed RSS o dati evento in pagina (JSON-LD)"
    elif any(x["tipo"] == "sitemap" for x in t) or h.get("cms"):
        out["livello"] = "C – solo pagine HTML (sitemap/CMS): leggibile con parser dedicato"
    elif h.get("raggiungibile"):
        out["livello"] = "D – sito dinamico o protetto: serve browser o Claude"
    else:
        out["livello"] = "X – non raggiungibile"
    return out

def main():
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=8) as ex:
        ris = list(ex.map(lambda kv: censisci(*kv), FONTI.items()))
    ris.sort(key=lambda r: (r["livello"], r["nome"]))
    json.dump(ris, open("censimento.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    righe = ["# Censimento fonti – Eventi a Bologna", "", f"{len(ris)} siti, {time.time()-t0:.0f} s", "",
             "| Fonte | Dominio | Livello | CMS | Cosa si è trovato |", "|---|---|---|---|---|"]
    for r in ris:
        cosa = "; ".join(f"{x['cosa']} ← {x['url'].replace('https://'+r['dominio'],'')}" for x in r["trovati"][:3])
        if r["home"].get("jsonld_eventi"): cosa += f"; JSON-LD eventi in home: {r['home']['jsonld_eventi']}"
        righe.append(f"| {r['nome']} | {r['dominio']} | {r['livello'][:1]} | {r['home'].get('cms','')} | {cosa} |")
    conta = {}
    for r in ris: conta[r["livello"]] = conta.get(r["livello"], 0) + 1
    righe += ["", "## Riepilogo", ""] + [f"- {k}: {v}" for k, v in sorted(conta.items())]
    open("censimento.md", "w", encoding="utf-8").write("\n".join(righe))
    print("\n".join(righe))

if __name__ == "__main__":
    main()
