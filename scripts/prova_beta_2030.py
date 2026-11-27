"""Prova della beta «Events 2030» (27/11/2026): toccando una sezione si apre la finestra dei filtri tematici,
con «Tutto» scelto di default; un genere filtra l'elenco come prima, «Tutto» lo toglie.
Serve un Chrome e playwright: dove mancano (flussi di GitHub) la prova si salta e lo dice.
Uso: python3 scripts/prova_beta_2030.py"""
import asyncio, os, shutil, sys
RADICE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


async def prova():
    from playwright.async_api import async_playwright
    chrome = shutil.which("google-chrome") or shutil.which("chromium")
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=chrome, args=["--no-sandbox", "--allow-file-access-from-files"])
        pg = await (await b.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)).new_page()
        await pg.goto("file://" + os.path.join(RADICE, "index.html"))
        await pg.wait_for_timeout(2500)
        assert not await pg.is_visible("#nA .rowg"), "i filtri tematici devono essere nascosti nella pagina"
        prima = await pg.text_content("#count")
        await pg.click('.modes [data-mode="s"]')
        await pg.wait_for_selector("#betaGen .bg-tutto", timeout=3000)
        assert await pg.get_attribute("#betaGen .bg-tutto", "aria-pressed") == "true", "«Tutto» deve essere scelto di default"
        n = await pg.locator("#betaGen .ch.gq").count()
        assert n >= 2, f"nella finestra servono i generi, trovati {n}"
        await pg.locator("#betaGen .ch.gq:not([disabled])").first.click()
        await pg.wait_for_timeout(600)
        assert not await pg.is_visible("#betaGen"), "dopo la scelta la finestra si chiude"
        dopo = await pg.text_content("#count")
        assert dopo != prima, "il genere scelto deve cambiare l'elenco"
        await pg.click('.modes [data-mode="s"]')
        await pg.wait_for_selector("#betaGen .bg-tutto")
        assert await pg.get_attribute("#betaGen .bg-tutto", "aria-pressed") == "false"
        await pg.click("#betaGen .bg-tutto")
        await pg.wait_for_timeout(600)
        assert await pg.text_content("#count") == prima, "«Tutto» deve togliere il genere"
        await b.close()


def main():
    try:
        import playwright  # noqa: F401
    except ImportError:
        print("prova beta 2030 saltata: manca playwright"); return 0
    if not (shutil.which("google-chrome") or shutil.which("chromium")):
        print("prova beta 2030 saltata: manca Chrome"); return 0
    asyncio.run(prova())
    print("prova beta 2030: finestra dei filtri riuscita")
    return 0


if __name__ == "__main__":
    sys.exit(main())
