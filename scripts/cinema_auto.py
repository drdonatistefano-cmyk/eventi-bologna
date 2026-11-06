#!/usr/bin/env python3
"""Aggiornamento automatico della scheda Cinema (gira su GitHub Actions, senza Claude).

Legge ogni giorno:
  - le pagine delle singole sale su movieplayer.it (campo `fonte` di dati/cinema.json): film e orari di oggi;
  - cinetecadibologna.it/programmazione/: proiezioni di oggi di Lumière, Modernissimo e Sala Cervi.
Il lunedì (o con --scopri) cerca anche sale nuove nelle pagine dei comuni della provincia su movieplayer.

Scrive dati/cinema.json, cinema.js (tramite scripts/cinema.py) e dati/cinema_stato.json.
Esce con codice 1 se la lettura non è riuscita abbastanza: il flusso GitHub lo segnala e
Claude interviene come riserva (vedi PROCEDURA.md, sezione Cinema).
Rispetta robots.txt: niente pagine di ricerca né filtri con parametri; una pagina al secondo.
"""
import datetime, html, json, os, re, subprocess, sys, time, unicodedata, urllib.request
from zoneinfo import ZoneInfo

RADICE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# --citta mi: Milano (dati in milano/dati/, pagina in milano/cinema.js); senza opzione: Bologna
CITTA = sys.argv[sys.argv.index("--citta") + 1] if "--citta" in sys.argv else "bo"
CART = os.path.join(RADICE, "milano") if CITTA == "mi" else RADICE
DATI = os.path.join(CART, "dati", "cinema.json")
STATO = os.path.join(CART, "dati", "cinema_stato.json")
CACHE = os.path.join(RADICE, "dati", "film_info.json")   # schede dei film già lette: ogni film si legge una volta sola
UA = "Mozilla/5.0 (compatible; EventiBolognaBot/1.0; +https://achevents.com/)"
CINETECA = "https://cinetecadibologna.it/programmazione/film-in-programma/"  # tutta la settimana
CT_SALE = {"lumi": "Cinema Lumière", "modernissimo": "Cinema Modernissimo", "cervi": "Sala Cervi"}
# comuni della Città metropolitana come li chiama movieplayer → nome ufficiale
COMUNI_MP = {"bazzano": "Valsamoggia", "porretta-terme": "Alto Reno Terme"}
UFFICIALI = ["Casalecchio di Reno", "Zola Predosa", "Sasso Marconi", "Valsamoggia", "Monte San Pietro",
    "San Giovanni in Persiceto", "Anzola dell'Emilia", "Calderara di Reno", "Crevalcore", "Sala Bolognese",
    "Sant'Agata Bolognese", "Castel Maggiore", "Argelato", "Bentivoglio", "Castello d'Argile", "Galliera",
    "Pieve di Cento", "San Giorgio di Piano", "San Pietro in Casale", "Budrio", "Baricella",
    "Granarolo dell'Emilia", "Malalbergo", "Minerbio", "Molinella", "Castenaso", "San Lazzaro di Savena",
    "Ozzano dell'Emilia", "Pianoro", "Loiano", "Monghidoro", "Monterenzio", "Imola", "Castel San Pietro Terme",
    "Medicina", "Dozza", "Castel Guelfo di Bologna", "Mordano", "Borgo Tossignano", "Casalfiumanese",
    "Fontanelice", "Castel del Rio", "Alto Reno Terme", "Camugnano", "Castel d'Aiano", "Castel di Casio",
    "Castiglione dei Pepoli", "Gaggio Montano", "Grizzana Morandi", "Lizzano in Belvedere", "Marzabotto",
    "Monzuno", "San Benedetto Val di Sambro", "Vergato"]
MP_CITTA, MM_CITTA = "bologna", "bologna"     # pagine città su movieplayer e mymovies
if CITTA == "mi":
    MP_CITTA, MM_CITTA = "milano", "milano"
    COMUNI_MP = {}
    UFFICIALI = ["Milano", "Rho", "Pero", "Arese", "Bollate", "Sesto San Giovanni", "Cinisello Balsamo", "Cologno Monzese",
        "Legnano", "Assago", "Rozzano", "San Donato Milanese", "San Giuliano Milanese", "Segrate", "Peschiera Borromeo",
        "Pioltello", "Cernusco sul Naviglio"]


def slug(s):
    s = unicodedata.normalize("NFD", s.lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


UFF = {slug(c): c for c in UFFICIALI}


def scarica(url):
    time.sleep(1.0)
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "it-IT,it;q=0.9"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", errors="replace")


def testo(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


def ora(s):
    m = re.match(r"^(\d{1,2})[.:](\d{2})$", s.strip())
    return f"{int(m.group(1)):02d}:{m.group(2)}" if m else None


def leggi_movieplayer(h):
    """Film e orari di oggi da una pagina sala di movieplayer."""
    i = h.find("list--film-cinema")
    if i < 0:
        raise ValueError("struttura della pagina cambiata (manca list--film-cinema)")
    blocco = h[i:]
    out = []
    for item in re.split(r'<div class="grid-item d-grid', blocco)[1:]:
        t = re.search(r'grid-item__title[^>]*>(.*?)</h2>', item, re.S)
        if not t:
            continue
        titolo = testo(t.group(1))
        orari, vo_ore = [], []
        for cella in re.findall(r'<div class="flex-fill[^"]*">(.*?)</div>', item, re.S):
            o = ora(re.sub(r"<span.*", "", cella, flags=re.S).strip())
            if not o:
                continue
            orari.append(o)
            if "originale" in cella.lower():
                vo_ore.append(o)
        generi = re.search(r"Generi:(.*?)</p>", item, re.S)
        generi = ", ".join(x.strip() for x in testo(generi.group(1)).split(",") if x.strip()) if generi else ""
        cast = re.search(r'media__cast[^>]*>(.*?)</p>', item, re.S)
        cast = testo(cast.group(1)) if cast else ""
        regia = re.search(r"film di (.+?)(?: con |$)", cast)
        regia = regia.group(1).strip() if regia else ""
        inter = re.search(r"\bcon (.+)$", cast)
        inter = inter.group(1).strip() if inter else ""
        inter = re.sub(r"\s+,", ",", inter)
        if not regia:   # ripiego: il titolo del link alla recensione («… del film di Nome Cognome»)
            rr = re.search(r'title="[^"]*\bfilm di ([A-ZÀ-Ý][^"<>]{2,60}?)(?: con [^"]*)?"', item)
            regia = html.unescape(rr.group(1)).strip() if rr else ""
        date = re.search(r'media__dates[^>]*>(.*?)</p>', item, re.S)
        date = testo(date.group(1)) if date else ""
        durata = re.search(r"(\d{2,3}) min", date)
        anno = re.match(r"\s*(\d{4})", date)
        versione = ""
        if vo_ore:
            versione = "Versione originale" + ("" if len(vo_ore) == len(orari) else " (solo ore " + ", ".join(vo_ore) + ")")
        if titolo:
            out.append({"titolo": titolo, "orari": sorted(set(orari)), "versione": versione, "genere": generi, "regia": regia,
                        "interpreti": inter, "durata": int(durata.group(1)) if durata else None, "anno": int(anno.group(1)) if anno else None})
    return out


def leggi_cineteca(h, oggi):
    """Proiezioni di oggi nelle sale della Cineteca."""
    if "c-repeat-loop" not in h:
        raise ValueError("struttura della pagina della Cineteca cambiata")
    per_sala = {}
    for b in re.split(r'class="c-repeat-loop__content-container"', h)[1:]:
        dt = re.search(r'datetime="(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2})', b)
        if not dt or dt.group(1) != oggi:
            continue
        tit = re.search(r'c-repeat-loop__title[^>]*>(.*?)</h6>', b, re.S)
        dove = re.search(r'c-repeat-loop__where">(.*?)</div>', b, re.S)
        if not tit or not dove:
            continue
        dove = testo(dove.group(1)).lower()
        sala = next((v for k, v in CT_SALE.items() if k in dove), None)
        if not sala:
            continue
        info = re.search(r'c-repeat-loop__title-info">(.*?)</p>', b, re.S)
        info = testo(info.group(1)) if info else ""
        regia = re.search(r"\bdi (.+?) \(\d+", info)
        pa = re.match(r"\((?:[^,()]*, )?([^/()]+)/(\d{4})\)", info)
        du = re.search(r"\((\d+)′\)", info)
        ver = re.search(r'audio-info.*?info-item-text">(.*?)</div>', b, re.S)
        titolo = testo(tit.group(1))
        link = re.search(r'href="(https://cinetecadibologna\.it/programmazione/proiezione/[^"?]+/)', b)
        f = per_sala.setdefault(sala, {}).setdefault(titolo.lower(), {"titolo": titolo, "orari": [], "versione": testo(ver.group(1)) if ver else "", "genere": "", "regia": regia.group(1) if regia else "", "paese": pa.group(1).strip() if pa else "", "anno": int(pa.group(2)) if pa else None, "durata": int(du.group(1)) if du else None, "_scheda": link.group(1) if link else ""})
        f["orari"].append(dt.group(2))
    for films in per_sala.values():
        for f in films.values():
            f["orari"] = sorted(set(f["orari"]))
    return {k: list(v.values()) for k, v in per_sala.items()}


def chiave(s):
    s = unicodedata.normalize("NFD", html.unescape(s).lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def leggi_mymovies(h):
    """Scheda breve di ogni film in programmazione a Bologna (genere, paese, anno, durata, regia, interpreti)."""
    if "schedine-titolo" not in h:
        raise ValueError("struttura della pagina mymovies cambiata")
    out = {}
    for b in h.split('class="schedine-titolo"')[1:]:
        b = b[:6000]
        tt = re.search(r'<a href="https://www\.mymovies\.it/film/\d{4}/[^"]+" title="([^"]+)"', b)
        if not tt:
            continue
        lancio = re.search(r'schedine-lancio">(.*?)</div>', b, re.S)
        lancio = lancio.group(1) if lancio else ""
        gen = [html.unescape(g) for g in re.findall(r'title="Film [^"]+" href="https://www\.mymovies\.it/film/[a-z-]+/">([^<]+)</a>', lancio)]
        pa = re.search(r'\?country=[^"]+">([^<]+)</a>', lancio)
        du = re.search(r"Durata (\d+) Minuti", lancio)
        an = re.search(r'/film/(\d{4})/">\d{4}</a>', lancio)
        reg = re.search(r"Un film di (.*?)\.\s*(?:<span|<strong|</div>)", b, re.S)
        con = re.search(r"<span>Con (.*?)</span>", b, re.S)
        nomi = lambda s: [html.unescape(x).strip() for x in re.findall(r">([^<]+)</a>", s)]
        r_ = nomi(reg.group(1)) if reg else []
        c_ = nomi(con.group(1))[:4] if con else []
        info = {"genere": ", ".join(gen), "paese": html.unescape(pa.group(1)).strip() if pa else "",
                "durata": int(du.group(1)) if du else None, "anno": int(an.group(1)) if an else None,
                "regia": " e ".join(r_), "interpreti": (", ".join(c_[:-1]) + " e " + c_[-1]) if len(c_) > 1 else "".join(c_)}
        titolo = html.unescape(tt.group(1))
        for k in {chiave(titolo), chiave(titolo.split(" - ")[0])}:
            out.setdefault(k, info)
    return out


def leggi_18tickets(h):
    """Biglietterie 18tickets: {chiave(titolo): link alla pagina d'acquisto del film}."""
    out = {}
    for b in re.split(r"<li[^>]*class=['\"]splide__slide", h)[1:]:
        u = re.search(r"href=['\"](https://[^'\"]+/film/\d+)", b)
        t = re.search(r"<p[^>]*page-heading[^>]*>(.*?)</p>", b, re.S) or re.search(r"<h\d[^>]*>(.*?)</h\d>", b, re.S)
        if u and t and testo(t.group(1)):
            tt, link = testo(t.group(1)), u.group(1).replace("://www.", "://")
            out.setdefault(chiave(tt), link)
            out.setdefault(chiave(re.sub(r"\s*[(\[].*?[)\]]", "", tt)), link)  # senza titolo originale tra parentesi
    return out


def cerca_link(tk, titolo):
    for k in (chiave(titolo), chiave(titolo.split(" - ")[0]), chiave(re.split(r"\s[–-]\s", titolo)[0])):
        if k and k in tk:
            return tk[k]
    k = chiave(titolo)
    return next((v for c, v in tk.items() if len(k) > 5 and (c.startswith(k + " ") or k.startswith(c + " "))), None)


def permesso(url):
    import urllib.robotparser
    from urllib.parse import urlsplit
    r = urllib.robotparser.RobotFileParser()
    p = urlsplit(url)
    try:
        r.parse(scarica(f"{p.scheme}://{p.netloc}/robots.txt").splitlines())
    except Exception:
        return True  # robots.txt assente: lettura permessa
    return r.can_fetch(UA, url)


def tipo_da_nome(n):
    n = n.lower()
    if re.search(r"uci|space|multisala|giometti|starplex|medusa|cineci|century|cinecomfort", n): return "Multisala"
    if "arena" in n: return "Arena"
    if "essai" in n: return "D'essai"
    return "Sala di comunità"


def scopri(d, log):
    """Cerca sale nuove nelle pagine dei comuni della provincia su movieplayer."""
    h = scarica(f"https://movieplayer.it/cinema/{MP_CITTA}/")
    note = {s.get("fonte") for s in d["sale"]}
    nuove = 0
    for cslug in sorted(set(re.findall(rf'href="/cinema/{MP_CITTA}/([a-z0-9-]+)/"', h))):
        comune = COMUNI_MP.get(cslug) or UFF.get(cslug)
        if not comune:
            continue
        try:
            p = scarica(f"https://movieplayer.it/cinema/{MP_CITTA}/{cslug}/")
        except Exception as e:
            log.append(f"scoperta {cslug}: {e}")
            continue
        sel = p[p.find("Seleziona il cinema"):] if "Seleziona il cinema" in p else ""
        for href, nome in re.findall(r'href="(/cinema/[a-z0-9-]+_\d+/)"[^>]*>([^<]+)</a>', sel[:20000]):
            url = "https://movieplayer.it" + href
            if url in note:
                continue
            note.add(url)
            nome = html.unescape(nome).strip()
            nid = "c%03d" % (1 + max([int(s["id"][1:]) for s in d["sale"]] or [0]))
            d["sale"].append({"id": nid, "nome": nome if nome.lower().startswith("cinema") or "uci" in nome.lower() else "Cinema " + nome,
                              "citta": comune, "indirizzo": "", "tipo": tipo_da_nome(nome), "sito": "", "fonte": url, "film": [], "auto": True})
            nuove += 1
    return nuove


def main():
    oggi = datetime.datetime.now(ZoneInfo("Europe/Rome")).date()
    d = json.load(open(DATI, encoding="utf-8"))
    log, lette, fallite = [], [], []
    if "--scopri" in sys.argv or oggi.weekday() == 0 or not d["sale"]:
        try:
            n = scopri(d, log)
            log.append(f"sale nuove trovate: {n}")
        except Exception as e:
            log.append(f"scoperta non riuscita: {e}")
    # movieplayer, sala per sala
    for s in d["sale"]:
        u = s.get("fonte", "")
        if not re.match(r"^https://movieplayer\.it/cinema/[a-z0-9-]+_\d+/$", u):
            continue
        try:
            s["film"] = leggi_movieplayer(scarica(u))
            for f in s["film"]:
                f["giorni"] = {oggi.isoformat(): f["orari"]}
            lette.append(s["nome"])
        except Exception as e:
            s["film"] = []          # mai orari vecchi
            fallite.append(f"{s['nome']}: {e}")
    # Cineteca
    ct_ok = True
    try:
        if CITTA != "bo":
            raise LookupError("salta")   # la Cineteca è solo a Bologna
        hct = scarica(CINETECA)
        ct = {}
        for k in range(8):   # oggi e i 7 giorni seguenti
            g = (oggi + datetime.timedelta(days=k)).isoformat()
            for sala, films in leggi_cineteca(hct, g).items():
                acc = ct.setdefault(sala, {})
                for f in films:
                    x = acc.setdefault(f["titolo"].lower(), {**f, "orari": [], "giorni": {}})
                    x["giorni"][g] = f["orari"]
                    if k == 0:
                        x["orari"] = f["orari"]
        cache = json.load(open(CACHE, encoding="utf-8")) if os.path.exists(CACHE) else {}
        nuove = 0
        for films in ct.values():
            for f in films.values():
                u = f.pop("_scheda", "")
                if u and u not in cache and nuove < 40:
                    try:
                        h = scarica(u)
                        m = re.search(r'Con: ([^<"\n]+)', h)
                        cache[u] = {"interpreti": html.unescape(m.group(1)).strip() if m else ""}
                        nuove += 1
                    except Exception as e:
                        log.append(f"scheda film {u}: {e}")
                if u in cache and cache[u].get("interpreti") and not f.get("interpreti"):
                    f["interpreti"] = cache[u]["interpreti"]
        json.dump(cache, open(CACHE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        for s in d["sale"]:
            if s["nome"] in CT_SALE.values():
                s["film"] = list(ct.get(s["nome"], {}).values())
        lette.append("Cineteca")
        if not ct:
            log.append("Cineteca: nessuna proiezione oggi trovata")
    except LookupError:
        pass
    except Exception as e:
        ct_ok = False
        for s in d["sale"]:
            if s["nome"] in CT_SALE.values():
                s["film"] = []
        fallite.append(f"Cineteca: {e}")
    # schede dei film da mymovies (una sola pagina): genere uniforme, regia e interpreti mancanti
    try:
        mm = leggi_mymovies(scarica(f"https://www.mymovies.it/cinema/{MM_CITTA}/"))
        trovati = 0
        for s in d["sale"]:
            for f in s["film"]:
                info = mm.get(chiave(f["titolo"])) or mm.get(chiave(f["titolo"].split(" - ")[0]))
                if not info:
                    continue
                trovati += 1
                if info["genere"]:
                    f["genere"] = info["genere"]
                for k in ("regia", "interpreti", "paese", "durata", "anno"):
                    if info.get(k) and not f.get(k):
                        f[k] = info[k]
        log.append(f"mymovies: {len(mm)} schede, {trovati} film abbinati")
    except Exception as e:
        log.append(f"mymovies non letto: {e}")
    # link d'acquisto dei singoli film dalle biglietterie 18tickets (una pagina per biglietteria)
    pagine = {}
    for s in d["sale"]:
        b = s.get("biglietti", "")
        if "18tickets.it" in b and s["film"]:
            pagine.setdefault(b, []).append(s)
    for b, sale in pagine.items():
        try:
            if not permesso(b):
                log.append(f"biglietteria {b}: vietata da robots.txt")
                continue
            tk = leggi_18tickets(scarica(b))
            n = 0
            for s in sale:
                for f in s["film"]:
                    u = cerca_link(tk, f["titolo"])
                    if u:
                        f["biglietti"] = u
                        n += 1
                    else:
                        f.pop("biglietti", None)
            log.append(f"biglietteria {b}: {len(tk)} film in vendita, {n} abbinati")
        except Exception as e:
            log.append(f"biglietteria {b} non letta: {e}")
    nmp = len(lette) - (1 if ct_ok and CITTA == "bo" else 0)
    tot_mp = nmp + sum(1 for f in fallite if not f.startswith("Cineteca"))
    film = {f["titolo"].lower() for s in d["sale"] for f in s["film"]}
    ok = ct_ok and tot_mp > 0 and nmp / tot_mp >= 0.6 and len(film) >= 8
    stato = {"quando": datetime.datetime.now(ZoneInfo("Europe/Rome")).isoformat(timespec="minutes"),
             "giorno": oggi.isoformat(), "ok": ok, "film": len(film),
             "sale_con_film": sum(1 for s in d["sale"] if s["film"]), "pagine_lette": len(lette),
             "pagine_fallite": fallite, "note": log}
    if len(film) > 0:
        d["aggiornato"] = d["giorno_orari"] = oggi.isoformat()
        d["fonte_aggiornamento"] = "automatico (GitHub)"
        json.dump(d, open(DATI, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        r = subprocess.run([sys.executable, os.path.join(RADICE, "scripts", "cinema.py"), DATI, os.path.join(CART, "cinema.js")])
        if r.returncode:
            stato["ok"] = False
            stato["note"].append("cinema.py ha segnalato errori: cinema.js non aggiornato")
    else:
        stato["note"].append("nessun film letto: dati lasciati come erano")
    json.dump(stato, open(STATO, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(stato, ensure_ascii=False, indent=1))
    sys.exit(0 if stato["ok"] else 1)


if __name__ == "__main__":
    main()
