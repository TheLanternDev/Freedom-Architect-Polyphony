/**
 * Offline-first service worker z automatycznym cache-busting.
 *
 * CACHE_VERSION jest aktualizowany przy każdym renderze przez Vite
 * (sw-version.ts plugin) lub ręcznie przed deployem.
 */
const CACHE_VERSION = "__BUILD_TIMESTAMP__";
const CACHE_NAME = `aw-cache-${CACHE_VERSION}`;
const STATIC_ASSETS = ["/", "/index.html"];
const API_CACHE_ROUTES = ["/health", "/integrations/status"];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(STATIC_ASSETS)),
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((names) =>
      Promise.all(
        names
          .filter((name) => name.startsWith("aw-cache-") && name !== CACHE_NAME)
          .map((name) => caches.delete(name)),
      ),
    ),
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);

  if (event.request.method !== "GET") return;

  const isStaticAsset =
    url.pathname.startsWith("/assets/") ||
    url.pathname.endsWith(".html") ||
    url.pathname === "/";

  const isApiCache = API_CACHE_ROUTES.some((r) => url.pathname === r);

  if (isStaticAsset) {
    // Network-first for HTML (picks up new deploys), cache-first for hashed assets
    const isHtml = url.pathname.endsWith(".html") || url.pathname === "/";
    if (isHtml) {
      event.respondWith(
        fetch(event.request)
          .then((response) => {
            if (response.ok) {
              const clone = response.clone();
              caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
            }
            return response;
          })
          .catch(() => caches.match(event.request).then((r) => r || new Response("Offline", { status: 503 }))),
      );
    } else {
      event.respondWith(
        caches.match(event.request).then(
          (cached) =>
            cached ||
            fetch(event.request).then((response) => {
              if (response.ok) {
                const clone = response.clone();
                caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
              }
              return response;
            }),
        ),
      );
    }
    return;
  }

  if (isApiCache) {
    event.respondWith(
      fetch(event.request)
        .then((response) => {
          if (response.ok) {
            const clone = response.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
          }
          return response;
        })
        .catch(() => caches.match(event.request).then((r) => r || new Response("{}", { status: 503 }))),
    );
    return;
  }
});
