/** Register the PWA service worker and reload when a new version activates. */

let reloadScheduled = false;

function reloadOnce() {
  if (reloadScheduled) {
    return;
  }
  reloadScheduled = true;
  window.location.reload();
}

export function registerServiceWorker(): void {
  if (typeof window === "undefined" || !("serviceWorker" in navigator)) {
    return;
  }

  // Skip reload on first SW install; only reload when replacing an active worker.
  let skipNextControllerChange = !navigator.serviceWorker.controller;

  navigator.serviceWorker.addEventListener("controllerchange", () => {
    if (skipNextControllerChange) {
      skipNextControllerChange = false;
      return;
    }
    reloadOnce();
  });

  void navigator.serviceWorker
    .register("/sw.js", { scope: "/", updateViaCache: "none" })
    .then((registration) => {
      const checkForUpdates = () => {
        void registration.update().catch(() => {});
      };

      checkForUpdates();

      document.addEventListener("visibilitychange", () => {
        if (document.visibilityState === "visible") {
          checkForUpdates();
        }
      });

      window.setInterval(checkForUpdates, 60 * 60 * 1000);

      registration.addEventListener("updatefound", () => {
        const installing = registration.installing;
        if (!installing) {
          return;
        }
        installing.addEventListener("statechange", () => {
          if (installing.state === "installed" && navigator.serviceWorker.controller) {
            installing.postMessage({ type: "SKIP_WAITING" });
          }
        });
      });

      if (registration.waiting && navigator.serviceWorker.controller) {
        registration.waiting.postMessage({ type: "SKIP_WAITING" });
      }
    })
    .catch(() => {
      /* SW optional — app works without it */
    });
}
