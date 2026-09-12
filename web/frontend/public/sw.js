/* REDACTED service worker — the shell survives the network.
   Shell: network-first with cache fallback (the app always opens).
   Hashed Vite assets: stale-while-revalidate.
   /api and /ws: NEVER intercepted — the war is live or it is not. */
const SHELL = 'vf-shell-v3';

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(SHELL)
      .then((c) => c.addAll(['/', '/manifest.webmanifest']))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== SHELL).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);
  // opérations vivantes → jamais de cache
  if (url.pathname.startsWith('/api') || url.pathname.startsWith('/ws')) return;
  if (event.request.method !== 'GET') return;
  // C3 FIX (audit): in prod the API is SAME-ORIGIN (no /api prefix) —
  // every backend GET route must bypass the SWR branch or the app
  // renders days-stale state (provider chip, mission status, plans).
  if (/^\/(provider|health|reports|report|workspace|mission|missions|chat|tools|tool|dashboard|persona|snapshots|skills|admin|license|graph)\b/.test(url.pathname)) return;

  // navigation : réseau d'abord, repli shell (mode avion → l'app s'ouvre quand même)
  if (event.request.mode === 'navigate') {
    event.respondWith(
      fetch(event.request)
        .then((res) => {
          const copy = res.clone();
          caches.open(SHELL).then((c) => c.put('/', copy));
          return res;
        })
        .catch(() => caches.match('/'))
    );
    return;
  }

  // assets (hashés par Vite) : stale-while-revalidate
  event.respondWith(
    caches.match(event.request).then((hit) => {
      const net = fetch(event.request)
        .then((res) => {
          if (res && res.ok) {
            const copy = res.clone();
            caches.open(SHELL).then((c) => c.put(event.request, copy));
          }
          return res;
        })
        .catch(() => hit);
      return hit || net;
    })
  );
});
