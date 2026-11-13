"""Controllo velocita' delle tre guide (13/11/2026).

Apre le pagine vere dei tre siti in un browser senza schermo e misura quello
che vede una persona, da quattro punti di vista:

  prima visita 4G   telefono, rete 4G, processore 4 volte piu' lento di un
                    iPhone: la persona che arriva da Google per la prima volta
  prima visita 3G   lo stesso con rete lenta (campagna, treno)
  ritorno           telefono 4G, seconda visita: quello che c'e' nel telefono
                    deve bastare
  pc                computer con rete veloce
  uso               telefono, processore lento: quanto rispondono i tocchi
                    (filtri, ricerca, aprire una scheda, scorrere, mappa)

Per ogni pagina: primo disegno, contenuto visibile (le schede), foto visibili,
dati arrivati, KB scaricati, blocco totale (TBT) e blocco piu' lungo. Le prove
di apertura si ripetono e si tiene la mediana, perche' una sola misura balla.

Uso:  python3 scripts/velocita.py [uscita.json] [guide]   es. guide = places,events
      VEL_BASE_PLACES=http://localhost:8790/ ... per provare su una copia locale
      VEL_GIRI=3  quante volte ripetere le aperture (predefinito 3)
"""
import json
import os
import re
import statistics
import sys
import time

from playwright.sync_api import sync_playwright

GIRI = int(os.environ.get("VEL_GIRI", "3"))

INIT = """window.__LT=[];window.__EV=[];window.__LCP=0;
new PerformanceObserver(l=>{for(const e of l.getEntries())__LT.push([Math.round(e.startTime),Math.round(e.duration)])}).observe({type:'longtask',buffered:true});
new PerformanceObserver(l=>{for(const e of l.getEntries())__LCP=Math.round(e.startTime)}).observe({type:'largest-contentful-paint',buffered:true});
try{new PerformanceObserver(l=>{for(const e of l.getEntries())if(e.interactionId)__EV.push([e.name,Math.round(e.duration)])}).observe({type:'event',buffered:true,durationThreshold:16});}catch(e){}"""

RETI = {
    "4G": dict(latency=150, downloadThroughput=int(4e6 / 8), uploadThroughput=int(1.5e6 / 8)),
    "3G": dict(latency=300, downloadThroughput=int(1.6e6 / 8), uploadThroughput=int(0.75e6 / 8)),
    "fibra": dict(latency=20, downloadThroughput=int(50e6 / 8), uploadThroughput=int(10e6 / 8)),
}

FOTO3 = "[...document.querySelectorAll('{sel}')].slice(0,8).filter(i=>i.complete&&i.naturalWidth>0).length>=3"

GUIDE = {
    "places": {
        "nome": "Places", "base": "https://achplaces.com/",
        "pagine": {
            "guida": {"url": "index.html", "contenuto": "document.querySelectorAll('#grid > *').length>5",
                      "foto": FOTO3.format(sel="#grid img.cph"), "dati": r"/dati\.[0-9a-f]+\.json"},
            "mappa": {"url": "filtri.html", "contenuto": "!!(window.__mappa&&document.querySelector('canvas'))",
                      "foto": None, "visibile": "(()=>{const c=document.getElementById('cv');if(!c||!c.width)return false;const d=c.getContext('2d').getImageData(c.width/2|0,c.height/2|0,1,1).data;return d[3]>0})()", "dati": r"/mappan?\.[0-9a-f]+\.json"},
        },
    },
    "dinners": {
        "nome": "Dinners", "base": "https://achdinners.com/",
        "pagine": {
            "guida": {"url": "index.html", "contenuto": "document.querySelectorAll('button.card').length>5",
                      "foto": None, "dati": r"/idx\.[0-9a-f]+\.json"},
        },
    },
    "events": {
        "nome": "Events", "base": "https://achevents.com/",
        "pagine": {
            "guida": {"url": "index.html", "contenuto": "document.querySelectorAll('#list article.card').length>3",
                      "foto": None, "dati": r"/eventi\.js"},
        },
    },
}


def contesto(b, telefono=True):
    return b.new_context(
        viewport={"width": 390, "height": 844} if telefono else {"width": 1366, "height": 900},
        device_scale_factor=3 if telefono else 1, is_mobile=telefono, has_touch=telefono,
        geolocation={"latitude": 44.4949, "longitude": 11.3426}, permissions=["geolocation"],
        locale="it-IT")


def prepara(c, pg, rete, cpu):
    s = c.new_cdp_session(pg)
    s.send("Emulation.setCPUThrottlingRate", {"rate": cpu})
    s.send("Network.enable")
    if rete:
        s.send("Network.emulateNetworkConditions", {"offline": False, **RETI[rete]})
    return s


def apri(pg, s, url, p, timeout=90000):
    """Una apertura: tempi in millisecondi dall'inizio della navigazione."""
    st = {"kb": 0, "dati": None, "t0": None, "url": {}}

    def chiesto(e):
        st["url"][e["requestId"]] = e["request"]["url"]
        if st["t0"] is None:
            st["t0"] = e["timestamp"]

    def finito(e):
        st["kb"] += e.get("encodedDataLength", 0)
        u = st["url"].get(e["requestId"], "")
        if st["dati"] is None and p["dati"] and re.search(p["dati"], u) and st["t0"] is not None:
            st["dati"] = round((e["timestamp"] - st["t0"]) * 1000)

    s.on("Network.requestWillBeSent", chiesto)
    s.on("Network.loadingFinished", finito)
    t0 = time.time()
    pg.goto(url, wait_until="commit")
    visibile = None
    if p.get("visibile"):
        pg.wait_for_function(p["visibile"], polling=20, timeout=timeout)
        visibile = round((time.time() - t0) * 1000)
    pg.wait_for_function(p["contenuto"], timeout=timeout)
    contenuto = round((time.time() - t0) * 1000)
    foto = None
    if p["foto"]:
        try:
            pg.wait_for_function(p["foto"], timeout=30000)
            foto = round((time.time() - t0) * 1000)
        except Exception:
            foto = None
    pg.wait_for_timeout(3000)
    r = pg.evaluate("({fcp:Math.round((performance.getEntriesByName('first-contentful-paint')[0]||{}).startTime||0),lcp:__LCP,lt:__LT.slice()})")
    lt = [d for _, d in r["lt"]]
    s.remove_listener("Network.requestWillBeSent", chiesto)
    s.remove_listener("Network.loadingFinished", finito)
    return {"primo_disegno": r["fcp"], "visibile": visibile if visibile is not None else contenuto, "contenuto": contenuto, "foto": foto, "dati": st["dati"],
            "kb": round(st["kb"] / 1024), "tbt": sum(max(0, d - 50) for d in lt), "blocco_max": max(lt, default=0)}


def mediana(prove):
    out = {}
    for k in prove[0]:
        v = [p[k] for p in prove if p[k] is not None]
        out[k] = round(statistics.median(v)) if v else None
    out["giri"] = len(prove)
    return out


def apertura(b, g, nome_p, p, rete, cpu, telefono=True, ritorno=False, giri=GIRI):
    prove = []
    for _ in range(giri):
        c = contesto(b, telefono)
        pg = c.new_page()
        pg.add_init_script(INIT)
        s = prepara(c, pg, rete, cpu)
        url = g["base"] + p["url"]
        try:
            if ritorno:
                apri(pg, s, url, p)
                pg.goto("about:blank")
            prove.append(apri(pg, s, url, p))
        except Exception as e:
            print(f"  {g['nome']} {nome_p}: apertura non riuscita ({str(e)[:80]})")
        c.close()
    return mediana(prove) if prove else {"errore": "la pagina non si e' aperta"}


def misura(pg, nome, fn, res):
    pg.evaluate("__LT.length=0;__EV.length=0")
    try:
        fn()
    except Exception as e:
        res[nome] = {"errore": str(e)[:80]}
        return
    pg.wait_for_timeout(900)
    ev = pg.evaluate("__EV.slice()")
    lt = pg.evaluate("__LT.slice()")
    res[nome] = {"risposta": max([d for _, d in ev], default=0), "blocco_max": max([d for _, d in lt], default=0)}


def tocchi_places_guida(pg):
    r = {}
    if pg.is_visible("#ftog"):
        misura(pg, "apri filtri", lambda: pg.tap("#ftog"), r)
    cat = pg.locator("#g-cat button, #g-cat .chip").nth(1)
    misura(pg, "scegli categoria", lambda: cat.tap(), r)
    misura(pg, "togli categoria", lambda: cat.tap(), r)
    q = pg.locator("#q")
    if q.is_visible():
        misura(pg, "cerca «torre»", lambda: (q.tap(), pg.keyboard.type("torre", delay=80)), r)
        q.fill("")
    misura(pg, "scorri", lambda: [(pg.mouse.wheel(0, 1500), pg.wait_for_timeout(200)) for _ in range(8)], r)
    pg.mouse.wheel(0, -20000)
    pg.wait_for_timeout(500)
    misura(pg, "apri scheda", lambda: pg.locator("#grid > *").nth(2).tap(), r)
    return r


def tocchi_places_mappa(pg):
    r = {}
    misura(pg, "zoom +", lambda: pg.tap("#zin"), r)
    misura(pg, "trascina", lambda: (pg.mouse.move(200, 300), pg.mouse.down(),
                                    [pg.mouse.move(200 + i * 8, 300 + i * 5) for i in range(20)], pg.mouse.up()), r)
    misura(pg, "posizione", lambda: (pg.tap("#gps"), pg.wait_for_timeout(800)), r)
    it = pg.locator("#list .it, #items .row").first
    if it.count():
        misura(pg, "apri luogo", lambda: it.tap(), r)
    misura(pg, "torna all'Italia", lambda: (pg.keyboard.press("Escape"), pg.tap("#home")), r)
    return r


def tocchi_dinners(pg):
    r = {}
    q = pg.locator("#q")
    if q.is_visible():
        misura(pg, "cerca «osteria»", lambda: (q.tap(), pg.keyboard.type("osteria", delay=80)), r)
        q.fill("")
        pg.wait_for_timeout(600)
    if pg.is_visible("#mfil"):
        misura(pg, "apri filtri", lambda: pg.tap("#mfil"), r)
        pg.keyboard.press("Escape")
        if pg.is_visible("#fchiudi"):
            pg.tap("#fchiudi")
    misura(pg, "scorri", lambda: [(pg.mouse.wheel(0, 1500), pg.wait_for_timeout(200)) for _ in range(8)], r)
    pg.mouse.wheel(0, -20000)
    pg.wait_for_timeout(500)
    misura(pg, "apri scheda", lambda: pg.locator("button.card").nth(2).tap(), r)
    return r


def tocchi_events(pg):
    r = {}
    for nome in ("Mostre", "Spettacoli"):
        bt = pg.locator("button", has_text=nome)
        if bt.count():
            misura(pg, f"scheda «{nome}»", lambda bt=bt: bt.first.tap(), r)
    oggi = pg.locator("button.qc").first
    if oggi.count():
        misura(pg, "filtro «Oggi»", lambda: oggi.tap(), r)
        misura(pg, "togli «Oggi»", lambda: oggi.tap(), r)
    q = pg.locator("#q")
    if q.is_visible():
        misura(pg, "cerca «jazz»", lambda: (q.tap(), pg.keyboard.type("jazz", delay=80)), r)
        q.fill("")
        pg.wait_for_timeout(600)
    misura(pg, "scorri", lambda: [(pg.mouse.wheel(0, 1500), pg.wait_for_timeout(200)) for _ in range(8)], r)
    pg.mouse.wheel(0, -20000)
    pg.wait_for_timeout(500)
    misura(pg, "apri evento", lambda: pg.locator("#list article.card").nth(1).tap(), r)
    return r


TOCCHI = {("places", "guida"): tocchi_places_guida, ("places", "mappa"): tocchi_places_mappa,
          ("dinners", "guida"): tocchi_dinners, ("events", "guida"): tocchi_events}


def uso(b, chiave, g, nome_p, p):
    c = contesto(b)
    pg = c.new_page()
    pg.add_init_script(INIT)
    prepara(c, pg, None, 4)
    try:
        pg.goto(g["base"] + p["url"])
        pg.wait_for_function(p["contenuto"], timeout=90000)
        pg.wait_for_timeout(4000)
        r = TOCCHI[(chiave, nome_p)](pg)
    except Exception as e:
        r = {"errore": str(e)[:100]}
    c.close()
    return r


def giudizio(v):
    """verde / giallo / rosso, con le soglie di Google per i siti veloci."""
    out = {}
    a = v.get("prima visita 4G", {})
    vis = a.get("visibile", a.get("contenuto"))
    if vis is not None:
        out["contenuto"] = "verde" if vis <= 1500 else "giallo" if vis <= 3000 else "rosso"
    if a.get("tbt") is not None:
        out["blocco"] = "verde" if a["tbt"] <= 200 else "giallo" if a["tbt"] <= 600 else "rosso"
    tocchi = [x.get("risposta", 0) for x in v.get("uso", {}).values() if isinstance(x, dict) and "risposta" in x]
    if tocchi:
        m = max(tocchi)
        out["tocchi"] = "verde" if m <= 200 else "giallo" if m <= 500 else "rosso"
    ordine = {"verde": 0, "giallo": 1, "rosso": 2}
    out["insieme"] = max(out.values(), key=lambda x: ordine[x]) if out else "grigio"
    return out


def main():
    uscita = sys.argv[1] if len(sys.argv) > 1 else "velocita.json"
    scelte = sys.argv[2].split(",") if len(sys.argv) > 2 else list(GUIDE)
    try:
        R = json.load(open(uscita))
    except Exception:
        R = {"guide": {}}
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        for chiave in scelte:
            g = GUIDE[chiave]
            g["base"] = os.environ.get("VEL_BASE_" + chiave.upper(), g["base"])
            out = {"nome": g["nome"], "sito": g["base"], "pagine": {}}
            for nome_p, p in g["pagine"].items():
                print(f"{g['nome']} · {nome_p}")
                v = {
                    "prima visita 4G": apertura(b, g, nome_p, p, "4G", 4),
                    "prima visita 3G": apertura(b, g, nome_p, p, "3G", 4, giri=1),
                    "ritorno": apertura(b, g, nome_p, p, "4G", 4, ritorno=True, giri=1),
                    "pc": apertura(b, g, nome_p, p, "fibra", 1, telefono=False, giri=1),
                    "uso": uso(b, chiave, g, nome_p, p),
                }
                v["giudizio"] = giudizio(v)
                out["pagine"][nome_p] = v
                print("  ", json.dumps(v["prima visita 4G"]), v["giudizio"])
            out["aggiornato"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            R["guide"][chiave] = out
        b.close()
    R["aggiornato"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    json.dump(R, open(uscita, "w"), ensure_ascii=False, indent=1)

    # storico: una riga per guida, pagina e giorno (si tiene un anno)
    sto = os.path.join(os.path.dirname(os.path.abspath(uscita)) or ".", "velocita_storico.csv")
    righe = open(sto).read().splitlines() if os.path.exists(sto) else ["data,guida,pagina,contenuto_4g,foto_4g,tbt_4g,kb_4g,contenuto_3g,ritorno,pc,tocco_max,giudizio"]
    oggi = time.strftime("%Y-%m-%d", time.gmtime())
    for chiave in scelte:
        for nome_p, v in R["guide"][chiave]["pagine"].items():
            a, t = v["prima visita 4G"], [x.get("risposta", 0) for x in v["uso"].values() if isinstance(x, dict)]
            righe = [r for r in righe if not r.startswith(f"{oggi},{chiave},{nome_p},")]
            val = [a.get("contenuto"), a.get("foto"), a.get("tbt"), a.get("kb"), v["prima visita 3G"].get("contenuto"),
                   v["ritorno"].get("contenuto"), v["pc"].get("contenuto"), max(t, default=None), v["giudizio"].get("insieme")]
            righe.append(",".join([oggi, chiave, nome_p] + ["" if x is None else str(x) for x in val]))
    testa, corpo = righe[0], sorted(righe[1:])[-3 * 366:]
    open(sto, "w").write("\n".join([testa] + corpo) + "\n")
    print("salvato", uscita, "e", sto)


if __name__ == "__main__":
    main()
