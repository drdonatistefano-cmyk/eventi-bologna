"""Eventi a Bologna – esporta le statistiche di GoatCounter nel repository.

Uso (in GitHub Actions o a mano):
  GOATCOUNTER_TOKEN=... python3 scripts/statistiche.py [--dal AAAA-MM-GG] [--al AAAA-MM-GG]

Legge dall'API di GoatCounter (account "eventibologna") visite giornaliere,
pagine ed eventi (clic, filtri, ricerche, condivisioni) e scrive:
  dati/statistiche.json  – numeri completi, per giorno e per settimana dal lancio
  dati/statistiche.md    – riepilogo leggibile
Senza GOATCOUNTER_TOKEN non scrive nulla ed esce senza errore.
"""
import json, os, sys, re, datetime, urllib.request, urllib.parse, urllib.error, collections

SITO = os.environ.get("GOATCOUNTER_SITE", "eventibologna")
LANCIO = "2026-11-04"
API = f"https://{SITO}.goatcounter.com/api/v0"


def chiedi(percorso, **param):
    url = f"{API}{percorso}?" + urllib.parse.urlencode(param, doseq=True)
    req = urllib.request.Request(url, headers={
        "Authorization": "Bearer " + os.environ["GOATCOUNTER_TOKEN"],
        "Content-Type": "application/json", "User-Agent": "eventi-bologna-statistiche"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        print(f"Errore {e.code} da GoatCounter su {percorso}: {e.read().decode('utf-8', 'replace')[:500]}")
        raise


def ora_iso(giorno, fine=False):
    """GoatCounter vuole data e ora RFC 3339 arrotondate all'ora, non nel futuro."""
    d = datetime.datetime.fromisoformat(giorno).replace(tzinfo=datetime.timezone.utc)
    if fine:
        d = min(d + datetime.timedelta(days=1), datetime.datetime.now(datetime.timezone.utc).replace(minute=0, second=0, microsecond=0))
    return d.strftime("%Y-%m-%dT%H:%M:%SZ")


def tipo_evento(path):
    """Raggruppa i percorsi degli eventi registrati da index.html."""
    p = path.strip("/").lower()
    if p.startswith("condividi/"): return "condivisioni"
    if p.startswith("scheda/"): return "cambio scheda"
    m = re.match(r"^(spettacoli|mostre)/(.+)$", p)
    if not m: return "altro"
    scheda, resto = m.groups()
    if resto.startswith("clic-"):
        lab = resto[5:].split("/")[0]
        if scheda == "spettacoli" and lab in ("acquista", "biglietteria"): return "clic biglietti"
        if scheda == "spettacoli" and lab == "info": return "clic info spettacoli"
        if scheda == "mostre": return "clic mostre (scheda o sito)"
        return f"clic {lab}"
    for pref, nome in (("filtro/", "filtri"), ("ricerca/", "ricerche"), ("luogo/", "luoghi aperti"),
                       ("vista/", "cambio vista"), ("mostra-altri", "mostra altri"),
                       ("azzera-filtri", "azzera filtri"), ("apri-filtri", "apri filtri")):
        if resto.startswith(pref): return nome
    return "altro"


def main():
    if not os.environ.get("GOATCOUNTER_TOKEN"):
        print("GOATCOUNTER_TOKEN non impostato: niente da fare."); return
    a = sys.argv[1:]
    oggi = datetime.date.today()
    dal = a[a.index("--dal") + 1] if "--dal" in a else LANCIO
    al = a[a.index("--al") + 1] if "--al" in a else oggi.isoformat()

    try:
        me = chiedi("/me"); print("Collegato a GoatCounter come", me.get("email", "?"))
    except Exception:
        pass
    s0, s1 = ora_iso(dal), ora_iso(al, fine=True)
    tot = chiedi("/stats/total", start=s0, end=s1)
    hits, dopo = [], None
    for _ in range(10):  # pagine da 100 percorsi
        par = dict(start=s0, end=s1, limit=100, daily="true")
        if dopo: par["exclude_paths"] = ",".join(str(h["path_id"]) for h in hits if "path_id" in h)
        r = chiedi("/stats/hits", **par); hits += r.get("hits", [])
        if not r.get("more"): break
        dopo = True
    giorni = collections.Counter()
    for h in hits:  # visite per giorno = somma delle pagine viste (non eventi)
        if not h.get("event"):
            for s in h.get("stats", []) or []:
                giorni[s["day"][:10]] += s.get("daily", 0)
    pagine, eventi = [], collections.Counter()
    eventi_giorno = collections.defaultdict(collections.Counter)
    for h in hits:
        voce = {"path": h.get("path", ""), "titolo": h.get("title", ""), "conteggio": h.get("count", 0)}
        if h.get("event"):
            t = tipo_evento(voce["path"]); voce["tipo"] = t
            eventi[t] += voce["conteggio"]
            for s in h.get("stats", []) or []:
                eventi_giorno[s["day"][:10]][t] += s.get("daily", 0)
        pagine.append(voce)
    pagine.sort(key=lambda v: -v["conteggio"])

    try:
        refs = [{"origine": r.get("name") or "(diretto)", "conteggio": r.get("count", 0)}
                for r in chiedi("/stats/toprefs", start=s0, end=s1).get("stats", [])]
    except Exception as e:  # le provenienze sono un di più
        refs = [{"errore": str(e)}]

    # settimane dal lancio (settimana 1 = i primi 7 giorni dal 4/11/2026)
    l0 = datetime.date.fromisoformat(LANCIO)
    sett = collections.defaultdict(lambda: collections.Counter())
    for d, n in giorni.items():
        k = (datetime.date.fromisoformat(d) - l0).days // 7 + 1
        if k >= 1: sett[k]["visite"] += n
    for d, c in eventi_giorno.items():
        k = (datetime.date.fromisoformat(d) - l0).days // 7 + 1
        if k >= 1: sett[k].update(c)
    settimane = []
    for k in sorted(sett):
        inizio = l0 + datetime.timedelta(days=7 * (k - 1))
        settimane.append({"settimana": k, "dal": inizio.isoformat(),
                          "al": min(inizio + datetime.timedelta(days=6), datetime.date.fromisoformat(al)).isoformat(), **sett[k]})

    out = {"generato": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
           "dal": dal, "al": al, "visite_totali": sum(giorni.values()), "totale_goatcounter": tot.get("total"),
           "eventi_totali": tot.get("total_events", sum(eventi.values())),
           "eventi_per_tipo": dict(eventi.most_common()), "settimane": settimane,
           "eventi_per_giorno": {d: dict(c) for d, c in sorted(eventi_giorno.items())},
           "giorni": [{"giorno": d, "visite": giorni[d]} for d in sorted(giorni)],
           "provenienze": refs[:20], "pagine_ed_eventi": pagine[:200]}
    os.makedirs("dati", exist_ok=True)
    json.dump(out, open("dati/statistiche.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    r = [f"# Statistiche del sito – dal {dal} al {al}", "",
         f"Aggiornate il {out['generato'][:16].replace('T', ' ')} UTC da GoatCounter ({SITO}).", "",
         f"- Visite totali: **{out['visite_totali']}**", f"- Interazioni registrate: **{out['eventi_totali']}**", "",
         "## Per settimana dal lancio", "", "| Sett. | Dal | Al | Visite | Clic biglietti | Clic mostre | Filtri | Ricerche | Condivisioni |",
         "|---|---|---|---|---|---|---|---|---|"]
    for s in settimane:
        r.append(f"| {s['settimana']} | {s['dal']} | {s['al']} | {s.get('visite',0)} | {s.get('clic biglietti',0)} | "
                 f"{s.get('clic mostre (scheda o sito)',0)} | {s.get('filtri',0)} | {s.get('ricerche',0)} | {s.get('condivisioni',0)} |")
    r += ["", "## Interazioni per tipo", ""] + [f"- {k}: {v}" for k, v in eventi.most_common()]
    r += ["", "## Provenienze principali", ""] + [f"- {x.get('origine', x.get('errore'))}: {x.get('conteggio', '')}" for x in refs[:10]]
    open("dati/statistiche.md", "w", encoding="utf-8").write("\n".join(r) + "\n")
    print(f"Visite {out['visite_totali']} · interazioni {out['eventi_totali']} · settimane {len(settimane)}")


if __name__ == "__main__":
    main()
