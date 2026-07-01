"use client";

import { useEffect, useState } from "react";

const DISMISS_KEY = "robs-solar-install-dismissed";

type BeforeInstallPromptEvent = Event & {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
};

function isIosSafari(): boolean {
  if (typeof navigator === "undefined") {
    return false;
  }
  const ua = navigator.userAgent;
  const ios = /iPad|iPhone|iPod/.test(ua);
  const safari = /Safari/.test(ua) && !/CriOS|FxiOS|EdgiOS/.test(ua);
  return ios && safari;
}

function isStandalone(): boolean {
  if (typeof window === "undefined") {
    return false;
  }
  const standaloneMedia =
    typeof window.matchMedia === "function"
      ? window.matchMedia("(display-mode: standalone)").matches
      : false;
  return (
    standaloneMedia ||
    ("standalone" in navigator && (navigator as Navigator & { standalone?: boolean }).standalone === true)
  );
}

function readInstallEligibility(): { eligible: boolean; iosHint: boolean } {
  if (typeof window === "undefined") {
    return { eligible: false, iosHint: false };
  }
  if (isStandalone() || localStorage.getItem(DISMISS_KEY) === "1") {
    return { eligible: false, iosHint: false };
  }
  if (isIosSafari()) {
    return { eligible: true, iosHint: true };
  }
  return { eligible: false, iosHint: false };
}

export function InstallAppBanner() {
  const [initial] = useState(readInstallEligibility);
  const [installEvent, setInstallEvent] = useState<BeforeInstallPromptEvent | null>(null);
  const [dismissed, setDismissed] = useState(false);
  const [androidEligible, setAndroidEligible] = useState(false);

  useEffect(() => {
    if (initial.eligible || dismissed) {
      return;
    }

    const onBeforeInstall = (event: Event) => {
      event.preventDefault();
      setInstallEvent(event as BeforeInstallPromptEvent);
      setAndroidEligible(true);
    };

    window.addEventListener("beforeinstallprompt", onBeforeInstall);
    return () => window.removeEventListener("beforeinstallprompt", onBeforeInstall);
  }, [initial.eligible, dismissed]);

  const visible = !dismissed && (initial.eligible || androidEligible);

  const dismiss = () => {
    localStorage.setItem(DISMISS_KEY, "1");
    setDismissed(true);
  };

  const install = async () => {
    if (!installEvent) {
      return;
    }
    await installEvent.prompt();
    await installEvent.userChoice;
    setInstallEvent(null);
    setAndroidEligible(false);
    setDismissed(true);
  };

  if (!visible) {
    return null;
  }

  return (
    <div className="mx-auto mb-4 max-w-3xl rounded-xl border border-amber-400/35 bg-amber-500/10 px-4 py-3 text-sm text-amber-950 dark:text-amber-100">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="font-semibold">Install Rob&apos;s Solar on your phone</p>
          {initial.iosHint ? (
            <p className="mt-1 text-xs opacity-90">
              Tap Share, then &quot;Add to Home Screen&quot; to open the app like a native app.
            </p>
          ) : (
            <p className="mt-1 text-xs opacity-90">
              Add a home-screen shortcut for quick access and full-screen monitoring.
            </p>
          )}
        </div>
        <div className="flex shrink-0 gap-2">
          {!initial.iosHint && installEvent ? (
            <button type="button" className="solar-btn-primary text-xs" onClick={() => void install()}>
              Install app
            </button>
          ) : null}
          <button type="button" className="solar-btn-ghost text-xs" onClick={dismiss}>
            Dismiss
          </button>
        </div>
      </div>
    </div>
  );
}
