"""Protagonisti di uno spettacolo o di un incontro (campo «chi», regola del 17/11/2026, Stefano).

chi(e) -> stringa breve, es. «Fabio Nobile Quartet con Fabrizio Bosso», «regia di Massimo Popolizio», «dirige Riccardo Muti»,
oppure "" se nella descrizione non ci sono nomi di persone sicuri. Non tocca un «chi» già scritto a mano.
Uso a mano: python3 scripts/protagonisti.py <eventi.js|incontri.js> [--scrivi]
"""
import re, sys, json, unicodedata

def norm(s):
    s = unicodedata.normalize("NFD", str(s or "").lower())
    return re.sub(r"[^a-z0-9]+", " ", "".join(c for c in s if not unicodedata.combining(c))).strip()

U, L = "A-ZÀ-ÖØ-ÞŁŠŽČĆ", "a-zà-öø-ÿłšžčćńęą"
W = rf"[{U}][{L}'’]+(?:-[{U}][{L}'’]+)?"
PART = r"(?:de|De|Di|Da|Del|Dalla|Della|La|Lo|van|Van|von|Von|Mc|dos|da)"
NOME = rf"{W}(?:\s+{PART})?\s+{W}(?:\s+{W}(?!\s+[{U}]))?"
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
into the tour apicoltura acetaia azienda agricola cantina""".split())
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

def buono(n, titolo):
    w = n.split()
    if len(w) < 2 or len(w) > 4: return False
    if re.fullmatch(r"(?i)di|da|dal|dalla|de|del|della|d'", w[0]): return False   # «Di Leonardo Manzan», «Da Joseph Conrad»
    if any(norm(x) in STOP for x in w if not re.fullmatch(PART, x)): return False
    if w[-1].isupper() or any(len(x) == 1 for x in w): return False
    if len({norm(x) for x in w}) < len(w): return False
    if norm(w[-1]) and norm(w[-1]) in norm(titolo): return False
    return True

def chi(e):
    if (e.get("chi") or "").strip(): return e["chi"].strip()
    d, tit = e.get("descrizione") or "", e.get("artista") or ""
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
                        ruolo[n] = "dirige" if re.search(r"dirig|diretto|diretta|direttore|concertatore", k) and "regia" not in k else "regia di"
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
        nomi = [n.strip() for n in re.split(r"\s+(?:e|ed)\s+", resto) if buono(n.strip(), titolo)]
        if nomi: out.append(pre + " e ".join(nomi))
    return ", ".join(out)


def _leggi(p):
    s = open(p, encoding="utf-8").read(); i, j = s.index("{"), s.rindex("}") + 1
    return s[:i], json.loads(s[i:j]), s[j:]

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
