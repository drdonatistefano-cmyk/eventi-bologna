#!/usr/bin/env python3
"""Mappa delle fonti di Events: consultarla, tenerla in ordine, sapere che cosa guardare (28/11/2026).

Stefano, 28/11 14:26: «Lavora per mappare tutte le fonti affinché possano essere consultate agevolmente ogni volta che si
cerca aggiornamenti. Organizzale in modo efficiente. Fai in modo che il controllo sia gratis o super economico».

La mappa è dati/fonti.json (elenco unico). Il controllo costa zero:
  - le pagine con «sorveglia»: true le legge la sentinella la domenica e il mercoledì sera su GitHub (repository pubblico, minuti gratuiti)
    e dice quali sono cambiate e quali link sono comparsi; poi il flusso Cartelloni le apre con un browser;
  - Claude apre solo le pagine cambiate (--novita); le altre fonti si leggono dall'officina, gratis, solo quando servono (--url).

Uso:
  python3 scripts/fonti.py                 riepilogo per città: quante fonti, di che tipo, che cosa coprono
  python3 scripts/fonti.py --citta fi      tutte le fonti di una città (pagine, flussi, buchi noti)
  python3 scripts/fonti.py --novita [fi]   che cosa è cambiato all'ultima sentinella (pagine cambiate e link nuovi)
  python3 scripts/fonti.py --url fi        gli indirizzi da passare all'officina (segnaposti già riempiti per oggi)
  python3 scripts/fonti.py --md            scrive dati/FONTI.md (la mappa da leggere)
  python3 scripts/fonti.py --scrivi        rigenera dati/sentinella.json dalla mappa (lo usano sentinella e cartelloni)
  python3 scripts/fonti.py --controlla     la mappa è in ordine? (esce con 1 se no; lo usa prova_verifica.py)
"""
import datetime
import json
import os
import re
import sys

QUI = os.path.dirname(os.path.abspath(__file__))
RADICE = os.path.dirname(QUI)
sys.path.insert(0, QUI)
import citta_cfg as CC  # noqa: E402

MAPPA = os.path.join(RADICE, "dati", "fonti.json")
SENTINELLA = os.path.join(RADICE, "dati", "sentinella.json")
STATO = os.path.join(RADICE, "dati", "sentinella_stato.json")
TIPI = {"aggregatore", "portale", "teatro", "locale", "palazzetto", "cinema", "sport", "biglietteria"}
MESI = "gennaio febbraio marzo aprile maggio giugno luglio agosto settembre ottobre novembre dicembre".split()


def carica(rad=RADICE):
    return json.load(open(os.path.join(rad, "dati", "fonti.json"), encoding="utf-8"))


def pagine(citta=None, sorveglia=None, mappa=None):
    """Pagine della mappa, filtrate per città (sigla) e per «sorveglia». Le voci «tutte» valgono per ogni città."""
    m = mappa or carica()
    return [p for p in m["pagine"]
            if (citta is None or p["citta"] in (citta, "tutte")) and (sorveglia is None or bool(p.get("sorveglia")) == sorveglia)]


def nome_citta(k):
    return "tutte le città" if k == "tutte" else CC.TUTTE.get(k, (k,))[0]


def riempi(u, k, oggi=None):
    """Segnaposti dell'indirizzo per la città k e per oggi ({arte}, {aaaa}, {mm}, {mese_nome}, {provincia}, …)."""
    oggi = oggi or datetime.date.today()
    cfg = CC.CITTA.get(k, {})
    v = {"arte": cfg.get("arte", {"bo": "bologna", "mi": "milano"}.get(k, "")),
         "movieplayer": cfg.get("movieplayer", {"bo": "bologna", "mi": "milano"}.get(k, "")),
         "aaaa": str(oggi.year), "mm": f"{oggi.month:02d}", "mese_nome": MESI[oggi.month - 1],
         "provincia": (cfg.get("cartella") or CC.TUTTE.get(k, ("", ""))[1] or "bologna"),
         "comune": re.sub(r"[^a-z0-9]+", "-", (cfg.get("capo") or CC.TUTTE.get(k, ("",))[0]).lower().replace("ì", "i")).strip("-"),
         "stagione": str(oggi.year if oggi.month >= 7 else oggi.year - 1)}
    return re.sub(r"\{(\w+)\}", lambda m_: v.get(m_.group(1), m_.group(0)), u)


def controlla(rad=RADICE):
    """Errori della mappa: [testo]. Vuota = in ordine."""
    err = []
    try:
        m = carica(rad)
    except Exception as e:
        return [f"dati/fonti.json non si legge: {e}"]
    visti = set()
    for p in m.get("pagine", []):
        for k in ("citta", "nome", "url", "tipo", "copre"):
            if not p.get(k):
                err.append(f"voce senza «{k}»: {p.get('nome') or p.get('url')}")
        if p.get("citta") not in CC.TUTTE and p.get("citta") != "tutte":
            err.append(f"città sconosciuta «{p.get('citta')}»: {p.get('nome')}")
        if p.get("tipo") and p["tipo"] not in TIPI:
            err.append(f"tipo «{p['tipo']}» non previsto: {p.get('nome')}")
        if not str(p.get("url", "")).startswith("https://"):
            err.append(f"indirizzo non https: {p.get('nome')}")
        if p.get("sorveglia") and "{" in p.get("url", ""):
            err.append(f"una pagina sorvegliata non può avere segnaposti: {p.get('nome')}")
        chiave = (p.get("citta"), p.get("url"))
        if p.get("sorveglia") and chiave in visti:
            err.append(f"pagina doppia: {p.get('url')}")
        visti.add(chiave)
    for k in CC.attive(os.path.join(rad, "index.html")):
        if not any(p["citta"] == k and p.get("sorveglia") for p in m.get("pagine", [])):
            err.append(f"{nome_citta(k)}: città accesa senza nessuna pagina sorvegliata")
    for f in m.get("flussi", []):
        if not os.path.exists(os.path.join(rad, ".github", "workflows", f["flusso"])):
            err.append(f"flusso inesistente: {f['flusso']}")
        if not os.path.exists(os.path.join(rad, f["script"])):
            err.append(f"programma inesistente: {f['script']}")
    return err


def sentinella_da_mappa(m):
    """Il contenuto di dati/sentinella.json generato dalla mappa (solo le pagine sorvegliate, con i campi che servono)."""
    out = []
    for p in m["pagine"]:
        if p.get("sorveglia"):
            v = {"citta": p["citta"], "nome": p["nome"], "url": p["url"]}
            if p.get("pdf"):
                v["pdf"] = p["pdf"]
            out.append(v)
    return {"nota": "GENERATO da dati/fonti.json con python3 scripts/fonti.py --scrivi: non cambiarlo a mano. "
                    "Pagine controllate ogni settimana dalla sentinella (scripts/sentinella.py) e aperte dal flusso Cartelloni.",
            "pagine": out}


def riepilogo(m):
    righe = ["Mappa delle fonti di Events (dati/fonti.json)", ""]
    for k in list(CC.TUTTE) + ["tutte"]:
        ps = [p for p in m["pagine"] if p["citta"] == k]
        if not ps:
            continue
        sv = sum(1 for p in ps if p.get("sorveglia"))
        tipi = sorted({p["tipo"] for p in ps})
        copre = sorted({c for p in ps for c in p["copre"]})
        righe.append(f"- {nome_citta(k)}: {len(ps)} fonti ({sv} sorvegliate due volte a settimana) · {', '.join(tipi)} · copre {', '.join(copre)}")
    righe += ["", f"Flussi automatici: {len(m['flussi'])} · buchi noti: {len(m.get('buchi', []))}",
              "Dettaglio: --citta XX · cosa è cambiato: --novita · indirizzi per l'officina: --url XX"]
    return "\n".join(righe)


def dettaglio(m, k):
    r = [f"# Fonti di {nome_citta(k)}", ""]
    for p in pagine(k, mappa=m):
        come = "sorvegliata domenica e mercoledì" if p.get("sorveglia") else "a mano dall'officina"
        r.append(f"- [{p['tipo']}] {p['nome']} — {riempi(p['url'], k)} ({', '.join(p['copre'])}; {come})" + (f"\n    {p['note']}" if p.get("note") else ""))
    r += ["", "Flussi automatici:"]
    for f in m["flussi"]:
        if f["citta"] == "tutte" or k in f["citta"].split():
            r.append(f"- {f['flusso']} ({f['quando']}): {'; '.join(f['fonti'])}")
    b = [x["cosa"] for x in m.get("buchi", []) if x["citta"] in (k, "tutte")]
    if b:
        r += ["", "Buchi noti:"] + [f"- {x}" for x in b]
    return "\n".join(r)


def novita(k=None, rad=RADICE):
    if not os.path.exists(os.path.join(rad, "dati", "sentinella_stato.json")):
        return "La sentinella non ha ancora girato."
    s = json.load(open(os.path.join(rad, "dati", "sentinella_stato.json"), encoding="utf-8"))
    r = [f"Sentinella del {s.get('giorno', '?')}: apri solo queste pagine.", ""]
    for p in s.get("pagine", []):
        if k and p.get("citta") != k:
            continue
        if p.get("esito") in ("cambiata", "nuova"):
            nuovi = p.get("novita", [])
            r.append(f"- [{p.get('citta')}] {p.get('nome')} ({p.get('esito')}) {p.get('url')}")
            for t in nuovi[:12]:
                r.append(f"    + {t}")
    nl = [p for p in s.get("pagine", []) if (not k or p.get("citta") == k) and (str(p.get("esito", "")).startswith("non letta") or "vietata" in str(p.get("esito", "")))]
    if nl:
        r += ["", "Non lette (riprovare dall'officina):"] + [f"- [{p.get('citta')}] {p.get('nome')}: {p.get('esito')}" for p in nl]
    return "\n".join(r) if len(r) > 2 else r[0] + "\nNessuna pagina cambiata."


def markdown(m):
    r = ["# Mappa delle fonti di Events", "",
         "Generata da `dati/fonti.json` con `python3 scripts/fonti.py --md`: si cambia la mappa, non questo file.", "",
         "**Come si controlla, gratis:** ogni domenica e mercoledì sera la sentinella (GitHub, minuti gratuiti del repository pubblico) legge le "
         "pagine sorvegliate e segna quelle cambiate con i link nuovi; il flusso Cartelloni le apre con un browser e legge TicketOne. "
         "Il lunedì basta `python3 scripts/fonti.py --novita` per sapere che cosa aprire. Le fonti «a mano» si leggono dall'officina "
         "(`python3 strumenti/leggi_online.py $(python3 scripts/fonti.py --url XX)` nel repository privato), solo quando servono.", ""]
    for k in list(CC.TUTTE) + ["tutte"]:
        ps = [p for p in m["pagine"] if p["citta"] == k]
        if not ps:
            continue
        r += [f"## {nome_citta(k).capitalize()}", "", "| fonte | tipo | copre | controllo |", "|---|---|---|---|"]
        for p in ps:
            r.append(f"| [{p['nome']}]({p['url']}) | {p['tipo']} | {', '.join(p['copre'])} | {'domenica e mercoledì' if p.get('sorveglia') else "a mano"} |")
        r.append("")
    r += ["## Flussi automatici", "", "| flusso | quando | città | fonti |", "|---|---|---|---|"]
    for f in m["flussi"]:
        r.append(f"| `{f['flusso']}` | {f['quando']} | {f['citta']} | {'; '.join(f['fonti'])} |")
    r += ["", "## Buchi noti", ""] + [f"- **{nome_citta(x['citta'])}**: {x['cosa']}" for x in m.get("buchi", [])]
    r += ["", "## Note sulle fonti", ""] + [f"- **{p['nome']}**: {p['note']}" for p in m["pagine"] if p.get("note")]
    return "\n".join(r) + "\n"


def main(a):
    m = carica()
    if "--controlla" in a:
        e = controlla()
        print("\n".join(e) if e else "Mappa delle fonti in ordine.")
        sys.exit(1 if e else 0)
    if "--scrivi" in a:
        nuovo = json.dumps(sentinella_da_mappa(m), ensure_ascii=False, indent=1) + "\n"
        vecchio = open(SENTINELLA, encoding="utf-8").read() if os.path.exists(SENTINELLA) else ""
        if nuovo != vecchio:
            open(SENTINELLA, "w", encoding="utf-8").write(nuovo)
        print(f"dati/sentinella.json: {len(sentinella_da_mappa(m)['pagine'])} pagine ({'riscritto' if nuovo != vecchio else 'invariato'})")
        return
    if "--md" in a:
        open(os.path.join(RADICE, "dati", "FONTI.md"), "w", encoding="utf-8").write(markdown(m))
        print("scritto dati/FONTI.md")
        return
    k = next((x for x in a if not x.startswith("--")), None)
    if "--novita" in a:
        print(novita(k))
    elif "--url" in a:
        print("\n".join(riempi(p["url"], k) for p in pagine(k, mappa=m) if p["citta"] == k or "{" in p["url"]))
    elif "--citta" in a and k:
        print(dettaglio(m, k))
    else:
        print(riepilogo(m))


if __name__ == "__main__":
    main(sys.argv[1:])
