const CACHE_VERSION = "robs-solar-v3";

self.addEventListener("install", (event) => {
  event.waitUntil(self.skipWaiting());
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    (async () => {
      await self.clients.claim();
      const clients = await self.clients.matchAll({ type: "window" });
      for (const client of clients) {
        client.postMessage({ type: "SW_ACTIVATED", version: CACHE_VERSION });
      }
    })(),
  );
});

self.addEventListener("message", (event) => {
  if (event.data?.type === "SKIP_WAITING") {
    event.waitUntil(self.skipWaiting());
  }
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  // Never intercept API traffic — stale metrics caused device mismatches.
  if (url.pathname.startsWith("/backend")) {
    return;
  }
  if (event.request.mode === "navigate") {
    event.respondWith(
      fetch(event.request).catch(
        () =>
          new Response(
            `<!DOCTYPE html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width'><title>Offline</title></head><body style='font-family:system-ui;background:#0c0f14;color:#f8fafc;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0'><p>Rob's Solar requires a connection (${CACHE_VERSION}).</p></body></html>`,
            { headers: { "Content-Type": "text/html" } },
          ),
      ),
    );
  }
});
