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
# 20/11: un flusso col file illeggibile fallisce con il nome uguale al percorso; corretto, i giri buoni hanno il nome vero
giri = [
    {"name": "Controllo link biglietti", "path": ".github/workflows/controllo_biglietti.yml", "status": "completed", "conclusion": "success"},
    {"name": ".github/workflows/controllo_biglietti.yml", "path": ".github/workflows/controllo_biglietti.yml", "status": "completed", "conclusion": "failure"},
    {"name": ".github/workflows/controllo_biglietti.yml", "path": ".github/workflows/controllo_biglietti.yml", "status": "completed", "conclusion": "failure"},
]
g = V.riassumi_giri(giri, {"controllo_biglietti.yml"})
prova("un flusso corretto dopo giri falliti col nome del file non resta rosso", g["rotti"] == [] and g["falliti"] == {"Controllo link biglietti": 2})


# ---------------------------------------------------------------- parti comuni delle guide (REGOLE §8 sexies.3)
prova("tre copie uguali di installa.js: nessuna differenza", V.copie_diverse({"places": b"x", "dinners": b"x", "events": b"x"}) == [])
prova("una copia diversa si vede e si sa quale", V.copie_diverse({"places": b"x", "dinners": b"y", "events": b"x"}) == ["dinners"])
prova("una copia che non si è potuta scaricare non conta come diversa", V.copie_diverse({"places": b"x", "dinners": None, "events": b"x"}) == [])


# ---------------------------------------------------------------- città di Events (18/11/2026)
# Una città accesa a metà compare nel selettore e resta vuota o ferma. Si prende una copia dei file veri
# e ci si mette un guasto alla volta: il controllo deve accorgersene (lezione 5 del §8 bis).
import re as _re
import shutil as _sh
import tempfile as _tf
import controlla_citta as CC  # noqa: E402

RAD = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if os.path.exists(os.path.join(RAD, "index.html")) and os.path.isdir(os.path.join(RAD, ".github")):
    def copia():
        d = _tf.mkdtemp()
        _sh.copy(os.path.join(RAD, "index.html"), d)
        for sub in ("scripts", os.path.join(".github", "workflows")):
            _sh.copytree(os.path.join(RAD, sub), os.path.join(d, sub))
        os.makedirs(os.path.join(d, "dati"))
        _sh.copy(os.path.join(RAD, "dati", "sentinella.json"), os.path.join(d, "dati"))
        for c in ("milano", "ravenna", "ferrara"):
            os.makedirs(os.path.join(d, c))
            for f in CC.DATI_PAGINA:
                if os.path.exists(os.path.join(RAD, c, f)):
                    _sh.copy(os.path.join(RAD, c, f), os.path.join(d, c))
        return d

    def cambia(d, f, a, b):
        p = os.path.join(d, f)
        s = open(p, encoding="utf-8").read()
        open(p, "w", encoding="utf-8").write(s.replace(a, b, 1))

    def errori(d):
        return [cosa for liv, _, cosa in CC.controlla(d) if liv == "errore"]

    d = copia()
    prova("città: le città di oggi sono collegate (nessun errore)", errori(d) == [])
    cambia(d, "scripts/versioni.py", '"ferrara"', '"x"')
    prova("città: una città tolta da versioni.py si vede", any("versioni.py" in e for e in errori(d)))
    d = copia()
    open(os.path.join(d, "ravenna", "eventi.js"), "w").write('window.EVENTI_DATA={"aggiornato":"","eventi":[]};')
    prova("città: una città accesa ma vuota è un errore", any("vuota" in e for e in errori(d)))
    d = copia()
    os.remove(os.path.join(d, "ferrara", "mostre.js"))
    prova("città: un file dei dati che manca si vede", any("ferrara/mostre.js" in e for e in errori(d)))
    d = copia()
    s = open(os.path.join(d, "index.html"), encoding="utf-8").read()
    s = _re.sub(r"const CITTA_ATTIVE=\[[^\]]*\]", 'const CITTA_ATTIVE=["bo","mi","ra","fe","rn"]', s)
    s = s.replace("const CITTA_CFG={", 'const CITTA_CFG={\n rn:{k:"rn",sigla:"RN",nome:"Rimini",path:"/rimini/"},', 1)
    open(os.path.join(d, "index.html"), "w", encoding="utf-8").write(s)
    e = errori(d)
    prova("città: Rimini accesa solo in index.html dà molti errori (citta.py, versioni, flussi, file, verifica)",
          len([x for x in e if "citta.py" in x or "versioni" in x or "eventi_auto" in x or "rimini/index.html" in x or "verifica.py" in x]) >= 5)
    d = copia()
    cambia(d, ".github/workflows/eventi_auto.yml", "ravenna/", "x/")
    cambia(d, ".github/workflows/eventi_auto.yml", "ravenna/", "x/")
    prova("città: un flusso che non salva più la città si vede", any("eventi_auto.yml" in x for x in errori(d)))
else:
    print("(prove delle città saltate: file del repository non presenti)")

oggi = datetime.date(2026, 12, 20)
righe = [{"giorno": "2026-12-%02d" % g, "sito": s, "visite": 200} for g in range(1, 21) for s in ("a", "b", "c")]
prova("soglia province: si contano le tre guide, oggi escluso", V.visite_ultimi_30(righe, oggi) == (19 * 600, 19))
prova("soglia province: i giorni più vecchi di 30 non contano",
      V.visite_ultimi_30([{"giorno": "2026-11-01", "sito": "a", "visite": 99999}], oggi) == (0, 0))

# ---------------------------------------------------------------- controllo dei link dei biglietti (19/11/2026)
# Il 15/11 il controllo aveva 140 link «non letti»: riletti con un browser, 60 Vivaticket su 71 portavano allo
# spettacolo giusto; i rotti veri erano pochi (404, dominio che non esiste, «evento non disponibile»).
import controlla_biglietti as CB  # noqa: E402
prova("biglietti: 404 e 410 sono rotti", CB.rotto_da("HTTP Error 404: Not Found") and CB.rotto_da(stato=410))
prova("biglietti: un dominio che non esiste è rotto", CB.rotto_da("<urlopen error [Errno -2] Name or service not known>"))
prova("biglietti: «evento non disponibile» sulla pagina è rotto", CB.rotto_da(stato=200, testo="EVENTO NON DISPONIBILE"))
prova("biglietti: 403, 302 in giro, 502 e tempi scaduti non sono rotti",
      not any(CB.rotto_da(e) for e in ("HTTP Error 403: Forbidden", "HTTP Error 302: The HTTP server returned a redirect",
                                        "HTTP Error 502: Bad Gateway", "TimeoutError", "saltato: sito lento o che rifiuta")))
prova("biglietti: una pagina normale non è rotta", not CB.rotto_da(stato=200, testo="ADDUE Teatro Dehon giovedì 19 novembre"))
ev = [{"data": "2026-11-19", "fino": "2026-11-19"}]
prova("biglietti: la data giusta è ok, una sola", CB.esito_date(ev, ["2026-11-19"]) == "ok")
prova("biglietti: date diverse sono «data diversa»", CB.esito_date(ev, ["2026-12-01"]) == "data diversa")
prova("biglietti: il controllo legge anche Ferrara e Ravenna", {"fe", "ra"} <= set(CB.CARTELLE.values()))


# ---------------------------------------------------------------- protagonisti (19/11/2026)
# Esempi veri segnalati da Stefano: il nome deve uscire; e casi che non devono diventare un nome.
import protagonisti as PR  # noqa: E402
for desc, atteso in [
    ("Gli Appiccicaticci: Tiziano Storti e Maria Pia Timo.", "Tiziano Storti e Maria Pia Timo"),
    ("Maria Pia Timo.", "Maria Pia Timo"),
    ("Ambra Angiolini dal testo di Stefano Benni.", "Ambra Angiolini"),
    ("Debora Caprioglio, Tiziana Foschi, Giancarlo Ratti.", "Debora Caprioglio, Tiziana Foschi e Giancarlo Ratti"),
    ("Di Leonardo Manzan.", ""), ("Da Joseph Conrad, Sala Fassbinder.", ""), ("Into The Beginning.", ""),
    ("Teatro Comico al Teatro Alighieri.", ""), ("Palazzo Pepoli in festa.", ""),
    # 20/11/2026 (Stefano: «manca Marta Ciappina; tutto deve funzionare con i nomi»): regola generale sui nomi di persona
    ("Marta Ciappina diretta da Marco D'Agostin.", "Marta Ciappina, regia di Marco D'Agostin"),
    ("Marco Paolini, teatro civile sull'acqua.", "Marco Paolini"),
    ("Il comico Francesco Baruto porta in scena il suo personaggio Nonna Marisa.", "Francesco Baruto"),
    ("Con Vorticerosa, Fabiano Ambu, Francesco Matteuzzi e Juan Carlos Acuña Gaso.", "Fabiano Ambu, Francesco Matteuzzi e Juan Carlos Acuña Gaso"),
    ("Conferenza-spettacolo della criminologa Roberta Bruzzone.", "Roberta Bruzzone"),
    ("Omaggio gospel a Whitney Houston e Tina Turner.", ""), ("Al Teatro Gian Carlo Menotti.", ""),
    ("Michael Jordan, un giocatore iconico.", ""), ("Testo di Luigi Pirandello.", ""),
    ("Cosa vede il giovane Michelangelo Merisi, detto il Caravaggio?", ""),
]:
    prova(f"protagonisti: «{desc[:40]}» → «{atteso}»", PR.chi({"artista": "Titolo qualsiasi", "descrizione": desc}) == atteso)


# ---------------------------------------------------------------- clic «Biglietti» con il sito di arrivo (20/11/2026)
# I clic portano anche il dominio del partner: le statistiche devono continuare a contarli come «clic biglietti».
import statistiche as ST  # noqa: E402
prova("clic Biglietti col dominio contato come clic biglietti",
      ST.tipo_evento("spettacoli/clic-biglietti/ticketone.it/Vasco") == "clic biglietti")
prova("clic Biglietti di Milano col dominio contato come clic biglietti",
      ST.tipo_evento("milano/spettacoli/clic-biglietti/vivaticket.com/Carmen") == "clic biglietti")
prova("clic Biglietti di Ferrara e Ravenna contati (prima finivano in «altro»)",
      ST.tipo_evento("ferrara/spettacoli/clic-biglietti/ticketone.it/X") == "clic biglietti"
      and ST.tipo_evento("ravenna/spettacoli/clic-biglietti/vivaticket.com/Y") == "clic biglietti")
prova("clic Info resta clic info", ST.tipo_evento("spettacoli/clic-info/Carmen") == "clic info spettacoli")
_ix = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "index.html")
if os.path.exists(_ix):
    _t = open(_ix, encoding="utf-8").read()
    prova("index.html registra il sito di arrivo nei clic Biglietti", "clic-biglietti/${domBigl(a)}" in _t and "function domBigl" in _t)

print(f"\n{len(FALLITE)} prove fallite" if FALLITE else "\nTutte le prove passano")
sys.exit(1 if FALLITE else 0)
