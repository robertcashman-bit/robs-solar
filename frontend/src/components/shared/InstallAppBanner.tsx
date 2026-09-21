"use client";

import Link from "next/link";
import { useEffect, useState, useSyncExternalStore } from "react";

const DISMISS_KEY = "robs-finance-install-dismissed";
const DISMISS_EVENT = "robs-finance-install-dismiss";

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

const HIDDEN_ELIGIBILITY = { eligible: false, iosHint: false } as const;
const IOS_ELIGIBILITY = { eligible: true, iosHint: true } as const;
const ANDROID_ELIGIBILITY = { eligible: true, iosHint: false } as const;

function readInstallEligibility(): { eligible: boolean; iosHint: boolean } {
  if (typeof window === "undefined") {
    return HIDDEN_ELIGIBILITY;
  }
  if (isStandalone() || localStorage.getItem(DISMISS_KEY) === "1") {
    return HIDDEN_ELIGIBILITY;
  }
  if (isIosSafari()) {
    return IOS_ELIGIBILITY;
  }
  return ANDROID_ELIGIBILITY;
}

function readDismissed(): boolean {
  if (typeof window === "undefined") {
    return false;
  }
  return localStorage.getItem(DISMISS_KEY) === "1";
}

function subscribeDismiss(onStoreChange: () => void): () => void {
  if (typeof window === "undefined") {
    return () => undefined;
  }
  const handler = () => onStoreChange();
  window.addEventListener("storage", handler);
  window.addEventListener(DISMISS_EVENT, handler);
  return () => {
    window.removeEventListener("storage", handler);
    window.removeEventListener(DISMISS_EVENT, handler);
  };
}

function subscribeEligibility(onStoreChange: () => void): () => void {
  return subscribeDismiss(onStoreChange);
}

export function InstallAppBanner() {
  // Hydration-safe: server snapshots hide the banner; client may reveal after hydrate.
  const initial = useSyncExternalStore(
    subscribeEligibility,
    readInstallEligibility,
    () => HIDDEN_ELIGIBILITY,
  );
  const dismissed = useSyncExternalStore(subscribeDismiss, readDismissed, () => false);
  const [installEvent, setInstallEvent] = useState<BeforeInstallPromptEvent | null>(null);
  const [androidEligible, setAndroidEligible] = useState(false);

  useEffect(() => {
    if (dismissed || localStorage.getItem(DISMISS_KEY) === "1") {
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
    window.dispatchEvent(new Event(DISMISS_EVENT));
  };

  const install = async () => {
    if (!installEvent) {
      return;
    }
    await installEvent.prompt();
    await installEvent.userChoice;
    setInstallEvent(null);
    setAndroidEligible(false);
    localStorage.setItem(DISMISS_KEY, "1");
    window.dispatchEvent(new Event(DISMISS_EVENT));
  };

  if (!visible) {
    return null;
  }

  return (
    <div className="mx-auto mb-4 max-w-3xl rounded-xl border border-amber-400/35 bg-amber-500/10 px-4 py-3 text-sm text-amber-950 dark:text-amber-100">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="font-semibold">Install Rob&apos;s Finance on your phone</p>
          {initial.iosHint ? (
            <p className="mt-1 text-xs opacity-90">
              Tap Share, then &quot;Add to Home Screen&quot; to open the app like a native app.
            </p>
          ) : (
            <p className="mt-1 text-xs opacity-90">
              Add a Dock, Desktop, or home-screen shortcut. Settings → App shortcut restores the
              Mac launcher if it disappeared.
            </p>
          )}
        </div>
        <div className="flex shrink-0 gap-2">
          {!initial.iosHint && installEvent ? (
            <button type="button" className="solar-btn-primary text-xs" onClick={() => void install()}>
              Install app
            </button>
          ) : (
            <Link href="/settings#app-shortcut" className="solar-btn-primary text-xs">
              App shortcut
            </Link>
          )}
          <button type="button" className="solar-btn-ghost text-xs" onClick={dismiss}>
            Dismiss
          </button>
        </div>
      </div>
    </div>
  );
}
