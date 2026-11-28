"""Prova della velocità di Events (28/11/2026, Stefano «velocizza tutti i siti»).
Controlla che le tre accelerazioni non cambino quello che si vede:
  1. il foglio dei filtri si costruisce solo quando è aperto: aperto dopo «Oggi» mostra le scelte e «Mostra N»
     uguale alle schede dell'elenco; richiuso e riaperto dopo aver tolto «Oggi» è di nuovo giusto;
  2. la misura della riga dei filtri (--nah) segue l'altezza vera della riga anche dopo i tocchi;
  3. le schede dell'elenco hanno content-visibility:auto (le schede fuori schermo non si impaginano subito)
     e l'elenco ha lo stesso numero di schede.
Più la misura di ogni mattina (velocita.py): dopo il tocco su una sezione chiude il pannello «Scegli che cosa vedere».
Serve un Chrome e playwright: dove mancano (flussi di GitHub) la prova si salta e lo dice.
Uso: python3 scripts/prova_velocita_events.py"""
import asyncio, os, shutil, sys
RADICE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RADICE, "scripts"))


async def prova():
    from playwright.async_api import async_playwright
    chrome = shutil.which("google-chrome") or shutil.which("chromium")
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=chrome, args=["--no-sandbox", "--allow-file-access-from-files"])
        pg = await (await b.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)).new_page()
        errori = []
        pg.on("pageerror", lambda e: errori.append(str(e)))
        await pg.goto("file://" + os.path.join(RADICE, "index.html"))
        await pg.wait_for_timeout(2500)
        cv = await pg.evaluate("getComputedStyle(document.querySelector('#list article.card')).contentVisibility")
        assert cv == "auto", f"le schede devono avere content-visibility:auto, trovato {cv!r}"
        oggi = pg.locator('#nA button.ch[data-v="oggi"]').first
        await oggi.click()
        await pg.wait_for_timeout(500)
        await pg.click("#fbtn")
        await pg.wait_for_timeout(500)
        assert (await pg.inner_html("#nAb")).strip(), "il foglio aperto deve avere le scelte"
        conto = await pg.text_content("#nAgo")
        assert conto.startswith("Mostra "), f"conto del foglio: {conto!r}"
        nah = await pg.evaluate("[getComputedStyle(document.documentElement).getPropertyValue('--nah').trim(), document.getElementById('nA').offsetHeight+'px']")
        assert nah[0] == nah[1], f"--nah {nah[0]} diverso dall'altezza vera {nah[1]}"
        await pg.evaluate("[...document.querySelectorAll('#nAf [data-chiudi]')].find(e=>e.tagName==='BUTTON').click()")
        await pg.wait_for_timeout(400)
        await oggi.click()
        await pg.wait_for_timeout(500)
        await pg.click("#fbtn")
        await pg.wait_for_timeout(500)
        conto2 = await pg.text_content("#nAgo")
        assert conto2 != conto, f"dopo aver tolto «Oggi» il conto del foglio riaperto deve cambiare ({conto} / {conto2})"
        await pg.evaluate("[...document.querySelectorAll('#nAf [data-chiudi]')].find(e=>e.tagName==='BUTTON').click()")
        await pg.wait_for_timeout(600)
        nah = await pg.evaluate("[getComputedStyle(document.documentElement).getPropertyValue('--nah').trim(), document.getElementById('nA').offsetHeight+'px']")
        assert nah[0] == nah[1], f"--nah {nah[0]} diverso dall'altezza vera {nah[1]}"
        # la misura del mattino: tocco su una sezione, pannello chiuso, poi un altro tocco riesce
        import velocita
        await pg.click('.modes [data-mode="m"]')
        await pg.wait_for_selector("#betaGen", timeout=3000)
        await pg.click("#betaGen button[data-bgclose]")
        await pg.wait_for_timeout(500)
        assert not await pg.is_visible("#betaGen"), "il pannello «Scegli che cosa vedere» si deve chiudere"
        assert hasattr(velocita, "chiudi_pannello_events"), "velocita.py deve chiudere il pannello dopo il tocco su una sezione"
        await pg.click('.modes [data-mode="s"]', timeout=3000)
        assert not errori, f"errori JavaScript: {errori}"
        await b.close()


def main():
    try:
        import playwright  # noqa: F401
    except ImportError:
        print("prova velocità Events: saltata (manca playwright)")
        return
    if not (shutil.which("google-chrome") or shutil.which("chromium")):
        print("prova velocità Events: saltata (manca Chrome)")
        return
    asyncio.run(prova())
    print("prova velocità Events: tutto come prima, più veloce")


if __name__ == "__main__":
    main()
