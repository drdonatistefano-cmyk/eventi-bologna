"""Verifica delle tre guide di Ach, da più punti di vista, in tre livelli di approfondimento.

Uso: python3 scripts/verifica.py LIVELLO USCITA.json [ID_RICHIESTA]
  1 = rapida (circa 1 minuto, senza browser): pagine, dati, servizi, posta, automazioni
  2 = completa (circa 8 minuti): in più le guide provate in un browser come su un telefono, link a campione, sicurezza
  3 = approfondita (circa 30 minuti): tre larghezze di schermo, campioni grandi, codice pubblico passato al setaccio
Non modifica nulla: legge soltanto. Il rapporto è pubblico (ramo «statistiche»): niente dati riservati qui dentro.
Regola (REGOLE.md §8 quater): ogni funzione nuova delle guide aggiunge qui il suo controllo.
Le prove di questo guardiano sono in scripts/prova_verifica.py; gli avvisi accettati in scripts/verifica_eccezioni.json.
15/11/2026 (eccezioni e link senza risposta: 16/11/2026).
"""
import concurrent.futures as cf
import datetime
import hashlib
import json
import os
import random
import re
import subprocess
import sys
import time
import urllib.parse

import requests

LIV = int(sys.argv[1]) if len(sys.argv) > 1 else 1
OUT = sys.argv[2] if len(sys.argv) > 2 else "verifica.json"
RICHIESTA = sys.argv[3] if len(sys.argv) > 3 else ""
B = {"places": os.environ.get("VER_PLACES", "https://achplaces.com/"),
     "dinners": os.environ.get("VER_DINNERS", "https://achdinners.com/"),
     "events": os.environ.get("VER_EVENTS", "https://achevents.com/")}
SERVIZI = os.environ.get("VER_SERVIZI", "https://servizi.achplaces.com")
LOCALE = any("localhost" in v for v in B.values())
UA = {"User-Agent": "Mozilla/5.0 (compatible; ach-verifica/1.0)"}
PROPRIETARIO = os.environ.get("GITHUB_REPOSITORY_OWNER", "")
random.seed(int(time.time()) // 86400)   # stesso campione per tutto il giorno: un errore si può ricontrollare

VISTE = []


class Vista:
    def __init__(self, nome, cosa):
        self.d = {"nome": nome, "cosa": cosa, "controlli": []}
        VISTE.append(self.d)

    def _c(self, esito, nome, dettaglio=""):
        self.d["controlli"].append({"esito": esito, "nome": nome, "dettaglio": str(dettaglio)[:400]})

    def ok(self, nome, dettaglio=""): self._c("ok", nome, dettaglio)
    def avviso(self, nome, dettaglio=""): self._c("avviso", nome, dettaglio)
    def errore(self, nome, dettaglio=""): self._c("errore", nome, dettaglio)

    def se(self, cond, nome, dettaglio="", grave=True):
        (self.ok if cond else (self.errore if grave else self.avviso))(nome, dettaglio)
        return cond


def prendi(url, **k):
    t = time.time()
    try:
        r = requests.get(url, headers=UA, timeout=k.pop("timeout", 25), **k)
        return r, time.time() - t
    except Exception as e:
        return None, str(e)[:120]


def stato(url, metodo="GET", **k):
    try:
        r = requests.request(metodo, url, headers=UA, timeout=20, allow_redirects=True, stream=True, **k)
        s = r.status_code
        r.close()
        return s
    except Exception:
        return 0


def protetto(v, nome, fn):
    """Un controllo che si rompe non deve fermare gli altri: diventa un errore nel rapporto."""
    try:
        fn()
    except Exception as e:
        v.errore(nome, f"il controllo si è interrotto: {type(e).__name__}: {e}")


def js_dati(testo):
    return json.loads(testo[testo.index("=") + 1:].rstrip().rstrip(";"))


def copie_diverse(copie):
    """Dato {guida: contenuto o None}, le guide la cui copia è diversa da quella più comune.
    Una copia che non si è potuta scaricare (None) non conta: «non sono riuscito a guardare» non è «diversa»."""
    import collections
    lette = {g: c for g, c in copie.items() if c is not None}
    if not lette:
        return []
    comune = collections.Counter(lette.values()).most_common(1)[0][0]
    return [g for g, c in lette.items() if c != comune]


def classifica_link(esiti):
    """Divide (indirizzo, codice) in rotti (404, 410), dubbi (altri 4xx/5xx: il sito rifiuta i controlli)
    e senza risposta (0: non siamo riusciti a guardare, non vuol dire che il link è rotto)."""
    rotti = [(u, s) for u, s in esiti if s in (404, 410)]
    dubbi = [(u, s) for u, s in esiti if s >= 400 and s not in (404, 410)]
    zitti = [(u, s) for u, s in esiti if s == 0]
    return {"rotti": rotti, "dubbi": dubbi, "senza_risposta": zitti, "provati": len(esiti), "guardati": len(esiti) - len(zitti)}


def giudizio_link(r):
    """ok fino al 3% di rotti fra i link guardati davvero, avviso fino al 10%, poi errore.
    Se meno di metà dei link ha risposto il controllo non ha visto abbastanza: avviso, mai «tutto bene»."""
    if r["guardati"] < r["provati"] / 2:
        return "avviso"
    q = len(r["rotti"]) / max(1, r["guardati"])
    return "ok" if q <= 0.03 else "avviso" if q <= 0.10 else "errore"


def riassumi_giri(giri, presenti):
    """Dai giri di GitHub (dal più recente): l'esito dell'ultimo giro di ogni programma, quante volte è fallito,
    e quali programmi hanno l'ultimo giro fallito. «presenti» sono i file dei flussi che esistono ancora:
    i giri di un flusso tolto non contano. Se l'elenco non si è potuto leggere (None) non si scarta nulla."""
    # 20/11/2026: i giri si raggruppano per FILE del flusso, non per nome. Un flusso con il file illeggibile fallisce con il
    # nome uguale al percorso (".github/workflows/x.yml"); i giri buoni dopo la correzione hanno il nome vero, e il rapporto
    # restava rosso per tre giorni per un flusso già sistemato (controllo_biglietti.yml, 19-20/11).
    ultimo, falliti, tot, nome = {}, {}, 0, {}
    for r in giri:
        if r.get("status") != "completed":
            continue
        if presenti is not None and os.path.basename(r.get("path") or "") not in presenti:
            continue
        tot += 1
        f = os.path.basename(r.get("path") or "") or r["name"]
        if f not in nome or nome[f].startswith(".github/"):
            nome[f] = r["name"]
        ultimo.setdefault(f, r["conclusion"])
        if r["conclusion"] in ("failure", "timed_out", "startup_failure"):
            falliti[f] = falliti.get(f, 0) + 1
    ultimo = {nome[f]: c for f, c in ultimo.items()}
    falliti = {nome[f]: n for f, n in falliti.items()}
    rotti = [n for n, c in ultimo.items() if c in ("failure", "timed_out", "startup_failure")]
    return {"ultimo": ultimo, "falliti": falliti, "tot": tot, "rotti": rotti}


# ---------------------------------------------------------------- eccezioni accettate (REGOLE §8 quater.6)
ECCEZIONI = os.path.join(os.path.dirname(os.path.abspath(__file__)), "verifica_eccezioni.json")


def leggi_eccezioni(percorso=ECCEZIONI):
    try:
        return json.load(open(percorso, encoding="utf-8")).get("accettati", [])
    except FileNotFoundError:
        return []


def applica_eccezioni(viste, voci, oggi):
    """Un avviso coperto da una voce valida diventa «ok» con dettaglio «noto, ...».
    Una voce copre solo se il controllo contiene TUTTE le sue parole; senza parole o senza scadenza non copre nulla.
    Gli errori non si perdonano mai. Restituisce le voci scadute, che vanno segnalate."""
    scadute, valide = [], []
    for e in voci:
        try:
            scade = datetime.date.fromisoformat(e.get("scade", ""))
        except ValueError:
            continue
        if not e.get("contiene"):
            continue
        (valide if scade >= oggi else scadute).append(e)
    for vi in viste:
        for c in vi["controlli"]:
            if c["esito"] != "avviso":
                continue
            testo = (c["nome"] + " " + c["dettaglio"]).lower()
            for e in valide:
                if all(p.lower() in testo for p in e["contiene"]):
                    c["esito"] = "ok"
                    c["dettaglio"] = (f"noto, accettato fino al {e['scade']}: {e.get('motivo', '')}" + (" · " + c["dettaglio"] if c["dettaglio"] else ""))[:400]
                    break
    return scadute


# ---------------------------------------------------------------- 1. pagine
def vista_pagine():
    v = Vista("Pagine e disponibilità", "Le pagine principali rispondono, in fretta e con il contenuto giusto")
    pagine = [("Places", B["places"], "Ach"), ("Places, mappa", B["places"] + "filtri.html", "canvas"),
              ("Places, Chi siamo", B["places"] + "chi-siamo/", "Chi siamo"), ("Places, Privacy", B["places"] + "privacy/", "privacy"),
              ("Places, mappa del sito", B["places"] + "sitemap.xml", "<sitemap"), ("Places, robots", B["places"] + "robots.txt", "Sitemap"),
              # 15/11/2026: la guida come un'app (icona sulla schermata Home)
              ("Places, app: manifesto", B["places"] + "app.webmanifest", "standalone"), ("Places, app: pagina per gli ospiti", B["places"] + "app/", "achInstalla"),
              ("Dinners, app: manifesto", B["dinners"] + "app.webmanifest", "standalone"), ("Dinners, app: pagina per gli ospiti", B["dinners"] + "app/", "achInstalla"),
              ("Events, app: manifesto", B["events"] + "app.webmanifest", "standalone"), ("Events, app: pagina per gli ospiti", B["events"] + "app/", "achInstalla"),
              # 16/11/2026: tasto WhatsApp nella scheda (REGOLE 8 sexies); Places quando la chat Places lo pubblica
              ("Dinners, tasto WhatsApp", B["dinners"], "function waDin("), ("Events, tasto WhatsApp", B["events"], "function waEv("),
              ("Events Milano, tasto WhatsApp", B["events"] + "milano/", "function waEv("),
              ("Events, pagina Collaborano con noi", B["events"] + "collaborano/", "Teatro Dal Verme"),
              ("Events, pulsante Collaborano con noi", B["events"], "ach-guide__coll"),
              # 16/11/2026: filtri nuovi (chip in alto e foglio a gruppi)
              # 18/11/2026: la scheda piccola non è un pulsante con dentro altri link (WebAbility); Ravenna e Ferrara
              ("Events, schede piccole accessibili", B["events"], 'class="mopen"'), ("Events, comune nelle schede", B["events"], 'class="mcom"'), ("Events, clic Biglietti con il sito di arrivo", B["events"], "clic-biglietti/"), ("Events Ravenna", B["events"] + "ravenna/", "Events"),
              ("Events Ferrara", B["events"] + "ferrara/", "Events"),
              ("Events, filtri nuovi", B["events"], 'F.id="nAf"'), ("Places, riquadro dei filtri che segue", B["places"], 'getElementById("nAm")'), ("Places, tasto WhatsApp", B["places"], "function waPl("), ("Events Milano, filtri nuovi", B["events"] + "milano/", 'F.id="nAf"'),
              ("Dinners", B["dinners"], "Dinners"), ("Dinners, Chi siamo", B["dinners"] + "chi-siamo/", "Chi siamo"),
              ("Dinners, Privacy", B["dinners"] + "privacy/", "privacy"),
              ("Events Bologna", B["events"], "Events"), ("Events Milano", B["events"] + "milano/", "Events"),
              ("Events, Chi siamo", B["events"] + "chi-siamo/", "Chi siamo"), ("Events, Privacy", B["events"] + "privacy/", "privacy"),
              # 18/11/2026 (lavoro SEO approvato da Stefano): mappe del sito, robots e indirizzo canonico delle città
              ("Events, robots", B["events"] + "robots.txt", "Sitemap"), ("Events, mappa del sito", B["events"] + "sitemap.xml", "<urlset"),
              ("Dinners, robots", B["dinners"] + "robots.txt", "Sitemap"), ("Dinners, mappa del sito", B["dinners"] + "sitemap.xml", "<sitemap"),
              ("Events Bologna, indirizzo canonico", B["events"], '<link rel="canonical" href="https://achevents.com/">'),
              ("Events Milano, indirizzo canonico", B["events"] + "milano/", '<link rel="canonical" href="https://achevents.com/milano/">'),
              ("Events Ravenna, indirizzo canonico", B["events"] + "ravenna/", '<link rel="canonical" href="https://achevents.com/ravenna/">'),
              ("Events Ferrara, indirizzo canonico", B["events"] + "ferrara/", '<link rel="canonical" href="https://achevents.com/ferrara/">'),
              ("Statistiche Places", B["places"] + "statistiche.html", "<html"), ("Statistiche Dinners", B["dinners"] + "statistiche.html", "<html"),
              ("Statistiche Events", B["events"] + "statistiche.html", "<html"), ("Velocità", B["events"] + "velocita.html", "<html")]
    with cf.ThreadPoolExecutor(8) as ex:
        ris = list(ex.map(lambda p: prendi(p[1]), pagine))
    for (nome, url, segno), (r, t) in zip(pagine, ris):
        if r is None:
            v.errore(nome, f"non raggiungibile: {t}")
        elif r.status_code != 200:
            v.errore(nome, f"risposta {r.status_code} ({url})")
        elif segno.lower() not in r.text.lower():
            v.errore(nome, f"la pagina risponde ma manca «{segno}»: contenuto inatteso")
        elif t > 3:
            v.avviso(nome, f"lenta a rispondere: {t:.1f} s")
        else:
            v.ok(nome, f"{t:.2f} s")
    if not LOCALE:
        for g, u in B.items():
            s = stato(u.replace("https://", "http://"))
            v.se(s == 200, f"{g}: l'indirizzo senza https porta al sito", f"risposta {s}", grave=False)
    # le parti comuni delle guide restano uguali (REGOLE §8 sexies.3, 16/11/2026): oggi installa.js
    copie = {}
    for g, u in B.items():
        r, _ = prendi(u + "installa.js")
        copie[g] = r.content if r is not None and r.status_code == 200 else None
    diverse = copie_diverse(copie)
    lette = [g for g, c in copie.items() if c is not None]
    if len(lette) < 2:
        v.avviso("installa.js uguale nelle tre guide", f"lette solo {len(lette)} copie su {len(copie)}")
    else:
        v.se(not diverse, "installa.js uguale nelle tre guide", (f"diversa in: {', '.join(diverse)}" if diverse else f"{len(lette)} copie identiche"), grave=False)


# ---------------------------------------------------------------- 2. dati
def vista_dati():
    v = Vista("Dati", "I file dei dati esistono, si leggono, sono completi e aggiornati")
    oggi = datetime.date.today()

    def events():
        for citta, base, minimo in (("Bologna", B["events"], 150), ("Milano", B["events"] + "milano/", 200),
                                    ("Ravenna", B["events"] + "ravenna/", 40), ("Ferrara", B["events"] + "ferrara/", 40)):   # RA e FE dal 18/11/2026
            r, _ = prendi(base + "eventi.js")
            if not v.se(r is not None and r.status_code == 200, f"Events {citta}: file degli eventi"):
                continue
            d = js_dati(r.text)
            ev = d.get("eventi", [])
            v.se(len(ev) >= minimo, f"Events {citta}: numero di eventi", f"{len(ev)} (attesi almeno {minimo})")
            eta = (oggi - datetime.date.fromisoformat(d["aggiornato"])).days
            v.se(eta <= 2, f"Events {citta}: aggiornato di recente", f"ultimo aggiornamento {d['aggiornato']} ({eta} giorni fa)", grave=eta > 5)
            senza = [e.get("id") for e in ev if not (e.get("luogo") and e.get("data") and e.get("artista"))]
            v.se(len(senza) <= len(ev) * 0.01, f"Events {citta}: eventi con titolo, luogo e data", f"{len(senza)} incompleti", grave=False)
            passati = [e for e in ev if (e.get("fino") or e.get("data") or "9") < oggi.isoformat()]
            v.se(len(passati) <= len(ev) * 0.05, f"Events {citta}: niente eventi già passati", f"{len(passati)} con data passata", grave=False)
            chiavi = [(e.get("data"), e.get("ora"), (e.get("artista") or "").lower(), e.get("luogo")) for e in ev]
            doppi = len(chiavi) - len(set(chiavi))
            v.se(doppi <= len(ev) * 0.01, f"Events {citta}: niente doppioni", f"{doppi} doppioni", grave=False)
        for f, chiave in (("mostre.js", "mostre"), ("serate.js", "serate"), ("incontri.js", "incontri"), ("sport.js", "eventi"), ("cinema.js", "sale")):
            r, _ = prendi(B["events"] + f)
            if r is None or r.status_code != 200:
                v.errore(f"Events: {f}", "manca")
                continue
            d = js_dati(r.text)
            n = d.get(chiave)
            n = len(n) if isinstance(n, (list, dict)) else (n or 0)
            eta = (oggi - datetime.date.fromisoformat(d.get("aggiornato", "2000-01-01"))).days
            v.se(n > 0 and eta <= 7, f"Events: {f}", f"{n} voci, aggiornato {eta} giorni fa", grave=n == 0 or eta > 14)
        r, _ = prendi(B["events"] + "versioni.js")
        v.se(r is not None and r.status_code == 200 and len(js_dati(r.text)) >= 5, "Events: impronte dei file (versioni.js)")

    def dinners():
        r, _ = prendi(B["dinners"])
        m = re.search(r"idx\.[0-9a-f]+\.json", r.text if r is not None else "")
        if not v.se(bool(m), "Dinners: la pagina indica il file dell'indice"):
            return
        ri, t = prendi(B["dinners"] + m.group(0), timeout=60)
        if not v.se(ri is not None and ri.status_code == 200, "Dinners: indice dei locali"):
            return
        d = ri.json()
        n = len(d["col"]["n"])
        v.se(n >= 40000, "Dinners: numero di locali nell'indice", f"{n:,}".replace(",", "."))
        v.se(all(len(c) == n for c in d["col"].values() if isinstance(c, list)), "Dinners: colonne dell'indice tutte della stessa lunghezza")
        scelti = sum(1 for x in d["col"].get("pos", []) if x)
        v.se(scelti >= 2500, "Dinners: locali in classifica", f"{scelti}", grave=False)
        nomi = set(re.findall(r"d/([A-Z]{2})\.[0-9a-f]+\.json", ri.text[:200000] + (r.text if r is not None else "")))
        mm = re.search(r"\"BO\":\"([0-9a-f]+)\"|BO\.([0-9a-f]+)\.json", ri.text[:400000] + r.text)
        if mm:
            h = mm.group(1) or mm.group(2)
            s = stato(B["dinners"] + f"d/BO.{h}.json")
            v.se(s == 200, "Dinners: dettagli di una provincia (Bologna)", f"risposta {s}")
        del nomi

    def places():
        r, _ = prendi(B["places"])
        nomi = sorted(set(re.findall(r"[a-z]+(?:\.[a-z]+)*\.[0-9a-f]{10}\.(?:json|js)", r.text if r is not None else "")))
        if not v.se(len(nomi) >= 3, "Places: la pagina indica i file dei dati", f"{len(nomi)} file"):
            return
        camp = nomi if LIV >= 2 else nomi[:6]
        with cf.ThreadPoolExecutor(8) as ex:
            st = list(ex.map(lambda n: stato(B["places"] + n), camp))
        rotti = [n for n, s in zip(camp, st) if s != 200]
        if rotti:   # 17/11/2026: una risposta mancata (0) si riprova una volta prima di dare errore
            rotti = [n for n in rotti if stato(B["places"] + n) != 200]
        v.se(not rotti, "Places: i file dei dati citati dalla pagina esistono", f"{len(camp)} controllati" + (f", mancano: {rotti[:5]}" if rotti else ""))
        m = re.search(r"dati\.[0-9a-f]+\.json", r.text)
        if m:
            rd, _ = prendi(B["places"] + m.group(0), timeout=60)
            ok = rd is not None and rd.status_code == 200
            v.se(ok and len(rd.content) > 100000 and isinstance(rd.json(), dict), "Places: file principale dei luoghi leggibile",
                 f"{len(rd.content) // 1024} KB" if ok else "")
        rs, _ = prendi(B["places"] + "sitemap-1.xml", timeout=60)
        if v.se(rs is not None and rs.status_code == 200, "Places: mappa del sito (elenco delle pagine)"):
            url = re.findall(r"<loc>([^<]+)</loc>", rs.text)
            com = [u for u in url if "/comune/" in u]
            luo = [u for u in url if "/luogo/" in u]
            v.se(len(com) >= 2500 and len(luo) >= 8000, "Places: pagine per Google", f"{len(com)} comuni, {len(luo)} luoghi")
            n = {1: 6, 2: 30, 3: 250}[LIV]
            camp = random.sample(com, min(n // 2, len(com))) + random.sample(luo, min(n // 2, len(luo)))
            if LOCALE:
                camp = [u.replace("https://achplaces.com/", B["places"]) for u in camp]
            with cf.ThreadPoolExecutor(10) as ex:
                st = list(ex.map(stato, camp))
            rotti = [u for u, s in zip(camp, st) if s != 200]
            v.se(not rotti, "Places: pagine a campione dalla mappa del sito", f"{len(camp)} aperte" + (f", non rispondono: {rotti[:4]}" if rotti else ""))

    protetto(v, "Events", events)
    protetto(v, "Dinners", dinners)
    protetto(v, "Places", places)


# ---------------------------------------------------------------- 3. servizi e posta
RADICE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOGLIA_PROVINCE = 10000   # business plan (bp_dinamico.py, SOGLIA_APERTURA): visite medie mensili delle tre guide
# 22/11/2026: account non scritto (progetto trasferibile): dal repository in cui si gira o dall'indirizzo git
REPO_GH = os.environ.get("GITHUB_REPOSITORY") or re.sub(r"^.*github\.com[:/]+|\.git$", "", subprocess.run(["git", "remote", "get-url", "origin"], cwd=os.path.dirname(os.path.abspath(__file__)), capture_output=True, text=True).stdout.strip())
STAT_VISITE = f"https://raw.githubusercontent.com/{REPO_GH}/statistiche/dati/visite_guide.json"


def visite_ultimi_30(righe, oggi):
    """Visite delle tre guide negli ultimi 30 giorni completi (oggi escluso) e quanti di quei giorni hanno dati."""
    da = (oggi - datetime.timedelta(days=30)).isoformat()
    giorni = {}
    for r in righe:
        g = r.get("giorno", "")
        if da <= g < oggi.isoformat():
            giorni[g] = giorni.get(g, 0) + int(r.get("visite") or 0)
    return sum(giorni.values()), len(giorni)


def vista_citta():
    """18/11/2026 (Stefano): le città accese sono collegate dappertutto, e quando le visite superano la soglia
    del business plan la decisione di aprire nuove province arriva a Stefano (il flusso apre una segnalazione)."""
    v = Vista("Città di Events", "Ogni città accesa è collegata in tutti i file; soglia per aprire nuove province")

    def collegamenti():
        import controlla_citta as CC
        if not os.path.exists(os.path.join(RADICE, "index.html")):
            v.avviso("Città collegate dappertutto", "file del repository non presenti: controllo saltato")
            return
        r = CC.controlla(RADICE)
        for liv, c, cosa in r:
            (v.errore if liv == "errore" else v.avviso)(f"Città {c}", cosa)
        if not any(liv == "errore" for liv, _, _ in r):
            v.ok("Città collegate dappertutto", ", ".join(CC.citta_attive(open(os.path.join(RADICE, "index.html"), encoding="utf-8").read())))

    def soglia():
        r, t = prendi(STAT_VISITE)
        if r is None or r.status_code != 200:
            v.avviso("Nuove province: soglia del business plan", f"visite non lette: {t}")
            return
        tot, giorni = visite_ultimi_30(r.json(), datetime.date.today())
        det = f"{tot} visite delle tre guide negli ultimi 30 giorni ({giorni} giorni con dati), soglia {SOGLIA_PROVINCE}"
        if tot >= SOGLIA_PROVINCE:
            v.avviso("Nuove province: decisione per Stefano", det + ". Il business plan prevede di aprire la prima ondata (Rimini, Modena…): la decide Stefano")
        else:
            v.ok("Nuove province: soglia del business plan", det)

    def due_parti():
        """18/11/2026: eventi-presto.js (prossimi 14 giorni, all'apertura) + eventi-resto.js (dopo) = eventi.js, in ogni città.
        Se non tornano, chi apre la pagina vede spettacoli in meno o doppi."""
        for cart, nome in (("", "Bologna"), ("milano/", "Milano"), ("ravenna/", "Ravenna"), ("ferrara/", "Ferrara")):
            pezzi = {}
            for f in ("eventi", "eventi-presto", "eventi-resto"):
                r, _ = prendi(B["events"] + cart + f + ".js")
                pezzi[f] = js_dati(r.text) if r is not None and r.status_code == 200 else None
            if pezzi["eventi"] is None:
                continue
            if pezzi["eventi-presto"] is None or pezzi["eventi-resto"] is None:
                v.errore(f"Events {nome}: spettacoli in due parti", "manca eventi-presto.js o eventi-resto.js (la pagina carica eventi.js intero, più lenta)")
                continue
            tutti = [e.get("id") for e in pezzi["eventi"].get("eventi", [])]
            p1 = [e.get("id") for e in pezzi["eventi-presto"].get("eventi", [])]
            p2 = [e.get("id") for e in pezzi["eventi-resto"].get("eventi", [])]
            uguali = sorted(map(str, p1 + p2)) == sorted(map(str, tutti))
            v.se(uguali, f"Events {nome}: spettacoli in due parti",
                 f"{len(p1)} subito + {len(p2)} dopo = {len(tutti)}" if uguali else
                 f"non tornano: {len(p1)} + {len(p2)} contro {len(tutti)} in eventi.js (lanciare «Versioni dei dati»)")
            fino = pezzi["eventi-presto"].get("fino_a", "")
            v.se(fino >= datetime.date.today().isoformat(), f"Events {nome}: prossimi giorni aggiornati",
                 f"eventi-presto.js arriva fino al {fino}", grave=False)

    def pagine_evento():
        """18/11/2026: le pagine dei singoli spettacoli (scripts/pagine_eventi.py) esistono, dichiarano il proprio
        indirizzo e, dove c'è l'indirizzo del luogo, hanno i dati «Event» che chiede Google (nome, inizio, luogo con via)."""
        r, t0 = prendi(B["events"] + "evento/elenco.json")
        if r is None or r.status_code != 200:
            v.errore("Events: pagine dei singoli spettacoli", f"elenco non raggiungibile: {t0 if r is None else r.status_code}")
            return
        voci = r.json()
        if not voci:
            v.avviso("Events: pagine dei singoli spettacoli", "elenco vuoto")
            return
        con = [x for x in voci if x.get("dati_event")]
        camp = random.sample(con, min(3, len(con))) + random.sample(voci, min(2, len(voci)))
        rotte = []
        for x in camp:
            u = B["events"] + "evento/" + x["nome"] + "/"
            rr, _ = prendi(u)
            if rr is None or rr.status_code != 200:
                rotte.append(f"{x['nome']}: non risponde"); continue
            if f'<link rel="canonical" href="https://achevents.com/evento/{x["nome"]}/">' not in rr.text:
                rotte.append(f"{x['nome']}: canonico sbagliato")
            if x.get("dati_event"):
                import re as _re
                m = _re.search(r'<script type="application/ld\+json">(.*?)</script>', rr.text, _re.S)
                try:
                    ld = json.loads(m.group(1)) if m else {}
                except ValueError:
                    ld = {}
                if not (ld.get("@type") == "Event" and ld.get("name") and ld.get("startDate")
                        and ((ld.get("location") or {}).get("address") or {}).get("streetAddress")):
                    rotte.append(f"{x['nome']}: dati «Event» incompleti")
        v.se(not rotte, "Events: pagine dei singoli spettacoli",
             f"{len(voci)} pagine, {len(con)} con i dati «Event»; {len(camp)} aperte a campione" + (f"; {'; '.join(rotte[:3])}" if rotte else ""))
        quota = len(con) / max(1, len(voci))
        v.se(quota >= 0.5, "Events: spettacoli con indirizzo del luogo", f"{quota:.0%} delle pagine (sotto il 50% Google ne vede pochi: "
             "guardare dati/indirizzi_da_vedere.json)" if quota < 0.5 else f"{quota:.0%} delle pagine", grave=False)

    protetto(v, "Città collegate dappertutto", collegamenti)
    protetto(v, "Spettacoli in due parti", due_parti)
    protetto(v, "Pagine dei singoli spettacoli", pagine_evento)
    protetto(v, "Nuove province: soglia del business plan", soglia)


def vista_servizi():
    v = Vista("Servizi e posta", "Disiscrizione, modulo delle correzioni e impostazioni dei domini per la posta")
    if LOCALE:
        v.avviso("Saltata", "in prova locale i servizi non si controllano")
        return
    r, _ = prendi(SERVIZI + "/disiscrivi")
    v.se(r is not None and r.status_code in (200, 400), "Pagina di disiscrizione raggiungibile", f"risposta {getattr(r, 'status_code', r)}")
    r, _ = prendi(SERVIZI + "/correggi/")
    v.se(r is not None and r.status_code == 200 and "<form" in r.text.lower(), "Modulo «Segnala una correzione»")
    if r is not None:
        v.se("privacy" in r.text.lower(), "Il modulo rimanda all'informativa privacy", grave=False)
    r, _ = prendi(SERVIZI + "/correggi/?comune=modena-mo")
    v.se(r is not None and r.status_code == 200, "Modulo aperto su un comune")
    s = stato(SERVIZI + "/posta")
    v.se(s in (401, 403, 404), "La pagina riservata dei numeri non si apre senza chiave", f"risposta {s}")
    s = stato(SERVIZI + "/verifica")
    v.se(s in (401, 403, 404), "La pagina delle verifiche non si apre senza chiave", f"risposta {s}")
    s = stato(SERVIZI + "/raccolta")
    v.se(s in (401, 403, 404, 405), "Le correzioni raccolte non si leggono senza autorizzazione", f"risposta {s}")
    try:
        s = requests.post(SERVIZI + "/correzione", json={}, headers=UA, timeout=20).status_code
    except Exception:
        s = 0
    v.se(400 <= s < 500, "Il modulo rifiuta una correzione vuota", f"risposta {s}")
    try:
        s = requests.post(SERVIZI + "/conteggi", json={"x": 1}, headers=UA, timeout=20).status_code
    except Exception:
        s = 0
    v.se(s in (401, 403), "I numeri della Dashboard non si possono cambiare da fuori", f"risposta {s}")

    # 17/11/2026: i link delle lettere portano ?ref=<codice>; devono aprire la guida e il conteggio visite deve esserci
    for g, coda in (("places", "?lang=it&ref=P3-10#bologna-bo"), ("dinners", "?ref=P2#cerca=Bologna"), ("events", "?cerca=Teatro&ref=P1-E")):
        r, _ = prendi(B[g] + coda)
        aperta = r is not None and r.status_code == 200
        v.se(aperta, f"{g}: si apre dal link tracciato di una lettera", f"risposta {getattr(r, 'status_code', r)}")
        if aperta:
            v.se("goatcounter" in r.text, f"{g}: conteggio visite presente (vede da quale lettera arrivano)", grave=False)

    def dns(nome, tipo):
        try:
            j = requests.get("https://cloudflare-dns.com/dns-query", params={"name": nome, "type": tipo},
                             headers={"accept": "application/dns-json"}, timeout=15).json()
            return [a.get("data", "").strip('"').replace('" "', "") for a in j.get("Answer", [])]
        except Exception:
            return None

    for dom in ("achplaces.com", "achdinners.com", "achevents.com"):
        mx, txt, dm = dns(dom, "MX"), dns(dom, "TXT"), dns("_dmarc." + dom, "TXT")
        if mx is None or txt is None:
            v.avviso(f"{dom}: impostazioni di posta", "non lette (servizio DNS non raggiungibile)")
            continue
        v.se(any("infomaniak" in x for x in mx), f"{dom}: la posta arriva alla casella giusta (MX)", ", ".join(mx)[:80])
        spf = [x for x in txt if x.startswith("v=spf1")]
        v.se(len(spf) == 1 and "infomaniak" in spf[0], f"{dom}: autorizzazione all'invio (SPF)", (spf or ["manca"])[0][:80] + (" · più di un record SPF" if len(spf) > 1 else ""))
        v.se(bool(dm) and dm[0].startswith("v=DMARC1"), f"{dom}: regola antifalsificazione (DMARC)", (dm or ["manca"])[0][:60])
        dk = dns("20261113._domainkey." + dom, "TXT")
        v.se(bool(dk), f"{dom}: firma delle email (DKIM)", "presente" if dk else "manca")


# ---------------------------------------------------------------- 4. velocità
def vista_velocita():
    v = Vista("Velocità", "L'ultima misura fatta come da telefono (4G, 3G, ritorno, tocchi)")
    if LOCALE:
        v.avviso("Saltata", "in prova locale la velocità non si legge")
        return
    r, _ = prendi(f"https://raw.githubusercontent.com/{PROPRIETARIO}/eventi-bologna/statistiche/velocita.json")
    if not v.se(r is not None and r.status_code == 200, "Misure della velocità disponibili"):
        return
    d = r.json()
    for g, gd in d.get("guide", {}).items():
        for p, pd in gd.get("pagine", {}).items():
            giu = pd.get("giudizio") or {}
            ins = giu.get("insieme") if isinstance(giu, dict) else giu
            quando = (pd.get("quando") or gd.get("quando") or d.get("quando") or "")[:10]
            det = "; ".join(f"{k}: {x}" for k, x in giu.items() if k != "insieme")[:300] if isinstance(giu, dict) else ""
            nome = f"{gd.get('nome', g)}, {p}"
            if ins == "verde":
                v.ok(nome, f"verde ({quando})")
            elif ins == "giallo":
                v.avviso(nome, f"giallo ({quando}) {det}")
            else:
                v.errore(nome, f"{ins} ({quando}) {det}")
    q = d.get("quando") or d.get("aggiornato") or ""
    if q:
        try:
            eta = (datetime.datetime.now(datetime.timezone.utc) - datetime.datetime.fromisoformat(q.replace("Z", "+00:00"))).days
            v.se(eta <= 2, "La misura è recente", f"{q[:10]}", grave=False)
        except Exception:
            pass


# ---------------------------------------------------------------- 5. automazioni
def vista_automazioni():
    v = Vista("Automazioni", "I programmi automatici su GitHub (parte pubblica) stanno funzionando")
    # cartelloni letti da GitHub per il giro del lunedì (15/11/2026, REGOLE §8 quater)
    if not LOCALE and PROPRIETARIO:
        for c in ("bo", "mi"):
            r, _ = prendi(f"https://raw.githubusercontent.com/{PROPRIETARIO}/eventi-bologna/cartelloni/{c}/candidati.json")
            if r is None or r.status_code != 200:
                v.avviso(f"Cartelloni {c}: letti da GitHub", "il ramo «cartelloni» non c'è ancora")
                continue
            try:
                d = r.json()
                quando = datetime.datetime.strptime(d["quando"][:16], "%Y-%m-%d %H:%M")
                eta = (datetime.datetime.utcnow() - quando).days
                lette = sum(1 for p in d["pagine"] if p.get("esito") == "ok")
                v.se(eta <= 8, f"Cartelloni {c}: letti da GitHub questa settimana", f"{d['quando']}, {eta} giorni fa", grave=False)
                v.se(lette >= max(1, len(d["pagine"]) * 0.6), f"Cartelloni {c}: pagine lette", f"{lette} su {len(d['pagine'])}", grave=False)
                v.se((d.get("ticketone") or {}).get("gruppi", 0) > 0, f"Cartelloni {c}: TicketOne letto", str(d.get("ticketone"))[:200], grave=False)
            except Exception as e:
                v.avviso(f"Cartelloni {c}: rapporto leggibile", f"{type(e).__name__}: {e}")
    tok = os.environ.get("GITHUB_TOKEN", "")
    if not (tok and PROPRIETARIO):
        v.avviso("Saltata", "senza accesso a GitHub")
        return
    h = {"Authorization": "Bearer " + tok, "Accept": "application/vnd.github+json"}
    da = (datetime.datetime.utcnow() - datetime.timedelta(days=3)).strftime("%Y-%m-%dT%H:%M:%SZ")
    for repo in ("achplaces", "achdinners.com", "eventi-bologna"):
        giri = []
        for pag in (1, 2, 3):
            try:
                rs = requests.get(f"https://api.github.com/repos/{PROPRIETARIO}/{repo}/actions/runs",
                                  params={"per_page": 100, "page": pag, "created": ">=" + da}, headers=h, timeout=30).json().get("workflow_runs", [])
            except Exception:
                rs = []
            if not rs:
                break
            giri += rs
        try:   # i flussi che esistono ancora: i giri di un flusso tolto non contano (16/11/2026)
            el = requests.get(f"https://api.github.com/repos/{PROPRIETARIO}/{repo}/contents/.github/workflows", headers=h, timeout=30)
            presenti = {f["name"] for f in el.json()} if el.status_code == 200 else None
        except Exception:
            presenti = None
        g = riassumi_giri(giri, presenti)
        ultimo, falliti, tot, rotti = g["ultimo"], g["falliti"], g["tot"], g["rotti"]
        if rotti:
            v.errore(f"{repo}: programmi il cui ultimo giro è fallito", ", ".join(rotti)[:300])
        elif falliti:
            v.avviso(f"{repo}: qualche giro fallito negli ultimi 3 giorni, poi ripartito", ", ".join(f"{k} ({n})" for k, n in falliti.items())[:300])
        else:
            v.ok(f"{repo}: nessun giro fallito negli ultimi 3 giorni", f"{tot} giri, {len(ultimo)} programmi")
        if "pages build and deployment" in ultimo:
            v.se(ultimo["pages build and deployment"] == "success", f"{repo}: ultima pubblicazione del sito riuscita")


# ---------------------------------------------------------------- 6. funzioni (browser)
PROVE = {
    "places": {"url": B["places"], "pronto": "document.querySelectorAll('#grid > *').length>5", "schede": "#grid > *", "cerca": "duomo"},
    "dinners": {"url": B["dinners"], "pronto": "document.querySelectorAll('button.card').length>5", "schede": "button.card", "cerca": "osteria"},
    "events": {"url": B["events"], "pronto": "document.querySelectorAll('#list article.card').length>3", "schede": "#list article.card", "cerca": "teatro"},
    "events-milano": {"url": B["events"] + "milano/", "pronto": "document.querySelectorAll('#list article.card').length>3", "schede": "#list article.card", "cerca": "teatro"},
}


def vista_funzioni():
    v = Vista("Funzioni delle guide", "Le guide aperte in un browser come su telefono, tablet e computer: si caricano, si cerca, si apre una scheda")
    from playwright.sync_api import sync_playwright
    larghezze = [(390, 844)] if LIV == 2 else [(390, 844), (820, 1180), (1440, 900)]
    with sync_playwright() as p:
        b = p.chromium.launch()
        for nome, g in PROVE.items():
            for w, h in larghezze:
                et = f"{nome} a {w} px"
                c = b.new_context(viewport={"width": w, "height": h}, is_mobile=w < 600, has_touch=w < 900)
                pg = c.new_page()
                err, cons = [], []
                pg.on("pageerror", lambda e: err.append(str(e)[:150]))
                pg.on("console", lambda m: cons.append(m.text[:150]) if m.type == "error" else None)
                try:
                    pg.goto(g["url"], timeout=60000)
                    pg.wait_for_function(g["pronto"], timeout=60000)
                    pg.wait_for_timeout(1500)
                    v.ok(f"{et}: la guida si carica")
                    sw = pg.evaluate("[document.documentElement.scrollWidth, innerWidth]")
                    v.se(sw[0] <= sw[1] + 2, f"{et}: niente esce dallo schermo in larghezza", f"contenuto {sw[0]} px su {sw[1]}", grave=False)
                    v.se(pg.locator('a[href*="chi-siamo"]').count() > 0 and pg.locator('a[href*="privacy"]').count() > 0,
                         f"{et}: link a Chi siamo e Privacy presenti", grave=False)
                    prima = pg.locator(g["schede"]).count()
                    pg.fill("#q", g["cerca"])
                    pg.wait_for_timeout(1800)
                    dopo = pg.locator(g["schede"]).count()
                    testo = pg.locator(g["schede"]).first.inner_text() if dopo else ""
                    v.se(dopo > 0, f"{et}: la ricerca «{g['cerca']}» trova risultati", f"{dopo} schede mostrate (prima {prima})")
                    del testo
                    pg.fill("#q", "zzqqxx")
                    pg.wait_for_timeout(1500)
                    v.se(pg.locator(g["schede"]).count() <= 1, f"{et}: una ricerca senza senso non trova nulla", grave=False)
                    pg.fill("#q", "")
                    pg.wait_for_timeout(1500)
                    lung = pg.evaluate("document.body.innerText.length")
                    pg.locator(g["schede"]).nth(1).click(timeout=8000)
                    pg.wait_for_timeout(1500)
                    lung2 = pg.evaluate("document.body.innerText.length")
                    v.se(lung2 != lung or pg.url != g["url"], f"{et}: toccando una scheda si apre il dettaglio", grave=False)
                    v.se(not err, f"{et}: nessun errore del programma della pagina", "; ".join(err[:3]))
                    gravi = [x for x in cons if not re.search(r"favicon|gc\.zgo\.at|goatcounter|ERR_BLOCKED|net::ERR|Failed to load resource", x)]
                    v.se(not gravi, f"{et}: nessun errore in console", "; ".join(gravi[:3]), grave=False)
                except Exception as e:
                    v.errore(f"{et}: prova interrotta", f"{type(e).__name__}: {str(e)[:200]}" + (" · errori: " + "; ".join(err[:2]) if err else ""))
                c.close()
        # funzioni particolari
        c = b.new_context(viewport={"width": 390, "height": 844})
        pg = c.new_page()

        def prova(nome, fn):
            try:
                fn()
            except Exception as e:
                v.errore(nome, f"{type(e).__name__}: {str(e)[:200]}")

        def cerca_link():
            pg.goto(B["events"] + "?cerca=Teatro", timeout=60000)
            pg.wait_for_function(PROVE["events"]["pronto"], timeout=60000)
            v.se(pg.input_value("#q") == "Teatro", "Events: il link «?cerca=» apre la guida già filtrata (usato nelle lettere ai locali)")

        def inglese():
            pg.goto(B["places"] + "?lang=en", timeout=60000)
            pg.wait_for_function(PROVE["places"]["pronto"], timeout=60000)
            pg.wait_for_timeout(1500)
            t = pg.evaluate("document.body.innerText.slice(0,3000)").lower()
            v.se(any(x in t for x in ("places", "search", "museum", "churches", "near")), "Places: la versione inglese si apre", grave=False)

        def comune():
            pg.goto(B["places"] + "?lang=it#bologna-bo", timeout=60000)
            pg.wait_for_function(PROVE["places"]["pronto"], timeout=60000)
            pg.wait_for_timeout(1500)
            v.se("bologna" in pg.evaluate("document.body.innerText.slice(0,6000)").lower(), "Places: il link a un comune apre quel comune (usato nelle lettere)", grave=False)

        def mappa():
            pg.goto(B["places"] + "filtri.html", timeout=60000)
            pg.wait_for_function("!!document.querySelector('canvas')", timeout=60000)
            v.ok("Places: la mappa si apre")

        def modulo():
            pg.goto(SERVIZI + "/correggi/?comune=modena-mo", timeout=60000)
            pg.wait_for_timeout(4000)
            n = pg.locator("select option").count()
            v.se(n > 5, "Modulo delle correzioni: elenca i luoghi del comune", f"{n} voci nell'elenco")

        prova("Events: link «?cerca=»", cerca_link)
        prova("Places: inglese", inglese)
        prova("Places: link a un comune", comune)
        prova("Places: mappa", mappa)
        if not LOCALE:
            prova("Modulo delle correzioni", modulo)
        b.close()


# ---------------------------------------------------------------- 7. link
def vista_link():
    v = Vista("Link", "Link verso biglietterie e pagine interne, a campione")
    n = {2: 30, 3: 200}[LIV]

    def events():
        tutti = []
        for base in (B["events"], B["events"] + "milano/"):
            r, _ = prendi(base + "eventi.js")
            if r is not None and r.status_code == 200:
                tutti += [e["biglietti"] for e in js_dati(r.text).get("eventi", []) if str(e.get("biglietti", "")).startswith("http")]
        per_dom = {}
        for u in set(tutti):
            per_dom.setdefault(urllib.parse.urlparse(u).netloc, []).append(u)
        camp = []
        while len(camp) < n and any(per_dom.values()):   # pochi per sito, per non disturbare nessuno
            for d in list(per_dom):
                if per_dom[d] and len(camp) < n:
                    camp.append(per_dom[d].pop(random.randrange(len(per_dom[d]))))
        with cf.ThreadPoolExecutor(6) as ex:
            st = list(ex.map(stato, camp))
        # chi non ha risposto si riprova una volta, con calma (lezione 6 del §8 bis)
        zitti = [i for i, s in enumerate(st) if s == 0]
        for i in zitti:
            time.sleep(3)
            st[i] = stato(camp[i])
        r = classifica_link(list(zip(camp, st)))
        det = (f"{len(camp)} provati, {len(r['rotti'])} rotti, {len(r['dubbi'])} che rifiutano i controlli automatici, "
               f"{len(r['senza_risposta'])} senza risposta (non verificati)")
        if r["rotti"]:
            det += " · " + "; ".join(f"{u} ({s})" for u, s in r["rotti"][:4])
        getattr(v, giudizio_link(r))("Events: link alle biglietterie", det)

    def places():
        rs, _ = prendi(B["places"] + "sitemap-1.xml", timeout=60)
        com = [u for u in re.findall(r"<loc>([^<]+)</loc>", rs.text) if "/comune/" in u]
        if LOCALE:
            com = [u.replace("https://achplaces.com/", B["places"]) for u in com]
        interni = set()
        for u in random.sample(com, 3 if LIV == 2 else 12):
            r, _ = prendi(u)
            if r is None:
                continue
            for hrf in re.findall(r'href="([^"#]+)"', r.text):
                a = urllib.parse.urljoin(u, hrf)
                if urllib.parse.urlparse(a).netloc == urllib.parse.urlparse(B["places"]).netloc:
                    interni.add(a)
        camp = random.sample(sorted(interni), min(len(interni), 40 if LIV == 2 else 200))
        with cf.ThreadPoolExecutor(10) as ex:
            st = list(ex.map(stato, camp))
        rotti = [u for u, s in zip(camp, st) if s != 200]
        v.se(not rotti, "Places: link interni delle pagine dei comuni", f"{len(camp)} provati" + (f", rotti: {rotti[:4]}" if rotti else ""))

    protetto(v, "Events: link alle biglietterie", events)
    protetto(v, "Places: link interni", places)


# ---------------------------------------------------------------- 8. sicurezza e riservatezza
# parole che non devono comparire nelle pagine pubbliche: qui solo l'impronta, non la parola
VIETATE = {"05b9115df05a", "0b3ef42fc746", "5f6fc0fcf25a", "cf439fc4887d", "e4d6dc0f6e28"}
CHIAVI = re.compile(r"AIza[0-9A-Za-z_\-]{35}|gh[pousr]_[0-9A-Za-z]{36}|github_pat_[0-9A-Za-z_]{40,}|-----BEGIN [A-Z ]*PRIVATE KEY|xox[baprs]-[0-9A-Za-z-]{20,}|sk-ant-[0-9A-Za-z_-]{20,}")


def vista_sicurezza():
    v = Vista("Sicurezza e riservatezza", "Niente chiavi né dati personali in pubblico, pagine di servizio fuori da Google")
    vietate = set(filter(None, os.environ.get("VER_VIETATE", "").split(","))) or VIETATE
    pagine = [B[g] + p for g in B for p in ("", "chi-siamo/", "privacy/")] + [B["events"] + "milano/"]
    for u in pagine:
        r, _ = prendi(u)
        if r is None or r.status_code != 200:
            continue
        testo = re.sub(r"<script[\s\S]*?</script>|<style[\s\S]*?</style>|<[^>]+>", " ", r.text)
        parole = set(re.findall(r"[a-zà-ù]{4,}", testo.lower()))
        trovate = [w for w in parole if hashlib.sha256(w.encode()).hexdigest()[:12] in vietate]
        v.se(not trovate, f"Nessun nome o indirizzo riservato in {u.replace('https://', '')}", f"{len(trovate)} parole riservate trovate")
        ch = CHIAVI.findall(r.text)
        v.se(not ch, f"Nessuna chiave nel codice di {u.replace('https://', '')}", f"{len(ch)} stringhe che sembrano chiavi")
    for g in B:
        r, _ = prendi(B[g] + "statistiche.html")
        if r is not None and r.status_code == 200:
            v.se("noindex" in r.text.lower(), f"{g}: la pagina delle statistiche è esclusa da Google", grave=False)
    if not LOCALE:
        for g in B:
            r, _ = prendi(B[g])
            hsts = (r.headers.get("strict-transport-security") if r is not None else None)
            v.se(bool(hsts), f"{g}: il browser è obbligato a usare la connessione sicura (HSTS)", grave=False)
    # il codice pubblico, se il flusso lo ha scaricato (livello 3)
    radice = os.environ.get("VER_CODICE", "")
    if radice and os.path.isdir(radice):
        n = trovati = 0
        dove = []
        for cart, _, files in os.walk(radice):
            if "/.git" in cart:
                continue
            for f in files:
                if not f.endswith((".py", ".js", ".yml", ".yaml", ".json", ".html", ".md", ".txt", ".toml", ".sh", ".csv")):
                    continue
                pth = os.path.join(cart, f)
                try:
                    if os.path.getsize(pth) > 3_000_000:
                        continue
                    t = open(pth, errors="ignore").read()
                except Exception:
                    continue
                n += 1
                if CHIAVI.search(t):
                    trovati += 1
                    dove.append(pth.replace(radice, "")[:80])
        v.se(trovati == 0, "Nessuna chiave nel codice dei repository pubblici", f"{n} file letti" + (f"; da guardare: {dove[:5]}" if dove else ""))


# ---------------------------------------------------------------- 9. struttura (livello 3)
def vista_struttura():
    v = Vista("Struttura del codice", "Misure semplici sul codice pubblico: dimensioni, prove automatiche, programmi pianificati")
    radice = os.environ.get("VER_CODICE", "")
    if not (radice and os.path.isdir(radice)):
        v.avviso("Saltata", "codice non scaricato")
        return
    for repo in sorted(os.listdir(radice)):
        base = os.path.join(radice, repo)
        if not os.path.isdir(base):
            continue
        wf = os.path.join(base, ".github", "workflows")
        flussi = [f for f in os.listdir(wf)] if os.path.isdir(wf) else []
        cron = senza_tempo = 0
        for f in flussi:
            t = open(os.path.join(wf, f), errors="ignore").read()
            cron += len(re.findall(r"cron:", t))
            if "timeout-minutes" not in t:
                senza_tempo += 1
        v.ok(f"{repo}: programmi automatici", f"{len(flussi)} programmi, {cron} orari pianificati")
        v.se(senza_tempo == 0, f"{repo}: ogni programma ha un tempo massimo", f"{senza_tempo} senza limite di tempo", grave=False)
        ix = os.path.join(base, "index.html")
        if os.path.exists(ix):
            kb = os.path.getsize(ix) // 1024
            v.se(kb <= 400, f"{repo}: peso della pagina principale", f"{kb} KB", grave=False)
        prove = sum(1 for c, _, fs in os.walk(base) if "/.git" not in c for f in fs if re.match(r"(test_|prove_).*\.py$|.*_test\.py$", f))
        v.se(prove > 0, f"{repo}: prove automatiche del codice", f"{prove} file di prove", grave=False)


def main():
    t0 = time.time()
    passi = [vista_pagine, vista_dati, vista_citta, vista_servizi, vista_velocita, vista_automazioni]
    if LIV >= 2:
        passi += [vista_funzioni, vista_link, vista_sicurezza]
    if LIV >= 3:
        passi += [vista_struttura]
    for fn in passi:
        try:
            fn()
        except Exception as e:
            Vista(fn.__name__, "").errore("La verifica si è interrotta", f"{type(e).__name__}: {e}")
    scadute = applica_eccezioni(VISTE, leggi_eccezioni(), datetime.date.today())
    if scadute:
        v = Vista("Eccezioni accettate", "Le voci di scripts/verifica_eccezioni.json: ognuna ha una scadenza")
        for e in scadute:
            v.avviso("Eccezione scaduta: va chiusa o rinnovata con il sì di Stefano", f"{', '.join(e['contiene'])} (scaduta il {e['scade']})")
    tutti = [c for vi in VISTE for c in vi["controlli"]]
    noti = sum(c["esito"] == "ok" and c["dettaglio"].startswith("noto,") for c in tutti)
    err = sum(c["esito"] == "errore" for c in tutti)
    avv = sum(c["esito"] == "avviso" for c in tutti)
    rapporto = {"quando": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "livello": LIV,
                "richiesta": RICHIESTA, "durata_secondi": round(time.time() - t0),
                "esito": "rosso" if err else "giallo" if avv else "verde",
                "controlli": len(tutti), "errori": err, "avvisi": avv, "noti": noti, "viste": VISTE}
    json.dump(rapporto, open(OUT, "w"), ensure_ascii=False, indent=1)
    print(f"livello {LIV}: {len(tutti)} controlli, {err} errori, {avv} avvisi, {rapporto['durata_secondi']} s")
    for vi in VISTE:
        for c in vi["controlli"]:
            if c["esito"] != "ok":
                print(f"  [{c['esito']}] {vi['nome']} · {c['nome']} · {c['dettaglio']}")


if __name__ == "__main__":
    main()
