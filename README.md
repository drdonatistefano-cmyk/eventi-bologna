# Eventi a Bologna

Concerti, teatro, comici, classica, grandi eventi e mostre a Bologna e nei 55 comuni della Città metropolitana, nei prossimi 12 mesi.

Sito pubblico: https://drdonatistefano-cmyk.github.io/eventi-bologna/
(la stessa pagina è anche su claude.ai: https://claude.ai/artifact/VkNm64jekYZkPj73i3mQAa)

- `index.html` — la pagina (schede Spettacoli e Mostre). Gli eventi passati vengono nascosti dalla pagina stessa.
- `eventi.js` — dati degli spettacoli (`window.EVENTI_DATA`)
- `mostre.js` — dati delle mostre (`window.MOSTRE_DATA`)
- `scripts/aggiorna.py` — controlla i dati e crea eventi.js / mostre.js (`python3 scripts/aggiorna.py eventi.json`, `python3 scripts/aggiorna.py mostre.json --mostre`)
- `scripts/censimento_fonti.py`, `dati/censimento.*` — verifica delle fonti leggibili in automatico

Aggiornamento: ogni lunedì un'attività programmata di Claude aggiorna eventi.js e mostre.js qui e sulla pagina claude.ai.

Statistiche: GoatCounter (senza cookie), attivo solo sul sito GitHub quando in `index.html` la costante `GC` contiene il nome dell'account.
