# Cartelloni di Milano letti da GitHub — 2026-11-22 22:57 UTC

Il giro del lunedì legge questi file e non apre pagine web.

- Candidati da giudicare (non ancora in guida): **119** in `candidati.json`
- TicketOne: {'gruppi': 513, 'abbinamento': "eventi con TicketOne: 507 su 1114\neventi con TicketOne dopo i controlli: 507\nnuovi da TicketOne: 44 Counter({'Pop e altra musica/': 23, 'Teatro/Prosa': 12, 'Teatro/Musical': 6, 'Jazz/': 1, 'Teatro/Incontro': 1, 'Classica/': 1})", 'link_nuovi': 10, 'spettacoli_mancanti': 44, 'link_scritti': True}
- Songkick: {'pagine': 12, 'concerti': 577, 'mancanti': 81}

## Controllo TicketOne (date in vendita nei prossimi 3 mesi)

- Date in vendita: 321, già in guida con il link: 212
- Date in più di spettacoli già in guida, messe fra i candidati pronti: **6**
- Forse in guida ma senza link TicketOne, da controllare: **2**
- In vendita e non in guida (spesso pacchetti, prove TV, laboratori): 4
- Mostre in vendita su TicketOne: senza link in guida 3, non in guida 6

Il dettaglio è in `candidati.json`, voce `controllo_ticketone.da_controllare`.

## Schede povere (prossime 3 settimane)

- Eventi con la scheda povera: 40, pagina dell'evento letta: **21** (testo in `povere/<id>.txt`, elenco in `povere.json`)
- Da completare con parole tue: protagonisti in `chi`, ora, durata e prezzi se scritti, una descrizione di 1-2 frasi. Mai copiare il testo.

## Pagine dei cartelloni

| Pagina | Esito | Cambiata | Eventi strutturati | Testo |
|---|---|---|---|---|
| Songkick – concerti Milano | ok | **sì** |  | `pagine/songkick-concerti-milano.txt` |
| Teatro alla Scala – stagione | ok | **sì** | 0 | `pagine/teatro-alla-scala-stagione.txt` |
| Piccolo Teatro | ok | **sì** | 0 | `pagine/piccolo-teatro.txt` |
| Teatro Manzoni | ok | **sì** | 0 | `pagine/teatro-manzoni.txt` |
| Teatro Arcimboldi | non letta: Error: Page.goto: net::ERR_EMPTY_RESPONSE at https://www.teatroarcimboldi.it/ | no |  | `pagine/teatro-arcimboldi.txt` |
| Teatro dal Verme – I Pomeriggi Musicali | ok | **sì** | 0 | `pagine/teatro-dal-verme-i-pomeriggi-musicali.txt` |
| Teatro Franco Parenti | ok | **sì** | 0 | `pagine/teatro-franco-parenti.txt` |
| Teatro Elfo Puccini | ok | **sì** | 0 | `pagine/teatro-elfo-puccini.txt` |
| Blue Note Milano | ok | **sì** | 0 | `pagine/blue-note-milano.txt` |
| arte.it – mostre a Milano | ok | **sì** | 0 | `pagine/arte-it-mostre-a-milano.txt` |
