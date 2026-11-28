"""Elenco unico delle città della guida (dal 15/11/2026, con Ravenna e Ferrara).

Bologna e Milano restano configurate anche nei singoli script come prima; Ravenna e Ferrara
prendono tutto da qui. Perimetro: il comune capoluogo e tutta la sua provincia.
"""

CITTA = {
    "ra": {
        "cartella": "ravenna", "nome": "Ravenna", "minimo": 5,
        "dice": "ravenna", "arte": "ravenna", "tm": "Ravenna", "movieplayer": "ravenna", "mymovies": "ravenna",
        "zone": {
            "Ravenna": ["Ravenna"],
            "Costa e Russi": ["Cervia", "Russi"],
            "Bassa Romagna": ["Lugo", "Alfonsine", "Bagnacavallo", "Bagnara di Romagna", "Conselice", "Cotignola", "Fusignano",
                              "Massa Lombarda", "Sant'Agata sul Santerno"],
            "Faentino": ["Faenza", "Brisighella", "Casola Valsenio", "Castel Bolognese", "Riolo Terme", "Solarolo"],
        },
        "alias": {"milano marittima": "Cervia", "pinarella": "Cervia", "tagliata": "Cervia", "marina di ravenna": "Ravenna",
                  "lido adriano": "Ravenna", "punta marina": "Ravenna", "marina romea": "Ravenna", "madonna dell'albero": "Ravenna",
                  "sant'alberto": "Ravenna", "lido di classe": "Ravenna", "lido di savio": "Ravenna", "classe": "Ravenna",
                  "porto corsini": "Ravenna", "casalborsetti": "Ravenna", "san zaccaria": "Ravenna", "granarolo faentino": "Faenza"},
    },
    "fe": {
        "cartella": "ferrara", "nome": "Ferrara", "minimo": 5,
        "dice": "ferrara", "arte": "ferrara", "tm": "Ferrara", "movieplayer": "ferrara", "mymovies": "ferrara",
        "zone": {
            "Ferrara": ["Ferrara"],
            "Alto Ferrarese": ["Cento", "Bondeno", "Terre del Reno", "Poggio Renatico", "Vigarano Mainarda"],
            "Copparese e Po": ["Copparo", "Riva del Po", "Tresignana", "Jolanda di Savoia"],
            "Delta e costa": ["Comacchio", "Codigoro", "Goro", "Mesola", "Lagosanto", "Fiscaglia", "Ostellato"],
            "Argentano": ["Argenta", "Portomaggiore", "Masi Torello", "Voghiera"],
        },
        "alias": {"lido degli estensi": "Comacchio", "lido di spina": "Comacchio", "porto garibaldi": "Comacchio",
                  "lido delle nazioni": "Comacchio", "lido di pomposa": "Comacchio", "lido degli scacchi": "Comacchio",
                  "lido di volano": "Codigoro", "pomposa": "Codigoro", "ro": "Riva del Po", "berra": "Riva del Po",
                  "mirabello": "Terre del Reno", "sant'agostino": "Terre del Reno", "migliarino": "Fiscaglia",
                  "massa fiscaglia": "Fiscaglia", "migliaro": "Fiscaglia", "formignana": "Tresignana", "tresigallo": "Tresignana",
                  "ferrara (fe)": "Ferrara"},
    },
    # 28/11/2026 (Stefano: «Preparati per inserire Modena Forlì e Firenze»): preparate, si accendono in CITTA_ATTIVE (index.html)
    "mo": {
        "cartella": "modena", "nome": "Modena", "minimo": 5,
        "dice": "modena", "arte": "modena", "tm": "Modena", "movieplayer": "modena", "mymovies": "modena",
        "zone": {
            "Modena": ["Modena"],
            "Carpi e Bassa": ["Carpi", "Campogalliano", "Novi di Modena", "Soliera", "Mirandola", "Camposanto", "Cavezzo",
                              "Concordia sulla Secchia", "Finale Emilia", "Medolla", "San Felice sul Panaro", "San Possidonio",
                              "San Prospero"],
            "Castelfranco e Sorbara": ["Castelfranco Emilia", "Bastiglia", "Bomporto", "Nonantola", "Ravarino", "San Cesario sul Panaro"],
            "Sassuolo e Ceramiche": ["Sassuolo", "Fiorano Modenese", "Formigine", "Maranello", "Frassinoro", "Montefiorino", "Palagano",
                                     "Prignano sulla Secchia"],
            "Vignola e Castelli": ["Vignola", "Castelnuovo Rangone", "Castelvetro di Modena", "Guiglia", "Marano sul Panaro",
                                   "Savignano sul Panaro", "Spilamberto", "Zocca", "Montese"],
            "Frignano": ["Pavullo nel Frignano", "Fanano", "Fiumalbo", "Lama Mocogno", "Montecreto", "Pievepelago", "Polinago",
                         "Riolunato", "Serramazzoni", "Sestola"],
        },
        "alias": {"modena (mo)": "Modena", "massa finalese": "Finale Emilia", "marzaglia": "Modena", "baggiovara": "Modena",
                  "sorbara": "Bomporto", "piumazzo": "Castelfranco Emilia", "manzolino": "Castelfranco Emilia",
                  "magreta": "Formigine", "casinalbo": "Formigine", "ubersetto": "Fiorano Modenese", "spezzano": "Fiorano Modenese",
                  "levizzano": "Castelvetro di Modena", "montale": "Castelnuovo Rangone", "fossoli": "Carpi", "limidi": "Soliera",
                  "pavullo": "Pavullo nel Frignano", "castelfranco": "Castelfranco Emilia"},
    },
    "fc": {
        "cartella": "forli-cesena", "nome": "Forlì-Cesena", "capo": "Forlì", "minimo": 5,
        "dice": "forli", "arte": "forli-cesena", "tm": "Forlì", "movieplayer": "forli", "mymovies": "forlicesena",
        "zone": {
            "Forlì": ["Forlì"],
            "Cesena": ["Cesena"],
            "Forlivese e Appennino": ["Forlimpopoli", "Bertinoro", "Castrocaro Terme e Terra del Sole", "Civitella di Romagna", "Dovadola",
                                      "Galeata", "Meldola", "Modigliana", "Portico e San Benedetto", "Predappio", "Premilcuore",
                                      "Rocca San Casciano", "Santa Sofia", "Tredozio"],
            "Valle del Savio": ["Bagno di Romagna", "Mercato Saraceno", "Montiano", "Sarsina", "Verghereto"],
            "Rubicone e costa": ["Cesenatico", "Gambettola", "Gatteo", "Longiano", "Roncofreddo", "San Mauro Pascoli",
                                 "Savignano sul Rubicone", "Sogliano al Rubicone", "Borghi"],
        },
        "alias": {"forli": "Forlì", "forlì (fc)": "Forlì", "forli (fc)": "Forlì", "cesena (fc)": "Cesena",
                  "castrocaro terme": "Castrocaro Terme e Terra del Sole", "castrocaro": "Castrocaro Terme e Terra del Sole",
                  "terra del sole": "Castrocaro Terme e Terra del Sole", "san piero in bagno": "Bagno di Romagna",
                  "gatteo a mare": "Gatteo", "valverde": "Cesenatico", "villamarina": "Cesenatico", "zadina": "Cesenatico",
                  "san mauro mare": "San Mauro Pascoli", "savignano": "Savignano sul Rubicone", "sogliano": "Sogliano al Rubicone",
                  "fratta terme": "Bertinoro", "santa maria nuova": "Bertinoro"},
    },
    "fi": {
        "cartella": "firenze", "nome": "Firenze", "minimo": 5,
        "dice": "florence", "arte": "firenze", "tm": "Firenze", "movieplayer": "firenze", "mymovies": "firenze",
        "zone": {
            "Firenze": ["Firenze"],
            "Piana e Colline": ["Sesto Fiorentino", "Calenzano", "Campi Bisenzio", "Signa", "Lastra a Signa", "Scandicci", "Fiesole",
                                "Vaglia"],
            "Chianti": ["Bagno a Ripoli", "Impruneta", "Greve in Chianti", "San Casciano in Val di Pesa", "Barberino Tavarnelle"],
            "Valdarno e Valdisieve": ["Figline e Incisa Valdarno", "Reggello", "Rignano sull'Arno", "Pontassieve", "Pelago", "Rufina",
                                      "Londa", "San Godenzo"],
            "Mugello": ["Borgo San Lorenzo", "Barberino di Mugello", "Scarperia e San Piero", "Vicchio", "Dicomano", "Firenzuola",
                        "Marradi", "Palazzuolo sul Senio"],
            "Empolese Valdelsa": ["Empoli", "Capraia e Limite", "Castelfiorentino", "Cerreto Guidi", "Certaldo", "Fucecchio",
                                  "Gambassi Terme", "Montaione", "Montelupo Fiorentino", "Montespertoli", "Vinci"],
        },
        "alias": {"florence": "Firenze", "firenze (fi)": "Firenze", "figline valdarno": "Figline e Incisa Valdarno",
                  "incisa in val d'arno": "Figline e Incisa Valdarno", "scarperia": "Scarperia e San Piero",
                  "san piero a sieve": "Scarperia e San Piero", "tavarnelle val di pesa": "Barberino Tavarnelle",
                  "barberino val d'elsa": "Barberino Tavarnelle", "settignano": "Firenze", "galluzzo": "Firenze",
                  "san casciano": "San Casciano in Val di Pesa", "limite sull'arno": "Capraia e Limite",
                  "capraia fiorentina": "Capraia e Limite", "montelupo": "Montelupo Fiorentino", "greve": "Greve in Chianti"},
    },
}


def comuni(k):
    return [c for cs in CITTA[k]["zone"].values() for c in cs]


# 28/11/2026: tutte le città in un posto solo, così una città nuova si aggiunge qui e gli script la trovano da soli.
# sigla -> (nome, cartella; "" per Bologna). Le città preparate ma spente stanno qui; quelle visibili sono CITTA_ATTIVE in index.html.
TUTTE = {"bo": ("Bologna", ""), "mi": ("Milano", "milano"),
         **{k: (v["nome"], v["cartella"]) for k, v in CITTA.items()}}


def attive(index="index.html"):
    """Le città accese (CITTA_ATTIVE in index.html); se il file non si legge, Bologna e Milano."""
    import os
    import re
    try:
        t = open(index if os.path.isabs(index) else os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", index),
                 encoding="utf-8").read()
        m = re.search(r"const CITTA_ATTIVE=\[([^\]]*)\]", t)
        return re.findall(r'"([a-z]{2})"', m.group(1)) if m else ["bo", "mi"]
    except OSError:
        return ["bo", "mi"]


def file_di(k, nome):
    """Percorso di un file di dati della città k (es. file_di("fe", "eventi.js") -> "ferrara/eventi.js")."""
    c = TUTTE[k][1]
    return f"{c}/{nome}" if c else nome
