"""Costruisce la pagina pubblica "Eventi a Bologna" (GitHub Pages).

Uso (dalla radice dell'archivio):  python3 scripts/build.py [AAAA-MM-GG]
Legge scripts/template.html e dati/eventi.json, toglie gli eventi passati,
pulisce i link di tracciamento e scrive index.html nella radice.
"""
import json, re, sys, datetime, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
SITE_URL = "https://drdonatistefano-cmyk.github.io/eventi-bologna/"
GOATCOUNTER = ""  # nome scelto su goatcounter.com, es. "eventibologna"
oggi = sys.argv[1] if len(sys.argv) > 1 else datetime.date.today().isoformat()

t = (ROOT / "scripts/template.html").read_text(encoding="utf-8")
ev = json.loads((ROOT / "dati/eventi.json").read_text(encoding="utf-8"))
ev = [e for e in ev if (e.get("fino") or e["data"]) >= oggi]
for e in ev:
    for k in ("fonte", "biglietti", "sito_luogo"):
        if e.get(k):
            e[k] = re.sub(r"\?utm_[^\"]*$", "", e[k])
ev.sort(key=lambda e: (e["data"], e.get("ora") or ""))
html = (t.replace("__DATA__", json.dumps(ev, ensure_ascii=False).replace("</", "<\\/"))
         .replace("__UPDATED__", oggi).replace("__SITE_URL__", SITE_URL).replace("__GC__", GOATCOUNTER))
(ROOT / "index.html").write_text(html, encoding="utf-8")
(ROOT / "dati/eventi.json").write_text(json.dumps(ev, ensure_ascii=False, indent=0), encoding="utf-8")
print(f"{len(ev)} eventi, aggiornato al {oggi}")
