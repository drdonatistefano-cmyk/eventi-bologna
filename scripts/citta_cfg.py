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
}


def comuni(k):
    return [c for cs in CITTA[k]["zone"].values() for c in cs]
