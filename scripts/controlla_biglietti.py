"""Controlla che i link dei biglietti degli Spettacoli (eventi.js + serate.js) portino alla data giusta.
uso: python3 scripts/controlla_biglietti.py [--max N] [--solo dominio]
Per ogni link apre la pagina (solo se il robots.txt del sito lo permette, una pagina al secondo per sito),
legge le date dell'evento dai dati schema.org (startDate) e le confronta con la data in guida.
Esiti: ok | data diversa | piu date (pagina con più date: va bene solo se è voluto) | senza data | non letto | vietato (robots).
Dal 11/11/2026 controlla anche:
- Sport (sport.js): ogni link deve aprirsi; se la pagina ha date (schema.org) la partita deve esserci;
  i link generici del club (biglietteria di tutte le partite) sono segnati «pagina generica».
- Cinema (dati/cinema.json): il link del film deve aprirsi e la pagina deve contenere il titolo del film
  (altrimenti «titolo assente»: il link porta a un altro film o alla pagina della sala).
Scrive dati/controllo_biglietti.json (riepilogo + elenco dei casi da correggere)."""
import json, re, sys, os, time, datetime, urllib.request, urllib.robotparser, collections, concurrent.futures, threading
from urllib.parse import urlparse

RADICE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UA = "Mozilla/5.0 (compatible; AchEventsGuide/1.0; +https://achevents.com)"
MAX = int(sys.argv[sys.argv.index("--max") + 1]) if "--max" in sys.argv else 100000
SOLO = sys.argv[sys.argv.index("--solo") + 1] if "--solo" in sys.argv else ""
_rp, _ult = {}, collections.defaultdict(float)


def carica(f):
    s = open(os.path.join(RADICE, f), encoding="utf-8").read()
    return json.loads(s[s.index("=") + 1:].rstrip().rstrip(";"))


def permesso(u):
    p = urlparse(u); base = f"{p.scheme}://{p.netloc}"
    if base not in _rp:
        rp = urllib.robotparser.RobotFileParser()
        try:
            r = urllib.request.Request(base + "/robots.txt", headers={"User-Agent": UA})
            rp.parse(urllib.request.urlopen(r, timeout=10).read().decode("utf-8", "ignore").splitlines())
        except Exception:
            rp.parse([])
        _rp[base] = rp
    return _rp[base].can_fetch(UA, u)


def dominio(u):
    return ".".join(urlparse(u).netloc.split(".")[-2:])   # i sottodomini (es. *.18tickets.it) sono lo stesso server


_lock_dom = collections.defaultdict(threading.Lock)


def apri(u):
    host = dominio(u)
    with _lock_dom[host]:
        att = 2.0 - (time.time() - _ult[host])
        if att > 0: time.sleep(att)
        _ult[host] = time.time()
    r = urllib.request.Request(u, headers={"User-Agent": UA, "Accept-Language": "it-IT,it;q=0.9"})
    with urllib.request.urlopen(r, timeout=15) as x:
        return x.geturl(), x.read().decode("utf-8", "ignore")


def date_pagina(h):
    date = set()
    for m in re.findall(r'(?is)<script[^>]*application/ld\+json[^>]*>(.*?)</script>', h):
        for d in re.findall(r'"startDate"\s*:\s*"(\d{4}-\d{2}-\d{2})', m): date.add(d)
    if not date:
        for d in re.findall(r'"(?:startDate|start_date|date_start|startTime)"\s*:\s*"(\d{4}-\d{2}-\d{2})', h): date.add(d)
    if not date:
        for d in re.findall(r'itemprop="startDate"[^>]*content="(\d{4}-\d{2}-\d{2})', h): date.add(d)
    return date


def main():
    oggi = datetime.date.today().isoformat()
    voci = collections.defaultdict(list)
    for c in ("", "milano/"):
        for f, k in (("eventi.js", "eventi"), ("serate.js", "serate")):
            try: lst = carica(c + f)[k]
            except Exception: continue
            for e in lst:
                u = e.get("biglietti", "")
                if u.startswith("https://") and (not SOLO or SOLO in u) and (e.get("fino") or e["data"]) >= oggi:
                    voci[u].append({"citta": "mi" if c else "bo", "id": e.get("id"), "data": e["data"], "fino": e.get("fino") or e["data"],
                                    "titolo": e.get("artista", ""), "luogo": e.get("luogo", "")})
    esiti, casi = collections.Counter(), []
    per_sito = collections.defaultdict(collections.Counter)
    blocco = threading.Lock()
    gruppi = collections.defaultdict(list)
    for u, ev in sorted(voci.items())[:MAX]: gruppi[dominio(u)].append((u, ev))

    def un_link(u, ev):
        nostre = sorted({x["data"] for x in ev})
        finale, trovate = "", []
        if not permesso(u): esito = "vietato"
        else:
            try:
                finale, h = apri(u)
                trovate = sorted(date_pagina(h))
                if not trovate: esito = "senza data"
                else:
                    ok_tutte = all(any(x["data"] <= d <= x["fino"] for d in trovate) for x in ev)
                    esito = "ok" if ok_tutte and len(trovate) == 1 else "piu date" if ok_tutte else "data diversa"
            except Exception as ex:
                esito, finale = "non letto", str(ex)[:80]
        return esito, nostre, trovate, finale

    def un_sito(host, elenco):
        t0, errori = time.time(), 0
        for u, ev in elenco:
            if time.time() - t0 > 420 or errori >= 5:   # sito lento o che rifiuta: si ferma e lo segnala
                esito, nostre, trovate, finale = "non letto", sorted({x["data"] for x in ev}), [], "saltato: sito lento o che rifiuta"
            else:
                esito, nostre, trovate, finale = un_link(u, ev)
                errori = errori + 1 if esito == "non letto" else 0
            with blocco:
                esiti[esito] += 1; per_sito[host.replace("www.", "")][esito] += 1
                if esito in ("data diversa", "piu date", "senza data", "non letto"):
                    casi.append({"esito": esito, "link": u, "finale": finale if finale != u else "", "date_guida": nostre, "date_pagina": trovate[:12],
                                 "eventi": [f'{x["citta"]} {x["id"]} {x["data"]} {x["titolo"][:50]} @ {x["luogo"][:30]}' for x in ev][:6]})

    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:
        list(pool.map(lambda kv: un_sito(*kv), gruppi.items()))
    # ---- sport ----
    sport = collections.defaultdict(list)
    for c in ("", "milano/"):
        try: lst = carica(c + "sport.js")["eventi"]
        except Exception: lst = []
        for e in lst:
            if e.get("biglietti", "").startswith("https://") and e["data"] >= oggi:
                sport[e["biglietti"]].append({"citta": "mi" if c else "bo", "id": e.get("id"), "data": e["data"], "fino": e.get("fino") or e["data"],
                                              "titolo": e.get("artista", ""), "luogo": e.get("luogo", "")})
    esiti_s, casi_s = collections.Counter(), []
    for u, ev in sorted(sport.items()):
        es, nostre, trovate, finale = un_link(u, ev) if permesso(u) else ("vietato", [], [], "")
        if es == "senza data" and len(ev) > 1: es = "pagina generica"
        esiti_s[es] += 1
        if es not in ("ok", "piu date", "vietato"):
            casi_s.append({"esito": es, "link": u, "partite": len(ev), "date_pagina": trovate[:6], "finale": finale if finale != u else "",
                           "eventi": [f'{x["citta"]} {x["data"]} {x["titolo"][:50]}' for x in ev][:3]})

    # ---- cinema ----
    def parole(t):
        return [w for w in re.findall(r"[a-zà-ü0-9]{4,}", t.lower()) if w not in ("film", "della", "delle", "dello", "nella", "parte", "versione", "originale")]
    film = collections.defaultdict(set)
    for c in ("", "milano/"):
        try: sale = json.load(open(os.path.join(RADICE, c + "dati", "cinema.json"), encoding="utf-8"))["sale"]
        except Exception: sale = []
        for sa in sale:
            for f in sa.get("film", []):
                u = f.get("biglietti", "")
                if u.startswith("https://"): film[u].add((sa["nome"], f.get("titolo", "")))
    esiti_c, casi_c = collections.Counter(), []

    def un_film(item):
        u, fs = item
        if len(fs) > 1: return u, fs, "pagina della sala", ""      # lo stesso link per più film: biglietteria della sala
        sala, titolo = next(iter(fs))
        if not permesso(u): return u, fs, "vietato", ""
        try:
            finale, h = apri(u)
            testo = re.sub(r"<[^>]+>", " ", h).lower()
            pw = parole(titolo)
            ok = not pw or sum(w in testo for w in pw) >= max(1, (len(pw) + 1) // 2)
            return u, fs, "ok" if ok else "titolo assente", finale
        except Exception as ex:
            return u, fs, "non letto", str(ex)[:80]
    gruppi_c = collections.defaultdict(list)
    for item in film.items(): gruppi_c[dominio(item[0])].append(item)

    def un_sito_c(elenco):
        t0 = time.time()
        for item in elenco:
            r = un_film(item) if time.time() - t0 < 600 else (item[0], item[1], "non letto", "saltato: sito lento")
            with blocco:
                esiti_c[r[2]] += 1
                if r[2] in ("titolo assente", "non letto"):
                    casi_c.append({"esito": r[2], "link": r[0], "film": sorted(f"{a} – {b}" for a, b in r[1])[:3], "finale": r[3] if r[3] != r[0] else ""})
    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:
        list(pool.map(un_sito_c, gruppi_c.values()))

    out = {"giorno": oggi, "link": len(voci), "esiti": esiti, "per_sito": per_sito, "casi": casi,
           "sport": {"link": len(sport), "esiti": esiti_s, "casi": casi_s}, "cinema": {"link": len(film), "esiti": esiti_c, "casi": casi_c}}
    json.dump(out, open(os.path.join(RADICE, "dati", "controllo_biglietti.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps({"link": len(voci), "esiti": esiti, "sport": esiti_s, "cinema": esiti_c}, ensure_ascii=False))
    for s, c in sorted(per_sito.items(), key=lambda x: -sum(x[1].values()))[:25]: print(f"  {s:40} {dict(c)}")


if __name__ == "__main__":
    main()
