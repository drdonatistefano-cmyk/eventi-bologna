"""Pagine leggibili su GitHub con le visite delle tre guide (Dinners e Places dal 9/11/2026, Events dall'11/11),
stesso formato stretto, leggibile anche su iPhone; il dettaglio dei clic di Events resta in dati/statistiche.md.
uso: python3 scripts/visite_md.py [dati/visite_guide.json]
Scrive dati/visite_events.md, dati/visite_dinners.md e dati/visite_places.md (tabella per giorno, totali, ultima lettura)."""
import json, sys, datetime

src = sys.argv[1] if len(sys.argv) > 1 else "dati/visite_guide.json"
righe = json.load(open(src))
MESI = "gen feb mar apr mag giu lug ago set ott nov dic".split()
GIORNI = "lun mar mer gio ven sab dom".split()
def gg(s):
    d = datetime.date.fromisoformat(s); return f"{GIORNI[d.weekday()]} {d.day} {MESI[d.month-1]} {d.year}"

for guida, file in (("Ach's Events Guide", "dati/visite_events.md"), ("Ach's Dinners Guide", "dati/visite_dinners.md"), ("Ach's Places Guide", "dati/visite_places.md")):
    r = [x for x in righe if x["guida"] == guida]
    sito = r[0]["sito"] if r else ""
    letto = max((x.get("letto") or "" for x in r), default="")
    try:
        lt = datetime.datetime.fromisoformat(letto).astimezone(datetime.timezone(datetime.timedelta(hours=1)))
        letto_txt = f"{gg(lt.date().isoformat())} alle {lt:%H:%M} (ora italiana)"
    except Exception:
        letto_txt = "—"
    g = sorted([x for x in r if x.get("giorno") and x.get("visite") is not None], key=lambda x: x["giorno"])
    out = [f"# {guida} – visite", "", f"Sito: https://{sito}/ · dati GoatCounter, aggiornati ogni 15 minuti · ultima lettura: {letto_txt}", ""]
    if not g:
        stato = next((x["stato"] for x in r if x.get("stato") != "ok"), "nessun dato ancora")
        out += [f"**Nessun dato:** {stato}.", ""]
    else:
        tot = sum(x["visite"] for x in g); sette = sum(x["visite"] for x in g[-7:])
        out += ["| Oggi | Ultimi 7 giorni | Dal lancio |", "|---:|---:|---:|", f"| {g[-1]['visite']} | {sette} | {tot} |", "",
                "## Visite per giorno", "", "| Giorno | Visite |", "|---|---:|"]
        out += [f"| {gg(x['giorno'])} | {x['visite']} |" for x in reversed(g)]
        out += ["", "Visite = pagine viste (senza clic e filtri). Giorni in ora UTC, come GoatCounter."]
        if guida == "Ach's Events Guide":
            out += ["", "Clic su biglietti, filtri e provenienze: [statistiche.md](statistiche.md)."]
    open(file, "w").write("\n".join(out) + "\n")
    print(file, len(g), "giorni")
