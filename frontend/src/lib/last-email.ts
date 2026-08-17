const LAST_EMAIL_KEY = "robs-finance.last-email";
const LEGACY_KEYS = [
  "robs-finance:last-email",
  "robs-solar.last-email",
  "lastSignInEmail",
  "last-email",
];

function storage(): Storage | null {
  if (typeof window === "undefined") {
    return null;
  }
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

export function readLastEmail(): string {
  const store = storage();
  if (!store) {
    return "";
  }
  const current = store.getItem(LAST_EMAIL_KEY)?.trim() ?? "";
  if (current) {
    return current;
  }
  for (const key of LEGACY_KEYS) {
    const legacy = store.getItem(key)?.trim() ?? "";
    if (legacy) {
      store.setItem(LAST_EMAIL_KEY, legacy);
      return legacy;
    }
  }
  return "";
}

export function rememberLastEmail(email: string): void {
  const store = storage();
  const normalized = email.trim().toLowerCase();
  if (!store || !normalized) {
    return;
  }
  store.setItem(LAST_EMAIL_KEY, normalized);
}

export function lastEmailStorageKey(): string {
  return LAST_EMAIL_KEY;
}
