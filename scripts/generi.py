"""Verifica i generi musicali degli artisti su MusicBrainz (gira su GitHub Actions).
Legge dati/generi_da_verificare.json (lista di nomi) e scrive dati/generi_artisti.json
{nome: {"genere": "Rock|Jazz|Classica|Pop e altra musica", "tag": [...], "mbid": ...}}.
Rispetta le regole di MusicBrainz: un User-Agent riconoscibile e una richiesta al secondo."""
import json, time, urllib.request, urllib.parse, os
UA = "AchEventsGuide/1.0 ( https://achevents.com )"
ROCK = ("rock", "metal", "punk", "indie", "alternative", "hardcore", "grunge", "shoegaze", "post-punk", "garage", "emo", "prog", "stoner", "doom", "noise", "new wave", "blues", "folk", "country", "psychedelic")
JAZZ = ("jazz", "soul", "funk", "bossa", "swing", "fusion", "gospel")
CLAS = ("classical", "opera", "baroque", "orchestral", "contemporary classical", "minimalism", "chamber", "neoclassical")
def get(u):
    r = urllib.request.Request(u, headers={"User-Agent": UA, "Accept": "application/json"})
    return json.load(urllib.request.urlopen(r, timeout=20))
nomi = json.load(open("dati/generi_da_verificare.json"))
out = json.load(open("dati/generi_artisti.json")) if os.path.exists("dati/generi_artisti.json") else {}
for n in nomi:
    if n in out: continue
    try:
        d = get("https://musicbrainz.org/ws/2/artist/?fmt=json&limit=1&query=" + urllib.parse.quote('artist:"%s"' % n))
        a = (d.get("artists") or [None])[0]
        if not a or a.get("score", 0) < 90:
            out[n] = {"genere": "", "tag": []}
        else:
            time.sleep(1.1)
            x = get("https://musicbrainz.org/ws/2/artist/%s?fmt=json&inc=tags+genres" % a["id"])
            tags = [t["name"] for t in sorted((x.get("genres") or []) + (x.get("tags") or []), key=lambda t: -t.get("count", 0))][:8]
            s = " ".join(tags)
            g = "Classica" if any(k in s for k in CLAS) else "Jazz" if any(k in s for k in JAZZ) else "Rock" if any(k in s for k in ROCK) else ("Pop e altra musica" if tags else "")
            out[n] = {"genere": g, "tag": tags, "mbid": a["id"]}
    except Exception as e:
        out[n] = {"genere": "", "tag": [], "errore": str(e)[:80]}
    time.sleep(1.1)
json.dump(out, open("dati/generi_artisti.json", "w"), ensure_ascii=False, indent=1)
print(len(out), "artisti;", sum(1 for v in out.values() if v["genere"]), "con genere")
