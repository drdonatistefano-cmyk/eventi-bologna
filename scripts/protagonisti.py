"""Protagonisti di uno spettacolo o di un incontro (campo «chi», regola del 17/11/2026, Stefano).

chi(e) -> stringa breve, es. «Fabio Nobile Quartet con Fabrizio Bosso», «regia di Massimo Popolizio», «dirige Riccardo Muti»,
oppure "" se nella descrizione non ci sono nomi di persone sicuri. Non tocca un «chi» già scritto a mano.
Uso a mano: python3 scripts/protagonisti.py <eventi.js|incontri.js> [--scrivi]
"""
import re, sys, json, unicodedata

def norm(s):
    s = unicodedata.normalize("NFD", str(s or "").lower())
    return re.sub(r"[^a-z0-9]+", " ", "".join(c for c in s if not unicodedata.combining(c))).strip()

U, L = "A-ZÀ-ÖØ-ÞŁŠŽČĆÑ", "a-zà-öø-ÿłšžčćńęąñ"
W = rf"[{U}](?:[{L}]+(?:['’][{U}]?[{L}]+)*|['’][{U}][{L}]+)(?:-[{U}][{L}]+)?(?![{L}])"   # 20/11: mai un nome tagliato a metà parola («Acuñ»);: anche D'Agostin, Dall'Oglio, O'Connor
PART = r"(?:de|De|Di|Da|Del|Dalla|Della|La|Lo|van|Van|von|Von|Mc|dos|da)"
NOME = rf"{W}(?:\s+{PART})?\s+{W}(?:\s+{W}(?:\s+{W})?(?!\s+[{U}]))?"   # 20/11: fino a 4 parole, «Juan Carlos Acuña Gaso»
LISTA = rf"{NOME}(?:\s*(?:,|\be\b|\bed\b|&)\s*{NOME}){{0,3}}"
STOP = set("""teatro teatri sala stagione concerto concerti orchestra orchestre quartetto quartet quintetto trio ensemble coro fondazione
associazione compagnia comune biblioteca museo musei festival rassegna banda accademia conservatorio scuola gruppo band istituto
universita centro casa circolo produzioni produzione cooperativa sociale notte una il la lo gli le un del della dei degli delle
premio cinema film libro libri edizioni editore editrice ensemble filarmonica sinfonica orchestra symphony orchestra quartet big
choir chorus opera balletto ballet dance company teatrale project records music live tour show special guest guests dj
natale capodanno ottobre novembre dicembre gennaio febbraio marzo aprile maggio giugno luglio agosto settembre
bologna milano ravenna ferrara italia italiana italiano europa roma napoli torino firenze venezia emilia romagna
ideato ideazione biglietti biglietto coreografie coreografia scene scenografia costumi luci musiche drammaturgia produzione coproduzione
testo testi traduzione adattamento durata info prenota prenotazioni acquista regia con assistente aiuto disegno suono video foto
librerie libreria coop kollettivo collettivo invisibile
palazzo palazzi villa chiesa basilica oratorio auditorium rocca castello piazza parco arena
into the tour apicoltura acetaia azienda agricola cantina
caffè caffe bar consultorio comitato federazione spazio mostra docente dipartimento psicologa intesa sanpaolo group
they might dancing queen thirty seconds stiamo fresche mamme quart camere""".split())
MAI = set("ingresso ingressi gratuito gratuita sonata sonate due tre quattro on monday tuesday wednesday thursday friday saturday sunday".split())   # mai in un nome, neppure dopo un nome proprio
TITOLI = r"(?:Arcivescovo|Monsignor|Mons\.|Cardinale|Don|Padre|Suor|Fra|Prof\.?|Professor|Professoressa|Dott\.?|Dottor|Dottoressa|Avv\.|Sindaco|Assessore|Assessora|Maestro|Maestra|M°)"
RUOLI = [  # (espressione prima dei nomi, prefisso mostrato)
    (r"special guest|guest star|ospite speciale|feat\.?|featuring|ft\.", "con"),
    (r"di e con|scritto e interpretato da|ideato e interpretato da|con la partecipazione di|con la voce di|voce di", "con"),
    (r"interpretato da|interpretata da|interpreti|in scena|protagonist[ai]", "con"),
    (r"regia(?: e drammaturgia)? di|regia|diretto da|diretta da|dirige|direttore|maestro concertatore", "@"),
    (r"a cura di|presentato da|presenta|modera|introduce|dialoga con|in dialogo con|conversa con|intervengono|interviene|relatore|relatori|incontro con|guidat[ao] da|racconta|raccontano|ne parlano", "con"),
    (r"pianoforte|piano|violino|violoncello|viola|chitarra|sax|soprano|tenore|baritono|mezzosoprano|contralto|basso|clarinetto|flauto|tromba|voce|batteria|contrabbasso|organo|arpa", "con"),
    (r"con", "con"),
]
RX = [(re.compile(rf"(?<![{L}{U}])(?i:{k})\s*[:,]?\s+({LISTA})"), p) for k, p in RUOLI]
# «Emanuela Canepa presenta il suo libro», «Marco Paolini racconta»
VERBO = re.compile(rf"(?:^|[.;:|·]\s*|\b(?:e|con)\s+)({NOME})\s+(?:presenta|presentano|racconta|raccontano|dialoga|dialogano|legge|leggono|porta|portano|interpreta|dirige|guida|accompagna|canta|suona)\b")
# 18/11/2026 (Stefano: «perché a Milano non è uscito il nome di Ambra Angiolini?»): la descrizione comincia con il nome,
# «Ambra Angiolini dal testo di Stefano Benni», «Lella Costa in …», «Toni Servillo torna con …». Solo all'inizio della descrizione.
INIZIO = re.compile(rf"^\s*({NOME})\s+(?:dal testo|da un testo|dai testi|in scena|in |nel |nella |nei |negli |tra |torna|torneranno|è |sono |e la sua|e il suo|e i suoi|alle prese|al pianoforte|alla chitarra)")
# 19/11/2026 (Stefano: «non compare Maria Pia Timo»): la descrizione è solo un elenco di nomi, «Maria Pia Timo.»,
# oppure un nome di compagnia seguito dai due punti, «Gli Appiccicaticci: Tiziano Storti e Maria Pia Timo.»
SOLO_NOMI = re.compile(rf"^\s*(?:[^:.\n]{{2,50}}:\s*)?((?:{NOME})(?:\s*,\s*(?:{NOME}))*(?:\s+e\s+(?:{NOME}))?)\s*\.?\s*$")
# «Nome Cognome, pianoforte»
STRUM = re.compile(rf"({NOME})\s*[,(–-]\s*(?:pianoforte|piano|violino|violoncello|viola|chitarra|sax|soprano|tenore|baritono|mezzosoprano|direttore|voce|clarinetto|flauto|arpa)\b")
FILM = re.compile(r"\b(film|pellicola|omonimo|omonima|romanzo|libro di|canzoni di|musiche di|brani di|repertorio di|omaggio a|tributo a|tribute|dedicat[oa] a|ispirat[oa] a|tratto da|da un'idea di|ricordo di|in memoria di|vita di|storia di)\W*$", re.I)

import os as _os
try:
    PROPRI = {r.strip() for r in open(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "dati", "nomi_propri.txt"), encoding="utf-8")
              if r.strip() and not r.startswith("#")}
except OSError:
    PROPRI = set()
# 20/11/2026 (Stefano: «per l'ennesima volta manca un nome, Marta Ciappina; tutto deve funzionare con i nomi»).
# Regola generale invece di una frase per volta: «Nome Cognome» dove il nome è un nome di persona (dati/nomi_propri.txt) è una persona,
# ovunque sia nella descrizione, tranne quando è l'autore o il soggetto (dopo «di», «da», «su», «omaggio a», …) o un luogo («via», «teatro»…).
PERSONA = re.compile(rf"(?<![{L}{U}'’])(?:{TITOLI}\s+)?({NOME})")
PRIMA_NO = re.compile(r"(?i)(?:\b(?:di|da|dal|dallo|dalla|dei|degli|delle|del|della|su|sul|sulla|a|ad|al|alla|per|via|viale|piazza|piazzale|largo|corso|vicolo|teatro|sala|auditorium|premio|fondazione|istituto|liceo|scuola|cinema|centro|biblioteca|museo|parco|chiesa|basilica|san|santa|santo|dedicat[oa]|omaggio|tributo|memoria|ricordo|tratto|ispirat[oa]|scritt[oa]|libro|romanzo|opera|opere|poesie|lettere|canzoni|musiche|brani|testi|testo|vita|storia|figura|mito|caso|epoca|tempi|anni|secondo|come|contro|oltre)|['’])\s*$")

CODA = set("testo testi voce direttore direttrice astrofisico astrofisica evangelista dopo nz sj regista attore attrice autore autrice scrittore scrittrice giornalista".split())
# nella stessa frase prima del nome: allora è il soggetto o l'autore, non chi è in scena
SOGGETTO = re.compile(r"(?i)\b(?:film|pellicola|omaggi\w*|tribut\w*|musiche|diari|personaggio|socio|morte|negoziatore|detto|tour|storia|vita|leggend\w*|mito|ricord\w*|dedicat\w*|ispirat\w*|giovane|vecchio|celebre)\b")
DOPO_NO = re.compile(r"(?i)^\W{0,3}(?:detto|detta|un giocatore|una giocatrice|il campione|la campionessa|pittore|pittrice|morto|morta|nato|nata|scomparso|scomparsa)\b")

def buono(n, titolo):
    w = n.split()
    if len(w) < 2 or len(w) > 4: return False
    if re.fullmatch(r"(?i)di|da|dal|dalla|de|del|della|d'", w[0]): return False   # «Di Leonardo Manzan», «Da Joseph Conrad»
    if any(norm(x) in MAI for x in w): return False
    # 20/11: dopo un nome di persona il cognome può essere una parola comune («Massimo Chiesa», «Andrea Piazza», «Imma Villa»)
    da_guardare = w if w[0] not in PROPRI else w[:1]
    if any(norm(x) in STOP for x in da_guardare if not re.fullmatch(PART, x)): return False
    if w[-1].isupper() or any(len(x) == 1 for x in w): return False
    if len({norm(x) for x in w}) < len(w): return False
    if norm(w[-1]) and norm(w[-1]) in norm(titolo): return False
    return True

def chi(e):
    if (e.get("chi") or "").strip(): return e["chi"].strip()
    d, tit = unicodedata.normalize("NFC", e.get("descrizione") or ""), e.get("artista") or ""   # 20/11: «Acuña» scritto con la tilde staccata
    if not d or d.isupper(): return ""
    nomi, pre, ruolo = [], None, {}
    for rx, p in RX:
        for m in rx.finditer(d):
            if FILM.search(d[max(0, m.start() - 30):m.start()]): continue
            for n in re.split(r"\s*(?:,|\be\b|\bed\b|&)\s*", m.group(1)):
                n = n.strip()
                if buono(n, tit) and n not in nomi:
                    nomi.append(n); ruolo[n] = p
                    if p == "@":
                        k = m.group(0).lower()
                        musica = e.get("genere") in ("Classica", "Jazz", "Concerti", "Musica") or re.search(r"(?i)orchestra|sinfoni|filarmonic|coro|ensemble|banda|concerto", d)
                        ruolo[n] = "dirige" if musica and re.search(r"dirig|diretto|diretta|direttore|concertatore", k) and "regia" not in k else "regia di"   # 20/11: a teatro e nella danza «diretta da» è la regia
    for m in VERBO.finditer(d):
        n = m.group(1).strip()
        if buono(n, tit) and n not in nomi: nomi.append(n); ruolo[n] = "con"
    m = SOLO_NOMI.match(d)
    if m:
        for n in re.split(r"\s*,\s*|\s+e\s+", m.group(1)):
            n = n.strip()
            if n and buono(n, tit) and n not in nomi: nomi.append(n); ruolo[n] = "con"
    m = INIZIO.match(d)
    if m and buono(m.group(1).strip(), tit) and m.group(1).strip() not in nomi:
        nomi.insert(0, m.group(1).strip()); ruolo[m.group(1).strip()] = "con"
    for m in PERSONA.finditer(d):
        n = m.group(1).strip()
        w = n.split()
        while len(w) > 2 and norm(w[-1]) in CODA: w = w[:-1]   # «Luca Perri Astrofisico», «Marlene Kuntz Dopo»
        while len(w) > 2 and w[0] not in PROPRI and w[1] in PROPRI and norm(w[0]) not in STOP and not re.fullmatch(r"(?i)di|da|dal|dalla|de|del|della|dei|degli|delle|d'|e|ed|a|al|alla|per|su|con", w[0]) and not re.search(r"[\w,]\s*$", d[:m.start()]): w = w[1:]   # «Se Federico Basso», «Conduce Luca Mastranto»
        n = " ".join(w)
        if w[0] not in PROPRI or n in nomi or not buono(n, tit): continue
        prima = d[max(0, m.start() - 40):m.start()]
        frase = re.split(r"[.;!?|·(]", d[:m.start()])[-1]
        if SOGGETTO.search(frase): continue   # «Omaggio a Whitney Houston e Tina Turner», «musiche di Fanny e Felix Mendelssohn»
        if DOPO_NO.search(d[m.end():m.end() + 30]): continue   # «Michael Jordan, un giocatore…», «Michelangelo Merisi, detto il Caravaggio»
        if PRIMA_NO.search(prima) or FILM.search(prima) or re.search(rf"[{U}][{L}'’]*\s+$", prima): continue   # «Teatro Gian Carlo Menotti»
        if any(n in x or x in n for x in nomi): continue
        nomi.append(n); ruolo[n] = "con"
    for m in STRUM.finditer(d):
        n = m.group(1).strip()
        if buono(n, tit) and n not in nomi: nomi.append(n); ruolo[n] = "con"
    nomi = [n for n in nomi if not any(n != x and n in x for x in nomi)][:3]
    if not nomi: return ""
    con = [n for n in nomi if ruolo[n] == "con"]; altri = [n for n in nomi if ruolo[n] != "con"]
    parti = []
    if con: parti.append(" e ".join(con[:2]) if len(con) <= 2 else ", ".join(con[:2]) + " e " + con[2])
    for n in altri[:1]: parti.append(f"{ruolo[n]} {n}")
    t = ", ".join(parti)
    return t if len(t) <= 80 else t[:80].rsplit(",", 1)[0]

def pulisci(t, titolo=""):
    """ricontrolla un «chi» già fatto (es. ricavato da una pagina): toglie i nomi non buoni"""
    out = []
    for parte in re.split(r",\s*", t or ""):
        m = re.match(r"^(regia di |dirige |con )?(.*)$", parte.strip()); pre, resto = m.group(1) or "", m.group(2)
        nomi = [n for n in (re.sub(r"\s+(?:Ingresso|Ingressi)\b.*$", "", n.strip()) for n in re.split(r"\s+(?:e|ed)\s+", resto)) if buono(n, titolo)]
        if nomi: out.append(pre + " e ".join(nomi))
    return ", ".join(out)


def _leggi(p):
    s = open(p, encoding="utf-8").read(); i, j = s.index("{"), s.rindex("}") + 1
    return s[:i], json.loads(s[i:j]), s[j:]

def mancati(e):
    """20/11/2026: coppie «Nome Cognome» rimaste fuori perché il nome non è in dati/nomi_propri.txt (da guardare il lunedì)"""
    if e.get("chi"): return []
    d = unicodedata.normalize("NFC", e.get("descrizione") or ""); out = []
    for m in PERSONA.finditer(d):
        n = m.group(1).strip(); w = n.split()
        if w[0] in PROPRI or not buono(n, e.get("artista") or ""): continue
        if PRIMA_NO.search(d[max(0, m.start() - 40):m.start()]) or re.search(rf"[{U}][{L}'’]*\s+$", d[max(0, m.start() - 40):m.start()]): continue
        out.append(n)
    return out

if __name__ == "__main__" and "--mancati" in sys.argv:
    # python3 scripts/protagonisti.py --mancati eventi.js milano/eventi.js …  → nomi possibili da aggiungere a dati/nomi_propri.txt
    for p in [x for x in sys.argv[1:] if not x.startswith("--")]:
        a, d, z = _leggi(p); k = "eventi" if "eventi" in d else "incontri"
        for e in d[k]:
            for n in mancati(e): print(f"{p}\t{e['id']}\t{n}\t{(e.get('descrizione') or '')[:80]}")
    sys.exit(0)

if __name__ == "__main__":
    p = sys.argv[1]; a, d, z = _leggi(p); k = "eventi" if "eventi" in d else "incontri"
    n = 0
    for e in d[k]:
        if not e.get("chi"):
            c = chi(e)
            if c:
                n += 1
                if "--scrivi" in sys.argv: e["chi"] = c
                elif "--mostra" in sys.argv: print(f"{e['artista'][:40]:40} | {c}")
    print(f"{p}: {n} su {len(d[k])} con protagonisti", file=sys.stderr)
    if "--scrivi" in sys.argv:
        open(p, "w", encoding="utf-8").write(a + json.dumps(d, ensure_ascii=False, separators=(",", ":")) + z)
