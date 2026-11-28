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
        for c in ("milano", "ravenna", "ferrara", "modena", "forli-cesena", "firenze"):
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
    cambia(d, "scripts/versioni.py", 'CARTELLE = [c or "." for n, c in _CC.TUTTE.values()]', 'CARTELLE = [".", "milano", "ravenna"]')
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
    # 28/11/2026: Modena, Forlì-Cesena e Firenze preparate ma spente
    d = copia()
    avv = [(n, cosa) for liv, n, cosa in CC.controlla(d) if liv == "avviso" and "non accesa" in cosa]
    prova("città: le tre province preparate e spente sono solo avvisi, col nome giusto",
          errori(d) == [] and {n for n, _ in avv} >= {"Modena", "Forlì-Cesena", "Firenze"})
    d = copia()
    s = open(os.path.join(d, "index.html"), encoding="utf-8").read()
    s = _re.sub(r"const CITTA_ATTIVE=\[[^\]]*\]", 'const CITTA_ATTIVE=["bo","mi","ra","fe","mo","fc","fi"]', s)
    open(os.path.join(d, "index.html"), "w", encoding="utf-8").write(s)
    e = errori(d)
    prova("città: accese, le tre province sono collegate dappertutto (manca solo il minimo di eventi)",
          all("eventi" in x and "eventi.js" in x for x in e))   # con i dati del 28/11: nessun errore
    import subprocess as _sp
    d = copia()
    _sp.run([sys.executable, os.path.join(d, "scripts", "citta.py")], cwd=d, capture_output=True)
    leggi = lambda c: open(os.path.join(d, c, "index.html"), encoding="utf-8").read()[:400]  # noqa: E731
    prova("città: una città preparata e spenta ha noindex, una accesa no",
          'name="robots" content="noindex"' in leggi("modena") and 'noindex' not in leggi("ferrara"))
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
    # 25/11/2026 (Stefano: «perché Daniele Tinti non esce nel box in elenco»): «di» che indica chi va in scena
    ("Stand-up di Daniele Tinti.", "Daniele Tinti"), ("Reading di Beatrice Zerbini · Poesia", "Beatrice Zerbini"),
    ("Lectio magistralis di Aldo Cazzullo · Lectio, Storia", "Aldo Cazzullo"), ("Guida all'ascolto di Luca Rebeggiani.", "Luca Rebeggiani"),
    ("Presentazione del libro “MONDOMANIA” di Alessandro La Fauci a eXtraBO", "Alessandro La Fauci"),
    ("Orchestra e Coro della Scala diretti da Myung-Whun Chung.", "dirige Myung-Whun Chung"),
    ("Lezione-concerto su Hindemith con il pianista Andrea Carcano.", "Andrea Carcano"),
    ("Il medico ed epidemiologo Franco Berrino parla di alimentazione.", "Franco Berrino"),
    ("La band di Manuel Agnelli rilegge l'album.", "Manuel Agnelli"),
    # … e «di» che indica l'autore o il soggetto: il nome resta fuori
    ("La commedia di Oscar Wilde con la Compagnia La Ragnatela.", ""), ("Dal film di Fausto Brizzi.", ""),
    ("Sulle canzoni di Umberto Tozzi.", ""), ("Il balletto di Pierre Lacotte.", ""),
    ("Il conflitto tra Antonio Salieri, musicista stimato, e il giovane Mozart.", ""),
]:
    prova(f"protagonisti: «{desc[:40]}» → «{atteso}»", PR.chi({"artista": "Titolo qualsiasi", "descrizione": desc}) == atteso)
# REGOLA 25/11/2026 (Stefano: «fai in modo che non si verifichi più»): sui dati veri di tutte le città nessuna persona
# nominata nella descrizione resta senza nome nel riquadro, a meno che sia chiaramente autore o soggetto o stia in
# dati/nomi_non_protagonisti.txt. Se questa prova fallisce: correggere la regola in protagonisti.py, oppure aggiungere
# il nome a dati/protagonisti_a_mano.txt (è in scena) o a dati/nomi_non_protagonisti.txt (non lo è). Mai saltarla.
_sosp = PR.tutti_i_sospetti(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
prova(f"REGOLA dei nomi: nessuna persona in scena senza nome nel riquadro ({len(_sosp)} da sistemare: "
      + ", ".join(f"{x[0]} {x[1]} {x[3]}" for x in _sosp[:5]) + ")", not _sosp)
prova("protagonisti: elenco a mano usato quando le regole non trovano nessuno",
      PR.chi({"artista": "Faust", "descrizione": "Il Faust visionario di Romeo Castellucci."}) == "regia di Romeo Castellucci")
prova("protagonisti: in un incontro «diretti da» è «a cura di», non «regia di»",
      PR.chi({"id": "i196", "artista": "Seminario", "genere": "Incontri e conferenze", "descrizione": "Seminari di filosofia diretti da Fabio Minazzi."}) == "a cura di Fabio Minazzi")


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

# ---------------------------------------------------------------- giro automatico: arte.it e siti con più sale (23/11/2026)
# Stefano: «sistema tutto e fai in modo che non accada più». Riquadro vero di arte.it (23/11/2026): l'occhiello ha
# dentro <span class="citta">; la vecchia lettura trovava solo «Milano» e scartava tutte le mostre.
import regole_auto as RAU  # noqa: E402
_arte = '''<a href="/calendario-arte/milano/mostra-62-wildlife-photographer-of-the-year-104514" class="link_mostre_list">
 <span class="thumb"><img src="x.jpg" alt="62° Wildlife" /></span><span class="cont_txt">
 <span class="data">Dal 20 Novembre 2026 al 7 Febbraio 2027</span> <span class="occhiello">
 <span class="citta">Milano</span> | Museo della Permanente </span> <span class="title"> <h2>62° Wildlife Photographer of The Year</h2>
 </span> <span class="sommario">Le fotografie naturalistiche pi&ugrave; rinomate...</span> <span class="l_tutto">&nbsp;</span></span></a>'''
_b, _m = RAU.arte_blocchi(_arte)
prova("arte.it: la mostra con l'occhiello annidato si legge (sede, città, date)",
      len(_b) == 1 and _b[0]["sede"] == "Museo della Permanente" and _b[0]["citta"] == "Milano"
      and _b[0]["inizio"] == "2026-11-20" and _b[0]["fine"] == "2027-02-07" and _b[0]["titolo"].startswith("62°"))
_vecchio = _arte.replace('<span class="citta">Milano</span>', 'Milano')
prova("arte.it: anche l'occhiello senza span interno si legge", RAU.arte_blocchi(_vecchio)[0][0]["sede"] == "Museo della Permanente")
prova("arte.it: riquadro senza date contato come scartato, non ignorato in silenzio",
      RAU.arte_blocchi(_arte.replace("Dal 20 Novembre 2026 al 7 Febbraio 2027", ""))[1] == {"senza date": 1})
prova("doppioni: stessa pagina di teatro con più sale = stesso organizzatore",
      RAU.stesso_organizzatore("https://www.tcbo.it/evento/opera/carmen-2027/", "https://www.tcbo.it/"))
prova("doppioni: due biglietterie generali non bastano a dire «stesso spettacolo»",
      not RAU.stesso_organizzatore("https://www.ticketone.it/event/a/", "https://www.ticketone.it/event/b/"))
prova("doppioni: Schiaccianoci alla Scala e al Lirico restano due spettacoli",
      not RAU.stesso_organizzatore("https://www.teatroallascala.org/", "https://www.ticketone.it/artist/balletto-milano/"))
prova("doppioni: fonte su un sottodominio dello stesso teatro (stagione2027.tcbo.it ↔ tcbo.it)",
      RAU.stesso_organizzatore("https://stagione2027.tcbo.it/", "https://www.tcbo.it/evento/danza/tao-dancetheatre-2027/"))
prova("doppioni: due articoli di giornale non dicono «stesso spettacolo»",
      not RAU.stesso_organizzatore("https://www.connessiallopera.it/a/", "https://www.connessiallopera.it/b/"))
prova("doppioni: stessa pagina d'acquisto dell'evento = stesso spettacolo (Ulisse al Comunale, 23/11)",
      RAU.stesso_biglietto("https://tcbo.vivaticket.it/it/event/il-ritorno-di-ulisse-in-patria/316600",
                           "https://tcbo.vivaticket.it/it/event/il-ritorno-di-ulisse-in-patria/316600?x=1"))
prova("doppioni: la pagina di un luogo su una biglietteria non basta",
      not RAU.stesso_biglietto("https://www.ticketone.it/city/bologna-218/venue/teatro-duse-16236/", "https://www.ticketone.it/city/bologna-218/venue/teatro-duse-16236/"))
prova("mostre: allestimenti di anni scartati, mostre vere tenute",
      RAU.permanente("2013-12-03", "2030-12-31", "2026-11-23") and RAU.permanente("2023-06-20", "2028-06-20", "2026-11-23")
      and not RAU.permanente("2026-11-20", "2027-02-07", "2026-11-23") and not RAU.permanente("2026-12-11", "2027-05-02", "2026-11-23"))
_sedi = {"Foyer Rossini": "Teatro Comunale – Foyer Rossini", "Persiceto": ["Teatro Comunale di San Giovanni in Persiceto", "San Giovanni in Persiceto"],
         "Auditorium Manzoni": "Auditorium Manzoni", "Teatro Comunale(?! di)": "Teatro Comunale"}
prova("sala: «Nabucco … Teatro Comunale» va al Comunale, non all'Auditorium Manzoni",
      RAU.sala_da_testo("Nabucco 3, 4, 5 novembre 2027 Teatro Comunale. Biglietti", _sedi, "Auditorium Manzoni") == ("Teatro Comunale", None))
prova("sala: Persiceto porta anche il comune",
      RAU.sala_da_testo("Concerto di Gala 26 novembre Teatro Comunale di San Giovanni in Persiceto", _sedi, "x") == ("Teatro Comunale di San Giovanni in Persiceto", "San Giovanni in Persiceto"))
prova("sala: senza riscontro resta la sala di base", RAU.sala_da_testo("Concerto da camera", _sedi, "Auditorium Manzoni") == ("Auditorium Manzoni", None))
import aggiorna as AGG  # noqa: E402
prova("doppioni: «P.F.M.» e «PFM – Premiata Forneria Marconi» sono lo stesso titolo", AGG.stesso_titolo("P.F.M.", "PFM – Premiata Forneria Marconi"))
prova("doppioni: «Sottotono» e «Sotto Tono», «Jax» e «J-Ax» uniti", AGG.stesso_titolo("Sottotono", "Sotto Tono") and AGG.stesso_titolo("Jax", "J-Ax"))
prova("doppioni: titoli diversi restano diversi", not AGG.stesso_titolo("Bonetti", "Bolero") and not AGG.stesso_titolo("Io", "Iosonouncane"))
_ea = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "eventi_auto.py"), encoding="utf-8").read()
prova("eventi_auto usa la lettura nuova di arte.it e la regola dello stesso organizzatore",
      "RA.arte_blocchi(" in _ea and "RA.stesso_organizzatore(" in _ea and 'e.get("luogo") or luogo' in _ea)

# ---------------------------------------------------------------- descrizioni lette dai siti (23/11/2026)
# Stefano: «usa cobra per cercare descrizioni, link sbagliati da correggere ed ogni azione necessaria per migliorare il
# sito». Casi veri trovati in guida il 23/11: menu dell'Ecoteatro, intestazioni dei Magazzini Generali, contatti del Bravo.
prova("descrizioni: il menu del sito non è una descrizione",
      RAU.pulisci_descrizione("ECOTEATRO THE GALLERY THE FRAME LO STAFF STAGIONE 2026/27 BIGLIETTI E ABBONAMENTI PER LE SCUOLE CORSI DI TEATRO AFFITTA IL TEATRO CONTATTI HOME") == "")
prova("descrizioni: via l'intestazione «TITOLO | LOCALE | DATA | ORE»",
      RAU.pulisci_descrizione("SANTI FRANCESI | MAGAZZINI GEENRALI | 01 APRILE 2027 | ORE 20.00 | MAGAZZINI GENERALI Un viaggio sonoro intimo e potente sta per arrivare.")
      == "Un viaggio sonoro intimo e potente sta per arrivare.")
prova("descrizioni: mai telefoni ed email in guida",
      RAU.pulisci_descrizione("Dettagli a breve… ___ INFO & PRENOTAZIONI: 051 266112 / 333 5973089 info@bravocaffe.it PRENOTA QUI IL TUO TAVOLO PER LA CENA") == "")
prova("descrizioni: la frase tagliata a metà finisce con i puntini, non con «e»",
      RAU.pulisci_descrizione("Diva è un monologo comico che mescola stand-up comedy, autobiografia e") == "Diva è un monologo comico che mescola stand-up comedy, autobiografia…")
prova("descrizioni: data, ora e sala in mezzo al testo vanno via",
      "Sala Puccini" not in RAU.pulisci_descrizione("VOICE TIME I concerti della domenica mattina Domenica 29 novembre ore 11:00 Sala Puccini VOICE TIME Concerti a cura delle classi di canto"))
prova("descrizioni: quelle buone e quelle generiche restano come sono",
      all(RAU.pulisci_descrizione(t) == t for t in ("Con Luca Bizzarri.", "I Double Soul propongono un viaggio nella musica soul.",
                                                   "Serata nel club APOLLO CLUB MILANO.", "Comicità all'ARCA.", "Spettacolo di prosa.")))
prova("eventi_auto ripulisce le descrizioni lette dai siti", _ea.count("RA.pulisci_descrizione(") >= 2)

# ---------------------------------------------------------------- indirizzi senza numero civico (27/11/2026)
import pagine_eventi as PE  # noqa: E402
prova("indirizzi: via e numero insieme", PE.via_civico({"via": "Via Cartoleria", "civico": "42"}) == "Via Cartoleria 42")
prova("indirizzi: senza numero civico solo la via, senza spazio in più",
      PE.via_civico({"via": "Largo Gustav Mahler", "civico": ""}) == "Largo Gustav Mahler")

# ---------------------------------------------------------------- mostre: minimo a mano (28/11/2026)
import json, subprocess as _sp2, tempfile as _tf2
_d = _tf2.mkdtemp()
_m = [dict(titolo=f"Mostra {i}", sede="Museo Civico San Domenico", citta="Forlì", inizio="2026-11-01", fine="2027-01-10",
           categoria="Pittura", descrizione="Mostra di pittura", ingresso="da verificare", orari="", fonte="https://example.org/" + str(i),
           sito="", biglietti="", biglietti_tipo="") for i in range(3)]
json.dump(_m, open(os.path.join(_d, "mostre.json"), "w"))
_ag = os.path.join(os.path.dirname(os.path.abspath(__file__)), "aggiorna.py")
_r1 = _sp2.run([sys.executable, _ag, "mostre.json", "--mostre", "--citta", "fc", "--oggi", "2026-11-28"], cwd=_d, capture_output=True)
_r2 = _sp2.run([sys.executable, _ag, "mostre.json", "--mostre", "--citta", "fc", "--oggi", "2026-11-28", "--minimo", "3"], cwd=_d, capture_output=True)
prova("mostre: 3 mostre senza --minimo non si scrivono, con --minimo 3 sì", _r1.returncode == 1 and _r2.returncode == 0)

print(f"\n{len(FALLITE)} prove fallite" if FALLITE else "\nTutte le prove passano")
sys.exit(1 if FALLITE else 0)
