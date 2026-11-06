// Cloudflare Worker per achevents.com – apre la città giusta in base a dove si trova il visitatore.
// Solo la home "/" viene smistata: chi è in Lombardia va su /milano/, tutti gli altri restano su Bologna.
// La scelta fatta col pulsante BO|MI (cookie "citta") vince sempre sulla posizione.
// I link condivisi (/milano/…, ?citta=bo) e i motori di ricerca non vengono mai rediretti.
export default {
  async fetch(request) {
    const url = new URL(request.url);
    if (url.pathname === "/" && request.method === "GET" && !url.search) {
      const cookie = request.headers.get("Cookie") || "";
      const scelta = (cookie.match(/(?:^|;\s*)citta=(bo|mi)/) || [])[1];
      const ua = request.headers.get("User-Agent") || "";
      const bot = /bot|crawl|spider|slurp|facebookexternalhit|preview/i.test(ua);
      const cf = request.cf || {};
      // Lombardia: codice regione ISO "25", oppure una sua provincia, oppure il nome
      const lombardia = cf.country === "IT" && (/^(25|MI|MB|BG|BS|CO|CR|LC|LO|MN|PV|SO|VA)$/.test(cf.regionCode || "") || /lombard/i.test(cf.region || ""));
      const citta = scelta || (lombardia ? "mi" : "bo");
      if (citta === "mi" && !bot) {
        return Response.redirect(url.origin + "/milano/", 302);
      }
    }
    return fetch(request);
  },
};
