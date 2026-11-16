#!/usr/bin/env python3
"""Casella redazione@achevents.com (Infomaniak) via IMAP, da GitHub Actions.

  python3 scripts/posta.py leggi [giorni]   -> scrive posta.json (messaggi recenti, testo e allegati piccoli)
  python3 scripts/posta.py bozze FILE.json  -> mette le lettere come BOZZE nella cartella Bozze della casella
  python3 scripts/posta.py manda FILE.json  -> invia le bozze indicate (solo quando Stefano dice «manda»)

La password sta solo nel segreto GitHub REDAZIONE_PASSWORD. Il contenuto della posta non finisce mai
in chiaro nel repository (pubblico) né nei log: il flusso lo cifra con dati/chiave_posta.pub.
"""
import base64, datetime, email, email.policy, imaplib, json, os, re, smtplib, sys, time
from email.message import EmailMessage
from email.utils import make_msgid, formatdate, parseaddr

HOST = "mail.infomaniak.com"
UTENTE = os.environ.get("REDAZIONE_UTENTE", "redazione@achevents.com")
PWD = os.environ.get("REDAZIONE_PASSWORD", "")
FIRMA_NOME = "Stefano Donati – Ach's Events Guide"


def connetti():
    if not PWD: sys.exit("Manca il segreto REDAZIONE_PASSWORD")
    m = imaplib.IMAP4_SSL(HOST, 993)
    m.login(UTENTE, PWD)
    return m


def cartelle(m):
    typ, d = m.list()
    out = []
    for r in d or []:
        s = r.decode(errors="replace")
        nome = s.rsplit(' "', 1)[-1].strip('"') if ' "' in s else s.split()[-1]
        out.append((s, nome))
    return out


def cartella_bozze(m):
    for s, nome in cartelle(m):
        if "\\Drafts" in s: return nome
    for s, nome in cartelle(m):
        if re.search(r"draft|bozz", nome, re.I): return nome
    return "Drafts"


def testo(msg):
    parti, allegati = [], []
    for p in msg.walk():
        if p.is_multipart(): continue
        fn = p.get_filename()
        ct = p.get_content_type()
        if fn or p.get_content_disposition() == "attachment":
            dati = p.get_payload(decode=True) or b""
            a = {"nome": fn or "allegato", "tipo": ct, "byte": len(dati)}
            if len(dati) <= 6_000_000: a["base64"] = base64.b64encode(dati).decode()
            allegati.append(a)
        elif ct == "text/plain":
            parti.append(p.get_content())
        elif ct == "text/html" and not parti:
            h = p.get_content()
            h = re.sub(r"(?is)<(script|style).*?</\1>", " ", h)
            h = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</tr>|</li>", "\n", h)
            parti.append(re.sub(r"[ \t]+", " ", re.sub(r"<[^>]+>", " ", h)))
    return "\n".join(parti).strip(), allegati


def leggi(giorni=14):
    m = connetti()
    m.select("INBOX", readonly=True)          # sola lettura: i messaggi restano «non letti»
    dal = (datetime.date.today() - datetime.timedelta(days=giorni)).strftime("%d-%b-%Y")
    typ, ids = m.search(None, f'(SINCE "{dal}")')
    out = []
    for i in (ids[0].split() if ids and ids[0] else [])[-40:]:
        typ, d = m.fetch(i, "(RFC822)")
        msg = email.message_from_bytes(d[0][1], policy=email.policy.default)
        corpo, allegati = testo(msg)
        out.append({"uid": i.decode(), "message_id": msg.get("Message-ID", ""), "da": msg.get("From", ""),
                    "a": msg.get("To", ""), "cc": msg.get("Cc", ""), "oggetto": msg.get("Subject", ""),
                    "data": msg.get("Date", ""), "testo": corpo[:60000], "allegati": allegati,
                    "references": msg.get("References", ""), "in_reply_to": msg.get("In-Reply-To", "")})
    info = {"letto": datetime.datetime.now(datetime.timezone.utc).isoformat(), "cartelle": [n for _, n in cartelle(m)],
            "bozze": cartella_bozze(m), "messaggi": out}
    m.logout()
    json.dump(info, open("posta.json", "w"), ensure_ascii=False)
    print(f"letti {len(out)} messaggi")          # nel log solo il numero, mai il contenuto


def componi(b):
    msg = EmailMessage()
    msg["From"] = f"{FIRMA_NOME} <{UTENTE}>"
    msg["To"] = b["a"]
    if b.get("cc"): msg["Cc"] = b["cc"]
    msg["Subject"] = b["oggetto"]
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = b.get("message_id") or make_msgid(domain="achevents.com")
    if b.get("in_reply_to"):
        msg["In-Reply-To"] = b["in_reply_to"]
        msg["References"] = (b.get("references", "") + " " + b["in_reply_to"]).strip()
    msg.set_content(b["testo"])
    if b.get("html"): msg.add_alternative(b["html"], subtype="html")
    return msg


def bozze(file):
    lettere = json.load(open(file))
    m = connetti()
    cart = cartella_bozze(m)
    for b in lettere:
        msg = componi(b)
        m.append(cart, "(\\Draft \\Seen)", imaplib.Time2Internaldate(time.time()), msg.as_bytes())
    m.logout()
    print(f"{len(lettere)} bozze salvate nella cartella {cart}")


def manda(file):
    lettere = json.load(open(file))
    s = smtplib.SMTP_SSL(HOST, 465)
    s.login(UTENTE, PWD)
    m = connetti()
    cart = cartella_bozze(m)
    inviate = next((n for t, n in cartelle(m) if "\\Sent" in t), "Sent")
    for b in lettere:
        msg = componi(b)
        s.send_message(msg)
        m.append(inviate, "(\\Seen)", imaplib.Time2Internaldate(time.time()), msg.as_bytes())
        # toglie la bozza con lo stesso oggetto e destinatario
        m.select(cart)
        typ, ids = m.search(None, "SUBJECT", '"%s"' % b["oggetto"].replace('"', ""), "TO", '"%s"' % parseaddr(b["a"])[1])
        for i in (ids[0].split() if ids and ids[0] else []):
            m.store(i, "+FLAGS", "\\Deleted")
        m.expunge()
    m.logout(); s.quit()
    print(f"{len(lettere)} lettere inviate")


if __name__ == "__main__":
    az = sys.argv[1] if len(sys.argv) > 1 else "leggi"
    if az == "leggi": leggi(int(sys.argv[2]) if len(sys.argv) > 2 else 14)
    elif az == "bozze": bozze(sys.argv[2])
    elif az == "manda": manda(sys.argv[2])
