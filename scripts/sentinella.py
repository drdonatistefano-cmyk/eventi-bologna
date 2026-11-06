"""Sentinella dei cartelloni: segnala solo le pagine cambiate dalla settimana prima.

Uso: python3 scripts/sentinella.py
Legge dati/sentinella.json (elenco pagine), scarica ogni pagina (rispettando robots.txt,
una al secondo) e confronta l'impronta dei testi dei link (i titoli degli spettacoli di
solito sono link; date e orologi non contano) con quella della volta precedente.
Scrive dati/sentinella_stato.json: pagine cambiate, invariate, non lette.
Il giro settimanale di Claude apre solo le pagine «cambiate».
"""
import datetime, hashlib, html, json, os, re, sys, time, urllib.request, urllib.robotparser
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

RADICE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ELENCO = os.path.join(RADICE, "dati", "sentinella.json")
STATO = os.path.join(RADICE, "dati", "sentinella_stato.json")
UA = "Mozilla/5.0 (compatible; AchEventsBot/1.0; +https://achevents.com/)"


def scarica(u):
    r = urllib.request.Request(u, headers={"User-Agent": UA, "Accept-Language": "it-IT,it;q=0.9"})
    with urllib.request.urlopen(r, timeout=30) as x:
        return x.read().decode("utf-8", "replace")


def permesso(u, cache={}):
    p = urlsplit(u); base = f"{p.scheme}://{p.netloc}"
    if base not in cache:
        rp = urllib.robotparser.RobotFileParser()
        try:
            rp.parse(scarica(base + "/robots.txt").splitlines())
        except Exception:
            rp = None
        cache[base] = rp
    rp = cache[base]
    return True if rp is None else rp.can_fetch(UA, u)


def impronta(h):
    h = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", h)
    testi = set()
    for t in re.findall(r"(?is)<a\b[^>]*>(.*?)</a>", h):
        t = html.unescape(re.sub(r"<[^>]+>", " ", t))
        t = re.sub(r"\d+", "", t)                       # niente numeri: date e orari cambiano da soli
        t = re.sub(r"\s+", " ", t).strip().lower()
        if 6 <= len(t) <= 160:
            testi.add(t)
    return hashlib.sha1("\n".join(sorted(testi)).encode()).hexdigest(), sorted(testi)


def main():
    elenco = json.load(open(ELENCO, encoding="utf-8"))["pagine"]
    prima = json.load(open(STATO, encoding="utf-8")) if os.path.exists(STATO) else {}
    vecchie = {p["url"]: p for p in prima.get("pagine", [])}
    oggi = datetime.datetime.now(ZoneInfo("Europe/Rome")).date().isoformat()
    out = []
    for p in elenco:
        r = {"citta": p["citta"], "nome": p["nome"], "url": p["url"], "controllata": oggi}
        v = vecchie.get(p["url"], {})
        try:
            if not permesso(p["url"]):
                r["esito"] = "vietata da robots.txt"
            else:
                imp, testi = impronta(scarica(p["url"]))
                r["impronta"] = imp
                r["testi"] = testi[:400]
                if not v.get("impronta"):
                    r["esito"] = "nuova"
                elif v["impronta"] != imp:
                    r["esito"] = "cambiata"
                    old = set(v.get("testi", []))
                    r["novita"] = [t for t in testi if t not in old][:40]   # link comparsi da una settimana all'altra
                else:
                    r["esito"] = "invariata"
        except Exception as e:
            r["esito"] = f"non letta: {e}"
            for k in ("impronta", "testi"):
                if v.get(k): r[k] = v[k]          # tiene l'ultima impronta buona
        out.append(r)
        time.sleep(1)
    stato = {"giorno": oggi, "pagine": out,
             "cambiate": [x["nome"] for x in out if x["esito"] in ("cambiata", "nuova")],
             "non_lette": [x["nome"] for x in out if x["esito"].startswith("non letta") or "vietata" in x["esito"]]}
    json.dump(stato, open(STATO, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{len(out)} pagine · cambiate/nuove {len(stato['cambiate'])} · non lette {len(stato['non_lette'])}")
    for x in out:
        print(f"- {x['nome']}: {x['esito']}" + (f" ({len(x.get('novita', []))} link nuovi)" if x['esito'] == 'cambiata' else ""))


if __name__ == "__main__":
    main()
