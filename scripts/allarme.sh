#!/bin/bash
# 23/11/2026 (Stefano: «cos'è tutta sta roba che arriva sulla mia posta… fai in modo di avere tutto sotto controllo»):
# gli allarmi dei flussi non aprono più segnalazioni su GitHub (ogni segnalazione = una email a Stefano). Si scrivono
# in allarmi.md sul ramo «allarmi» di questo repository; li legge la chat di coordinamento all'avvio
# (ristoranti-archivio, strumenti/avvio.py) e li porta a Stefano solo se serve una sua decisione.
# Uso: bash scripts/allarme.sh [--una-volta] "TITOLO" "TESTO"   (--una-volta: niente riga nuova se il titolo c'è già)
una=0; [ "${1:-}" = "--una-volta" ] && { una=1; shift; }
T="${1:?titolo}"; B="${2:-}"
URL="https://x-access-token:${GH_TOKEN:?GH_TOKEN}@github.com/${GITHUB_REPOSITORY}.git"
RUN="${GITHUB_SERVER_URL:-https://github.com}/${GITHUB_REPOSITORY}/actions/runs/${GITHUB_RUN_ID:-0}"
D=$(mktemp -d)
for i in 1 2 3 4 5; do
  rm -rf "$D" && mkdir -p "$D" && cd "$D" || exit 0
  git init -q && git remote add origin "$URL"
  if git fetch -q --depth 1 origin allarmi 2>/dev/null; then git checkout -q -B allarmi FETCH_HEAD; else git checkout -q --orphan allarmi; fi
  [ -f allarmi.md ] || printf '# Allarmi dei flussi di Events\n\nUna riga per allarme: data (UTC) · titolo · testo · giro. Li legge la chat di coordinamento.\n\n' > allarmi.md
  if [ $una = 1 ] && grep -qF " · $T · " allarmi.md; then echo "allarme già scritto: $T"; exit 0; fi
  printf -- '- %s · %s · %s · %s\n' "$(date -u +'%Y-%m-%d %H:%M')" "$T" "$B" "$RUN" >> allarmi.md
  git add allarmi.md
  git -c user.name="eventi-bot" -c user.email="actions@users.noreply.github.com" commit -q -m "Allarme: $T"
  git push -q origin HEAD:allarmi && { echo "allarme scritto: $T"; exit 0; }
  sleep 6
done
echo "allarme non scritto: $T"; exit 0
