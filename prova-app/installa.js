/* 15/11/2026 – «Tienila sul telefono»: aiuta a mettere la guida nella schermata Home, come un'app.
   - Android (Chrome, Edge, Samsung): usa la finestra «Installa» del telefono; se non c'è, istruzioni dal menu ⋮.
   - iPhone/iPad: Apple non permette di farlo in automatico → 3 istruzioni con la freccia verso Condividi.
   - già aperta come app: non mostra niente. Computer: niente.
   Nella prova (PROVA=true) compare dopo 2 secondi a ogni visita; nella versione vera dalla 2ª visita, e la × la nasconde per 90 giorni. */
(function () {
  var PROVA = true, COL = "#3d5f7d", NOME = "Ach's Events Guide", ICONA = "/prova-app/icona-192.png";
  var ua = navigator.userAgent || "";
  var standalone = (window.matchMedia && matchMedia("(display-mode: standalone)").matches) || navigator.standalone === true;
  var ios = /iPhone|iPad|iPod/.test(ua) || (/Macintosh/.test(ua) && navigator.maxTouchPoints > 1);
  var ipad = /iPad/.test(ua) || (/Macintosh/.test(ua) && navigator.maxTouchPoints > 1);
  var android = /Android/.test(ua);
  var safari = ios && !/CriOS|FxiOS|EdgiOS|OPiOS|GSA\//.test(ua);
  var richiesta = null;
  function ls(k, v) { try { if (v === undefined) return localStorage.getItem(k); localStorage.setItem(k, v); } catch (_) { return null; } }
  if (standalone) {   // aperta dall'icona: nella prova lo dice, così si vede che ha funzionato
    if (PROVA) addEventListener("load", function () { avviso("✓ Aperta come app, dalla schermata Home"); });
    return;
  }
  if (!ios && !android) return;
  if (!PROVA) {
    var visite = +(ls("app_visite") || 0) + 1; ls("app_visite", visite);
    if (visite < 2 || Date.now() < +(ls("app_no") || 0)) return;
  }
  addEventListener("beforeinstallprompt", function (e) { e.preventDefault(); richiesta = e; });
  addEventListener("appinstalled", function () { chiudi(); avviso("✓ Fatto: la trovi nella schermata Home"); ls("app_no", Date.now() + 3650 * 864e5); });

  var css = ".appx{position:fixed;left:10px;right:10px;bottom:calc(12px + env(safe-area-inset-bottom));z-index:99990;display:flex;align-items:center;gap:10px;max-width:460px;margin:0 auto;"
    + "background:#fffdf8;color:#1f1c18;border:1px solid #e3dccd;border-radius:14px;padding:10px 10px 10px 12px;box-shadow:0 10px 28px rgba(0,0,0,.25);font:14px/1.3 -apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;cursor:pointer;animation:appsu .35s ease-out}"
    + ".appx img{width:40px;height:40px;border-radius:9px;flex:none}.appx div{flex:1;min-width:0}.appx b{display:block;font-size:15px}.appx em{font-style:normal;opacity:.72;font-size:13px}"
    + ".appx .vai{width:30px;height:30px;border-radius:50%;background:" + COL + ";color:#fff;display:grid;place-items:center;font-size:19px;font-weight:700;flex:none}"
    + ".appx .x{border:0;background:none;color:inherit;opacity:.55;font-size:22px;line-height:1;padding:4px 6px;cursor:pointer}"
    + ".appv{position:fixed;inset:0;z-index:99991;background:rgba(0,0,0,.45);animation:appf .2s}"
    + ".appf{position:fixed;left:0;right:0;z-index:99992;max-width:520px;margin:0 auto;background:#fffdf8;color:#1f1c18;padding:16px 16px calc(18px + env(safe-area-inset-bottom));font:15px/1.4 -apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;box-shadow:0 -8px 30px rgba(0,0,0,.3)}"
    + ".appf.giu{bottom:0;border-radius:18px 18px 0 0}.appf.su{top:0;border-radius:0 0 18px 18px}"
    + ".appf h4{display:flex;align-items:center;gap:10px;margin:0 0 8px;font-size:17px}.appf h4 img{width:32px;height:32px;border-radius:7px}"
    + ".appf ol{list-style:none;margin:0;padding:0;display:block}.appf small{font-size:13px;opacity:.75}.appf h4{font-weight:700}.appf li{display:flex;gap:12px;align-items:center;padding:10px 0;border-top:1px solid #e3dccd}.appf li:first-child{border-top:0}"
    + ".appf .n{width:24px;height:24px;border-radius:50%;background:" + COL + ";color:#fff;display:grid;place-items:center;font-size:13px;font-weight:700;flex:none}"
    + ".appf .t{display:inline;border:1px solid #d6cdbb;border-radius:6px;padding:1px 6px;font-weight:600;white-space:nowrap}"
    + ".appf .ok{display:block;width:100%;margin-top:12px;border:0;border-radius:10px;padding:11px;background:#efe8da;color:#1f1c18;font:600 15px -apple-system,BlinkMacSystemFont,sans-serif}"
    + ".appf .fr{display:block;font-size:26px;line-height:1;color:" + COL + ";animation:apps 1.1s infinite;text-align:center;margin-top:10px}.appf.su .fr{text-align:right;margin:0 4px 4px 0}"
    + ".apptoast{position:fixed;left:50%;top:calc(14px + env(safe-area-inset-top));transform:translateX(-50%);z-index:99993;background:#1f1c18;color:#fff;border-radius:10px;padding:10px 14px;font:600 14px -apple-system,BlinkMacSystemFont,sans-serif;box-shadow:0 8px 24px rgba(0,0,0,.3)}"
    + "@media(prefers-color-scheme:dark){.appx,.appf{background:#24211d;color:#f1ece2;border-color:#3a352e}.appf li{border-color:#3a352e}.appf .t{border-color:#4a443b}.appf .ok{background:#332e28;color:#f1ece2}}"
    + "@keyframes appsu{from{transform:translateY(30px);opacity:0}}@keyframes appf{from{opacity:0}}@keyframes apps{50%{transform:translateY(6px)}}";

  function el(h) { var d = document.createElement("div"); d.innerHTML = h; return d.firstChild; }
  var chip, velo, foglio, ospite, R;
  function radice() {
    if (R) return R;
    ospite = document.createElement("div"); ospite.id = "ach-installa";
    ospite.style.cssText = "all:initial;position:static";
    document.body.appendChild(ospite);
    R = ospite.attachShadow ? ospite.attachShadow({ mode: "open" }) : ospite;
    var st = document.createElement("style");
    st.textContent = ":host{all:initial}*{box-sizing:border-box;margin:0;padding:0;font-family:inherit}" + css;
    R.appendChild(st);
    return R;
  }
  function mostra() {
    if (chip && chip.parentNode) return;
    radice();
    chip = el('<div class="appx" role="button" aria-label="Metti la guida sul telefono"><img src="' + ICONA + '" alt=""><div><b>Tienila sul telefono</b><em>tocca qui: si apre come un\'app</em></div><span class="vai">›</span><button class="x" aria-label="Chiudi">×</button></div>');
    chip.onclick = function (e) { if (e.target.classList.contains("x")) { chiudi(); if (!PROVA) ls("app_no", Date.now() + 90 * 864e5); return; } aggiungi(); };
    R.appendChild(chip);
  }
  function chiudi() { [chip, velo, foglio].forEach(function (x) { if (x && x.parentNode) x.parentNode.removeChild(x); }); }
  function istruzioni(passi, sopra) {
    velo = el('<div class="appv"></div>'); velo.onclick = chiudiFoglio;
    var fr = '<span class="fr">' + (sopra ? "⬆" : "⬇") + '</span>';
    foglio = el('<div class="appf ' + (sopra ? "su" : "giu") + '">' + (sopra && ios ? fr : "") + '<h4><img src="' + ICONA + '" alt="">Mettila nella schermata Home</h4><ol>'
      + passi.map(function (p, i) { return '<li><span class="n">' + (i + 1) + '</span><span>' + p + '</span></li>'; }).join("")
      + '</ol><button class="ok">Ho capito</button>' + (!sopra ? fr : "") + '</div>');
    foglio.querySelector(".ok").onclick = chiudiFoglio;
    radice(); R.appendChild(velo); R.appendChild(foglio);
  }
  function chiudiFoglio() { [velo, foglio].forEach(function (x) { if (x && x.parentNode) x.parentNode.removeChild(x); }); }
  function aggiungi() {
    if (richiesta) {                       // Android: la finestra vera del telefono
      richiesta.prompt();
      richiesta.userChoice.then(function (r) { if (r.outcome === "accepted") chiudi(); richiesta = null; });
      return;
    }
    if (ios && safari) {
      istruzioni(["Tocca <span class='t'>Condividi ⬆︎</span> " + (ipad ? "in alto" : "qui sotto") + "<br><small>(se non lo vedi, tocca prima <span class='t'>•••</span>)</small>",
                  "Scorri e tocca <span class='t'>Aggiungi alla schermata Home</span>",
                  "Tocca <span class='t'>Aggiungi</span> in alto a destra"], ipad);
    } else if (ios) {
      istruzioni(["Tocca <span class='t'>Condividi ⬆︎</span> nella barra dell'indirizzo",
                  "Tocca <span class='t'>Aggiungi alla schermata Home</span>",
                  "Tocca <span class='t'>Aggiungi</span>"], true);
    } else {                               // Android senza la finestra automatica (Firefox, alcuni Samsung)
      istruzioni(["Tocca il menu <span class='t'>⋮</span> in alto a destra",
                  "Tocca <span class='t'>Installa app</span> oppure <span class='t'>Aggiungi a schermata Home</span>",
                  "Conferma con <span class='t'>Installa</span> o <span class='t'>Aggiungi</span>"], true);
    }
  }
  function avviso(t) {
    radice();
    var a = el('<div class="apptoast">' + t + '</div>'); R.appendChild(a);
    setTimeout(function () { a.remove(); }, 4000);
  }
  window.achInstalla = function () { mostra(); aggiungi(); };   // per i bottoni della pagina /app
  addEventListener("load", function () { setTimeout(mostra, PROVA ? 2000 : 6000); });
  if ("serviceWorker" in navigator) addEventListener("load", function () { navigator.serviceWorker.register("/prova-app/sw.js", { scope: "/prova-app/" }).catch(function () {}); });
})();
