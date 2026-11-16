"""Prove di scripts/verifica.py: il guardiano prende gli errori veri e non grida per quelli finti?

Uso: python3 scripts/prova_verifica.py   (esce con 1 se una prova fallisce)
Non tocca la rete né i siti (REGOLE §8 quater.3): prova solo le regole con cui la verifica decide.
Gira nel flusso «Verifica delle guide» prima della verifica vera: un guardiano rotto non deve fare il giro.
16/11/2026.
"""
import datetime
import os
import sys

sys.argv = sys.argv[:1]                      # verifica.py legge il livello dagli argomenti: qui non serve
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import verifica as V  # noqa: E402

FALLITE = []


def prova(nome, cond):
    print(("ok    " if cond else "FALLITA ") + nome)
    if not cond:
        FALLITE.append(nome)


# ---------------------------------------------------------------- link delle biglietterie
# 16/11: un link TicketOne che non risponde (codice 0) era contato come rotto. Lezione 6 del §8 bis:
# «non sono riuscito a guardare» non è «non c'è».
r = V.classifica_link([("a", 200), ("b", 404), ("c", 410), ("d", 403), ("e", 0)])
prova("404 e 410 sono rotti", [u for u, _ in r["rotti"]] == ["b", "c"])
prova("403 è un sito che rifiuta i controlli, non un link rotto", [u for u, _ in r["dubbi"]] == ["d"])
prova("nessuna risposta (0) non è un link rotto", [u for u, _ in r["senza_risposta"]] == ["e"])
prova("la quota dei rotti si calcola solo sui link guardati davvero", r["guardati"] == 4)

campione = [("u%d" % i, 200) for i in range(29)] + [("tk", 0)]
prova("un solo link senza risposta su 30 non fa scattare l'avviso", V.giudizio_link(V.classifica_link(campione)) == "ok")
campione = [("u%d" % i, 200) for i in range(28)] + [("x", 404), ("y", 404)]
prova("due link davvero rotti su 30 fanno scattare l'avviso", V.giudizio_link(V.classifica_link(campione)) == "avviso")
campione = [("u%d" % i, 200) for i in range(20)] + [("x%d" % i, 404) for i in range(10)]
prova("un terzo di link rotti è un errore", V.giudizio_link(V.classifica_link(campione)) == "errore")
campione = [("u%d" % i, 200) for i in range(5)] + [("x%d" % i, 0) for i in range(25)]
prova("se quasi nessun link risponde il controllo non dice «tutto bene»", V.giudizio_link(V.classifica_link(campione)) == "avviso")


# ---------------------------------------------------------------- eccezioni accettate (§8 quater.6)
def rapporto():
    return [{"nome": "Sicurezza", "cosa": "", "controlli": [
        {"esito": "avviso", "nome": "places: il browser è obbligato a usare la connessione sicura (HSTS)", "dettaglio": ""},
        {"esito": "avviso", "nome": "events: link alle biglietterie", "dettaglio": "2 rotti"},
        {"esito": "errore", "nome": "dinners: il browser è obbligato a usare la connessione sicura (HSTS)", "dettaglio": ""},
    ]}]


oggi = datetime.date(2026, 11, 16)
voce = {"contiene": ["HSTS", "connessione sicura"], "motivo": "GitHub Pages non lo permette", "dal": "2026-11-16", "scade": "2027-02-16"}
vi = rapporto()
scadute = V.applica_eccezioni(vi, [voce], oggi)
c = vi[0]["controlli"]
prova("un avviso coperto dall'eccezione diventa noto", c[0]["esito"] == "ok" and c[0]["dettaglio"].startswith("noto"))
prova("l'eccezione non copre un avviso che non contiene tutte le sue parole", c[1]["esito"] == "avviso")
prova("l'eccezione non perdona mai un errore", c[2]["esito"] == "errore")
prova("un'eccezione valida non risulta scaduta", scadute == [])

vi = rapporto()
scadute = V.applica_eccezioni(vi, [dict(voce, scade="2026-11-15")], oggi)
prova("un'eccezione scaduta non perdona più nulla", vi[0]["controlli"][0]["esito"] == "avviso")
prova("un'eccezione scaduta viene segnalata", len(scadute) == 1)

vi = rapporto()
V.applica_eccezioni(vi, [{"contiene": [], "motivo": "larga", "scade": "2027-01-01"}], oggi)
prova("un'eccezione senza parole non perdona nulla (sarebbe larga)", all(x["esito"] != "ok" for x in vi[0]["controlli"]))

vi = rapporto()
V.applica_eccezioni(vi, [{"contiene": ["HSTS"], "motivo": "senza scadenza"}], oggi)
prova("un'eccezione senza scadenza non perdona nulla", vi[0]["controlli"][0]["esito"] == "avviso")

prova("il file delle eccezioni si legge e ogni voce ha parole e scadenza",
      all(v.get("contiene") and v.get("scade") and v.get("motivo") for v in V.leggi_eccezioni()))

# ---------------------------------------------------------------- automazioni
# 16/11: un flusso tolto dal repository non deve tenere rosso il rapporto con il suo ultimo giro fallito
giri = [  # dal più recente, come li dà GitHub
    {"name": "Posta della redazione", "path": ".github/workflows/posta.yml", "status": "completed", "conclusion": "failure"},
    {"name": "Cinema", "path": ".github/workflows/cinema.yml", "status": "completed", "conclusion": "success"},
    {"name": "Cinema", "path": ".github/workflows/cinema.yml", "status": "completed", "conclusion": "failure"},
    {"name": "Sport", "path": ".github/workflows/sport.yml", "status": "completed", "conclusion": "failure"},
    {"name": "Sport", "path": ".github/workflows/sport.yml", "status": "in_progress", "conclusion": None},
]
g = V.riassumi_giri(giri, {"cinema.yml", "sport.yml"})
prova("un flusso tolto dal repository non conta", "Posta della redazione" not in g["rotti"] and "Posta della redazione" not in g["falliti"])
prova("un flusso il cui ultimo giro è fallito resta un errore", g["rotti"] == ["Sport"])
prova("un flusso fallito e poi ripartito è solo un avviso", g["falliti"] == {"Cinema": 1, "Sport": 1} and "Cinema" not in g["rotti"])
g = V.riassumi_giri(giri, None)
prova("se l'elenco dei flussi non si legge non si scarta nulla", "Posta della redazione" in g["rotti"])


print(f"\n{len(FALLITE)} prove fallite" if FALLITE else "\nTutte le prove passano")
sys.exit(1 if FALLITE else 0)
