#!/usr/bin/env bash
# Salva i dati di un flusso su main senza litigare con gli altri flussi che girano nello stesso momento.
# uso: bash scripts/salva.sh "Messaggio del commit" file1 file2 ...
# - versioni.js (impronte di tutti i file dati) lo riscrive dopo aver preso le modifiche degli altri,
#   così un conflitto su versioni.js non blocca più il salvataggio (successo l'11/11/2026 col cinema);
# - esce con errore se dopo 5 tentativi il push non è riuscito (regola 8 bis.3: un flusso verde deve aver salvato).
set -u
MSG="$1"; shift
git config user.name "github-actions[bot]"
git config user.email "github-actions[bot]@users.noreply.github.com"
python3 scripts/versioni.py
# file delle impronte di tutte le città: solo quelli che esistono (git add si ferma su un file mancante)
fissi() { for f in versioni.js index.html eventi-presto.js eventi-resto.js milano/versioni.js milano/index.html milano/eventi-presto.js milano/eventi-resto.js ravenna/versioni.js ravenna/index.html ravenna/eventi-presto.js ravenna/eventi-resto.js ferrara/versioni.js ferrara/index.html ferrara/eventi-presto.js ferrara/eventi-resto.js; do [ -e "$f" ] && echo "$f"; done; }
git add "$@" $(fissi) 2>/dev/null || git add $(fissi)
if git diff --cached --quiet; then echo "nessuna modifica"; exit 0; fi
git commit -q -m "$MSG"
for i in 1 2 3 4 5; do
  git fetch -q --depth=50 origin main
  if ! git rebase -q -X theirs origin/main; then git rebase --abort; sleep 10; continue; fi
  python3 scripts/versioni.py
  git add $(fissi)
  git diff --cached --quiet || git commit -q --amend --no-edit
  if git push -q origin HEAD:main; then echo "salvato al tentativo $i"; exit 0; fi
  sleep $((5 * i))
done
echo "push non riuscito dopo 5 tentativi"; exit 1
