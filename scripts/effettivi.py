"""Converte dati/statistiche.json nelle misure effettive del cruscotto
"Ach's Events Guide – visite attese e reali".

Uso: python3 scripts/effettivi.py [dati/statistiche.json] [effettivi.json] [--con-oggi]

Per ogni periodo del cruscotto già iniziato somma visite e interazioni dei giorni
misurati e scrive una riga per metrica: {periodo, metrica, effettivo, giorni, al}.
I periodi non ancora conclusi escono con "parziale": true e i giorni misurati finora:
il cruscotto li mostra come «in corso» senza confrontarli con l'obiettivo del periodo intero.
"""
import json, sys, datetime

PERIODI = [("Settimana 1", "2026-11-04", "2026-11-10"), ("Settimana 2", "2026-11-11", "2026-11-17"),
           ("Primo mese", "2026-11-04", "2026-12-03"), ("Mese 3 (gennaio 2027)", "2027-01-04", "2027-02-03"),
           ("Mese 6 (aprile 2027)", "2027-04-04", "2027-05-03"), ("Mese 12 (ottobre 2027)", "2027-10-04", "2027-11-03")]
METRICHE = {"Clic sui biglietti": "clic biglietti", "Clic «Info» sugli spettacoli": "clic info spettacoli",
            "Clic sulle mostre": "clic mostre (scheda o sito)", "Uso dei filtri": "filtri",
            "Ricerche": "ricerche", "Condivisioni": "condivisioni"}
COMMISSIONE, PAGINE, RPM = 0.06, 2.5, 1.5  # come in economia.json del cruscotto


def main():
    con_oggi = "--con-oggi" in sys.argv  # per il cruscotto aggiornabile: conta anche il giorno in corso
    sys.argv = [a for a in sys.argv if a != "--con-oggi"]
    src = sys.argv[1] if len(sys.argv) > 1 else "dati/statistiche.json"
    out = sys.argv[2] if len(sys.argv) > 2 else "effettivi.json"
    s = json.load(open(src, encoding="utf-8"))
    oggi = str(s.get("generato", ""))[:10]  # il giorno della lettura non è concluso: non si conta
    visite = {g["giorno"]: g["visite"] for g in s.get("giorni", []) if con_oggi or not oggi or g["giorno"] < oggi}
    giorni_ev = s.get("eventi_per_giorno", {})
    ultimo = max(visite) if visite else None
    righe = []
    for nome, dal, al in PERIODI:
        if not ultimo or ultimo < dal: continue  # periodo non ancora iniziato
        fine = min(al, ultimo)
        parz = fine < al
        gg = [d for d in visite if dal <= d <= fine]
        n_giorni = (datetime.date.fromisoformat(fine) - datetime.date.fromisoformat(dal)).days + 1
        v = sum(visite[d] for d in gg)
        righe.append({"periodo": nome, "metrica": "Visite", "effettivo": v, "giorni": n_giorni, "al": fine, "parziale": parz})
        tot = {k: sum(giorni_ev.get(d, {}).get(t, 0) for d in giorni_ev if dal <= d <= fine) for k, t in METRICHE.items()}
        for k, n in tot.items():
            righe.append({"periodo": nome, "metrica": k, "effettivo": n, "giorni": n_giorni, "al": fine, "parziale": parz})
        ric = round(tot["Clic sui biglietti"] * COMMISSIONE + v * PAGINE * RPM / 1000, 2)
        righe.append({"periodo": nome, "metrica": "Ricavo potenziale", "effettivo": ric, "giorni": n_giorni, "al": fine, "parziale": parz})
    if con_oggi:
        for r in righe: r["letto"] = s.get("generato", "")
    json.dump(righe, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"Scritte {len(righe)} righe in {out} (dati fino al {ultimo})")


if __name__ == "__main__":
    main()
