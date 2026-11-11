"""Controlla che i link dei biglietti degli Spettacoli (eventi.js + serate.js) portino alla data giusta.
uso: python3 scripts/controlla_biglietti.py [--max N] [--solo dominio]
Per ogni link apre la pagina (solo se il robots.txt del sito lo permette, una pagina al secondo per sito),
legge le date dell'evento dai dati schema.org (startDate) e le confronta con la data in guida.
Esiti: ok | data diversa | piu date (pagina con più date: va bene solo se è voluto) | senza data | non letto | vietato (robots).
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


def apri(u):
    host = urlparse(u).netloc
    att = 1.0 - (time.time() - _ult[host])
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
    for u, ev in sorted(voci.items())[:MAX]: gruppi[urlparse(u).netloc].append((u, ev))

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
    out = {"giorno": oggi, "link": len(voci), "esiti": esiti, "per_sito": per_sito, "casi": casi}
    json.dump(out, open(os.path.join(RADICE, "dati", "controllo_biglietti.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps({"link": len(voci), "esiti": esiti}, ensure_ascii=False))
    for s, c in sorted(per_sito.items(), key=lambda x: -sum(x[1].values()))[:25]: print(f"  {s:40} {dict(c)}")


if __name__ == "__main__":
    main()
