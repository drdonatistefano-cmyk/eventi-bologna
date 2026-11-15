/* 15/11/2026 – prova «la guida come un'app» (achevents.com/prova-app/).
   Serve a Android per offrire «Installa». Pagina: prima la rete, la copia solo se manca la rete. Il resto passa com'è. */
const V = "prova-app-1";
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", e => e.waitUntil((async () => {
  for (const k of await caches.keys()) if (k !== V) await caches.delete(k);
  await self.clients.claim();
})()));
self.addEventListener("fetch", e => {
  const r = e.request;
  if (r.method !== "GET" || r.mode !== "navigate") return;
  e.respondWith((async () => {
    const c = await caches.open(V);
    try { const n = await fetch(r); if (n.ok) c.put("/prova-app/", n.clone()); return n; }
    catch (x) { const h = await c.match("/prova-app/"); if (h) return h; throw x; }
  })());
});
