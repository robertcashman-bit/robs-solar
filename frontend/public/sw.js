self.addEventListener("install", (event) => {
  event.waitUntil(self.skipWaiting());
});

self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener("fetch", (event) => {
  if (event.request.mode === "navigate") {
    event.respondWith(
      fetch(event.request).catch(
        () =>
          new Response(
            "<!DOCTYPE html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width'><title>Offline</title></head><body style='font-family:system-ui;background:#0c0f14;color:#f8fafc;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0'><p>Rob's Solar requires a connection.</p></body></html>",
            { headers: { "Content-Type": "text/html" } },
          ),
      ),
    );
  }
});
