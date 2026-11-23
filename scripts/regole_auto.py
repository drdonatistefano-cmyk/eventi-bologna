"""Regole pure (senza rete) usate da eventi_auto.py e locali_sito.py, provate in prova_verifica.py.

23/11/2026, Stefano: «sistema tutto e fai in modo che non accada più». Tre errori del giro automatico:
  1. arte.it: da novembre non era mai entrata una mostra (53 lette, 0 aggiunte). Il riquadro «occhiello»
     ha dentro un altro <span class="citta">: la vecchia lettura si fermava al primo </span> e trovava solo
     «Milano», senza la sede. Ora si legge tutto fino al titolo (arte_blocchi).
  2. Siti con più sale (TCBO: Comunale, Auditorium Manzoni, Foyer Rossini, Persiceto; ERT: Arena del Sole,
     Moline): tutto finiva nella sala di base e diventava un doppione della scheda giusta. Ora la sala si
     riconosce dal testo della pagina (sala_da_testo) e, se non basta, un evento con lo stesso titolo,
     date che si toccano e la fonte sullo stesso sito è considerato già in guida (stesso_organizzatore).
"""
import html, re, urllib.parse

MESI = {m: i for i, m in enumerate("gennaio febbraio marzo aprile maggio giugno luglio agosto settembre ottobre novembre dicembre".split(), 1)}


def _pulito(s):
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", s or "")).replace("\xa0", " ").split())


def data_it(s):
    m = re.match(r"(\d{1,2})\s+([A-Za-zÀ-ÿ]+)\s+(\d{4})", (s or "").strip())
    return f"{int(m.group(3)):04d}-{MESI[m.group(2).lower()]:02d}-{int(m.group(1)):02d}" if m and m.group(2).lower() in MESI else ""


def arte_blocchi(pagina):
    """Mostre di una pagina del calendario di arte.it: [{href, titolo, citta, sede, inizio, fine, sommario}]
    più un dizionario dei motivi per cui un riquadro non si è potuto leggere (per il riepilogo)."""
    out, motivi = [], {}
    for href, b in re.findall(r'<a href="(/calendario-arte/[^"]+)" class="link_mostre_list">(.*?)</a>', pagina or "", re.S):
        def campo(c, fino=None):
            if fino:   # riquadri con altri <span> dentro: si legge fino all'inizio del riquadro seguente
                x = re.search(r'<span class="%s">(.*?)<span class="%s"' % (c, fino), b, re.S)
            else:
                x = re.search(r'<span class="%s">(.*?)</span>' % c, b, re.S)
            return _pulito(x.group(1)) if x else ""
        tit = _pulito((re.search(r"<h[1-4][^>]*>(.*?)</h[1-4]>", b, re.S) or [None, ""])[1])
        dd = re.match(r"Dal (.+?) al (.+)$", campo("data"))
        occ = campo("occhiello", fino="title") or campo("occhiello")
        parti = [p.strip() for p in occ.split("|")]
        if not tit: motivi["senza titolo"] = motivi.get("senza titolo", 0) + 1; continue
        if not dd: motivi["senza date"] = motivi.get("senza date", 0) + 1; continue
        if len(parti) < 2 or not parti[1]: motivi["senza sede"] = motivi.get("senza sede", 0) + 1; continue
        ini, fin = data_it(dd.group(1)), data_it(dd.group(2))
        if not (ini and fin): motivi["date illeggibili"] = motivi.get("date illeggibili", 0) + 1; continue
        out.append({"href": href, "titolo": tit, "citta": parti[0], "sede": parti[1], "inizio": ini, "fine": fin,
                    "sommario": campo("sommario")})
    return out, motivi


def dominio(u):
    d = urllib.parse.urlparse(u or "").netloc.lower()
    d = re.sub(r"^www\.", "", d)
    # biglietterie dei teatri sullo stesso sito (tcbo.vivaticket.it ↔ tcbo.it)
    return d


GENERALI = r"ticketone|vivaticket|dice\.fm|songkick|feverup|ticketmaster|eventbrite|arte\.it|teatro\.it|bolognatoday|bolognawelcome|connessiallopera|operapertutti|liveticket|google|facebook|instagram"


def base(u):
    """Dominio registrato: stagione2027.tcbo.it → tcbo.it"""
    return ".".join(dominio(u).split(".")[-2:])


def stesso_organizzatore(f1, f2):
    """Le due fonti sono pagine dello stesso sito di teatro? (biglietterie generali e giornali non contano)"""
    a, b = base(f1), base(f2)
    if not a or not b or a != b: return False
    return not re.search(GENERALI, a)


def stesso_biglietto(b1, b2):
    """Stessa pagina d'acquisto di un singolo evento (non la pagina di un luogo o di una biglietteria)."""
    def n(u):
        u = re.sub(r"[?#].*$", "", (u or "").strip().lower()).rstrip("/")
        return re.sub(r"^https?://(www\.)?", "", u)
    x, y = n(b1), n(b2)
    if not x or x != y: return False
    percorso = x.split("/", 1)[1] if "/" in x else ""
    return percorso.count("/") >= 1 and not re.search(r"/(venue|city|cityd|luogo|location)/|^(biglietti|tickets?|shop)$", percorso)


def sala_da_testo(testo, sedi, base):
    """Sala di un sito con più sale: tra le espressioni di `sedi` ({espressione: luogo} o {espressione: [luogo, comune]})
    vince quella che compare prima nel testo della pagina dell'evento (dopo il titolo). Restituisce (luogo, comune o None); senza riscontro (base, None)."""
    meglio, pos = None, None
    for rx, v in (sedi or {}).items():
        m = re.search(rx, testo or "", re.I)
        if m and (pos is None or m.start() < pos): meglio, pos = v, m.start()
    if meglio is None: return (base, None)
    return tuple(meglio) if isinstance(meglio, list) else (meglio, None)


def permanente(inizio, fine, oggi):
    """Allestimenti di anni (2013→2030, 2023→2028): non sono mostre temporanee per la guida."""
    import datetime as _d
    try:
        i, f, o = (_d.date.fromisoformat(x) for x in (inizio, fine, oggi))
    except ValueError:
        return False
    return (f - i).days > 540 or (o - i).days > 365
