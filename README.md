# Eventi a Bologna

Concerti, teatro, comici, classica, grandi eventi e mostre a Bologna e nei 55 comuni della Città metropolitana, nei prossimi 12 mesi.

Sito pubblico: https://achevents.com/
(la stessa pagina è anche su claude.ai: https://claude.ai/artifact/VkNm64jekYZkPj73i3mQAa)

- `index.html` — la pagina (schede Spettacoli e Mostre). Gli eventi passati vengono nascosti dalla pagina stessa.
- `eventi.js` — dati degli spettacoli (`window.EVENTI_DATA`)
- `mostre.js` — dati delle mostre (`window.MOSTRE_DATA`)
- `scripts/aggiorna.py` — controlla i dati e crea eventi.js / mostre.js (`python3 scripts/aggiorna.py eventi.json`, `python3 scripts/aggiorna.py mostre.json --mostre`)
- `scripts/censimento_fonti.py`, `dati/censimento.*` — verifica delle fonti leggibili in automatico

Aggiornamento: ogni lunedì un'attività programmata di Claude aggiorna eventi.js e mostre.js qui e sulla pagina claude.ai.

Statistiche: GoatCounter (senza cookie), attivo solo sul sito GitHub quando in `index.html` la costante `GC` contiene il nome dell'account (eventibologna). Cruscotto: https://eventibologna.goatcounter.com

Statistiche esportate: il flusso `.github/workflows/statistiche.yml` ogni mattina legge l'API di GoatCounter (`scripts/statistiche.py`) e salva `dati/statistiche.json` e `dati/statistiche.md` (visite per giorno e per settimana dal lancio, clic sui biglietti, filtri, ricerche, condivisioni, provenienze). Serve il segreto `GOATCOUNTER_TOKEN` nelle impostazioni del repository; senza, il flusso non fa nulla.

Pagina delle statistiche: https://achevents.com/statistiche.html
Si aggiorna ogni ora con il workflow "Cruscotto statistiche" (scripts/cruscotto.py), che salva stats.json nel ramo `statistiche` senza ripubblicare il sito. Il riepilogo giornaliero in dati/statistiche.* resta del workflow "Statistiche".

Velocità (8/11/2026): la pagina carica prima `versioni.js` (piccolissimo, sempre fresco) con le impronte dei file dei dati, poi `eventi.js`, `serate.js`, `mostre.js`, `cinema.js` con `?h=<impronta>`: finché un file non cambia il telefono usa la copia che ha già (seconda visita da circa 3 s a 0,7 s su 4G lento). `scripts/versioni.py` ricalcola le impronte; lo lanciano i flussi cinema e serate prima di salvare e il flusso «Versioni dei dati» a ogni push dei dati (più un controllo ogni ora). Dopo aver cambiato a mano i dati si può lanciare `python3 scripts/versioni.py` e includere `versioni.js` nel commit. Senza versioni.js la pagina torna al metodo di prima.
