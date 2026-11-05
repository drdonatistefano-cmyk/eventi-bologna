#!/usr/bin/env python3
"""Dati per la pagina statistiche.html (cruscotto): visite e clic da GoatCounter
negli ultimi 30 giorni + stato del sito. Gira ogni ora nel workflow
"Cruscotto statistiche" e salva stats.json nel ramo `statistiche`
(così non ripubblica il sito). Il riepilogo giornaliero/settimanale resta
compito di scripts/statistiche.py.
Variabili: GOATCOUNTER_TOKEN (segreto), GITHUB_TOKEN, GITHUB_REPOSITORY."""
import json, os, sys, time, re, collections, datetime as dt, urllib.request, urllib.error, urllib.parse

GC = "eventibologna"
SITE = "https://drdonatistefano-cmyk.github.io/eventi-bologna/"
API = f"https://{GC}.goatcounter.com/api/v0"
TOKEN = os.environ.get("GOATCOUNTER_TOKEN", "").strip()
GH = os.environ.get("GITHUB_TOKEN", "")
REPO = os.environ.get("GITHUB_REPOSITORY", "drdonatistefano-cmyk/eventi-bologna")
UA = {"User-Agent": "eventi-bologna-cruscotto"}
now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
hour = now.replace(minute=0, second=0)          # GoatCounter vuole orari arrotondati all'ora, non nel futuro
iso = lambda d: d.strftime("%Y-%m-%dT%H:%M:%SZ")

def get(url, headers=None, raw=False, tries=3):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={**UA, **(headers or {})}), timeout=40) as r:
                b = r.read()
                return (r.status, b.decode("utf-8", "replace")) if raw else json.loads(b)
        except urllib.error.HTTPError as e:
            if e.code in (429, 502, 503) and i < tries - 1: time.sleep(3); continue
            if raw: return (e.code, "")
            raise
        except Exception:
            if i < tries - 1: time.sleep(3); continue
            if raw: return (0, "")
            raise

def gc(path, **q):
    time.sleep(0.3)  # massimo 4 richieste al secondo
    return get(f"{API}{path}?" + urllib.parse.urlencode(q, doseq=True),
               {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"})

out = {"generato": iso(now), "stato": {}, "errore": ""}

# ---------- stato del sito ----------
st = out["stato"]
code, html = get(SITE + f"?t={int(time.time())}", raw=True)
st["sito"] = {"http": code, "ok": code == 200 and "eventi.js" in html, "statistiche_attive": f'const GC="{GC}"' in html}
for f, var in (("eventi.js", "eventi"), ("mostre.js", "mostre")):
    c, t = get(SITE + f + f"?t={int(time.time())}", raw=True)
    info = {"http": c, "ok": False, "n": 0, "aggiornato": ""}
    m = re.search(r"=\s*(\{.*\})\s*;?\s*$", t, re.S)
    if c == 200 and m:
        try: d = json.loads(m.group(1)); info.update(ok=True, n=len(d.get(var, [])), aggiornato=d.get("aggiornato", ""))
        except Exception: pass
    st[var] = info

# ---------- GoatCounter ----------
if not TOKEN:
    out["errore"] = "manca_token"
else:
    try:
        today = now.date()
        lancio = dt.date(2026, 11, 4)  # GoatCounter risponde 404 per periodi prima della nascita del sito
        days = [d for d in (today - dt.timedelta(days=i) for i in range(29, -1, -1)) if d >= lancio]
        s30 = dt.datetime.combine(days[0], dt.time(), dt.timezone.utc)
        start = {"oggi": today, "7g": max(today - dt.timedelta(days=6), lancio), "30g": days[0]}
        # tutti i percorsi degli ultimi 30 giorni, con il dettaglio giornaliero
        hits = []
        for _ in range(10):
            q = dict(start=iso(s30), end=iso(hour), limit=100, daily="true")
            if hits: q["exclude_paths"] = ",".join(str(h["path_id"]) for h in hits if "path_id" in h)
            r = gc("/stats/hits", **q); hits += r.get("hits", [])
            if not r.get("more"): break
        visite_g = collections.Counter(); eventi_g = collections.Counter()
        per = {"7g": [], "30g": []}
        for h in hits:
            daily = {s["day"][:10]: s.get("daily", 0) for s in (h.get("stats") or [])}
            (eventi_g if h.get("event") else visite_g).update(daily)
            for k in per:
                n = sum(v for d, v in daily.items() if d >= start[k].isoformat()) if daily else (h.get("count", 0) if k == "30g" else 0)
                if n: per[k].append({"path": h.get("path", ""), "titolo": h.get("title", ""), "n": n, "evento": bool(h.get("event"))})
        out["giorni"] = [{"giorno": d.isoformat(), "visite": visite_g.get(d.isoformat(), 0)} for d in days]
        out["totali"] = {k: {"visite": sum(v for d, v in visite_g.items() if d >= s.isoformat()),
                             "eventi": sum(v for d, v in eventi_g.items() if d >= s.isoformat())} for k, s in start.items()}
        for k in per:
            sez = {"percorsi": sorted(per[k], key=lambda x: -x["n"])}
            s0 = dt.datetime.combine(start[k], dt.time(), dt.timezone.utc)
            for page in ("toprefs", "locations", "systems", "browsers", "sizes"):
                try:
                    rr = gc(f"/stats/{page}", start=iso(s0), end=iso(hour), limit=12)
                    sez[page] = [{"nome": y.get("name") or (y.get("id") if page == "sizes" else "") or "(diretto)", "n": y.get("count", 0)} for y in rr.get("stats", [])]
                except Exception:
                    sez[page] = []
            out[k] = sez
    except urllib.error.HTTPError as e:
        out["errore"] = {401: "token_non_valido", 403: "token_senza_permessi"}.get(e.code, f"http_{e.code}")
    except Exception as e:
        out["errore"] = "goatcounter_non_raggiungibile: " + str(e)[:150]

json.dump(out, open(sys.argv[1] if len(sys.argv) > 1 else "stats.json", "w"), ensure_ascii=False, indent=1)
print("ok", out.get("errore") or "", json.dumps(out.get("totali", {})))
