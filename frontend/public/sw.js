// InduStreakAI Service Worker — PWA with offline support
const CACHE_VERSION = 'v1';
const SHELL_CACHE = `ikp-shell-${CACHE_VERSION}`;
const DATA_CACHE = `ikp-data-${CACHE_VERSION}`;

const SHELL_ASSETS = ['/', '/chat', '/graph', '/maintenance', '/compliance', '/upload', '/search'];

// ── INSTALL: pre-cache app shell ──────────────────────────────────────────────
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(SHELL_CACHE).then((cache) => cache.addAll(SHELL_ASSETS)).then(() => self.skipWaiting())
  );
});

// ── ACTIVATE: clear old caches ────────────────────────────────────────────────
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== SHELL_CACHE && k !== DATA_CACHE).map((k) => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

// ── FETCH: network-first for API, cache-first for shell ───────────────────────
self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);

  // API: network-first, fallback to cache
  if (url.pathname.startsWith('/api/')) {
    event.respondWith(
      fetch(event.request)
        .then((res) => {
          const clone = res.clone();
          caches.open(DATA_CACHE).then((c) => c.put(event.request, clone));
          return res;
        })
        .catch(() => caches.match(event.request))
    );
    return;
  }

  // Shell: cache-first
  event.respondWith(caches.match(event.request).then((cached) => cached || fetch(event.request)));
});

// ── BACKGROUND SYNC: flush pending observations ───────────────────────────────
self.addEventListener('sync', (event) => {
  if (event.tag === 'sync-observations') {
    event.waitUntil(syncPending());
  }
});

async function syncPending() {
  // Flush any queued offline submissions stored in IndexedDB
  // Frontend handles the actual IDB calls; SW just triggers the flush
  const clients = await self.clients.matchAll();
  clients.forEach((c) => c.postMessage({ type: 'SYNC_PENDING' }));
}
