const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "/backend";

/** Default GET timeout for ordinary finance reads. */
export const DEFAULT_GET_TIMEOUT_MS = 12_000;
/** Reports aggregates can exceed the default on cold SQLite / large ledgers. */
export const REPORTS_GET_TIMEOUT_MS = 45_000;
/** Live balance refresh (QuickFile + Lunch Flow) — client aborts before a long hang. */
export const LIVE_REFRESH_TIMEOUT_MS = 15_000;
/** POST/PUT/PATCH/DELETE — allow slower writes. */
export const MUTATION_TIMEOUT_MS = 45_000;
/**
 * QuickFile force_full (~2-year) import can burn most of the daily 1000-request
 * quota and run for many minutes. Client must not abort at the normal mutation timeout.
 */
export const QUICKFILE_FORCE_FULL_SYNC_TIMEOUT_MS = 15 * 60_000;
/**
 * Auth bootstrap and health warmup must outlast a Vercel Python cold start
 * (~20–30s). A short abort looks like “logged out” and kicks the user to /login.
 */
export const COLD_START_GET_TIMEOUT_MS = 45_000;

const COLD_START_GET_PATHS = new Set([
  "/auth/me",
  "/health",
  "/auth/magic-code/status",
]);

/** Auth mutations must not enter the CSRF re-bootstrap retry loop. */
const NO_CSRF_RECOVERY_PATHS = new Set([
  "/auth/login",
  "/auth/logout",
  "/auth/magic-code/request",
  "/auth/magic-code/verify",
  "/auth/magic-link/consume",
]);

function barePath(path: string): string {
  return path.split("?")[0] ?? path;
}

function isReportsPath(path: string): boolean {
  const bare = barePath(path);
  return bare === "/finance/reports" || bare.startsWith("/finance/reports/");
}

function isActiveBudgetsPath(path: string): boolean {
  return barePath(path) === "/finance/budgets/active";
}

function isLiveRefreshPath(path: string): boolean {
  return barePath(path) === "/finance/live-refresh";
}

function isQuickFileForceFullSyncPath(path: string): boolean {
  const [bare, query = ""] = path.split("?");
  return (
    bare === "/finance/integrations/quickfile/sync"
    && /(?:^|&)force_full=true(?:&|$)/i.test(query)
  );
}

function isMutationMethod(method?: string): boolean {
  return Boolean(method && method.toUpperCase() !== "GET");
}

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

let csrfToken: string | null = null;
let csrfBootstrapInFlight: Promise<string | null> | null = null;

export function setCsrfToken(token: string | null) {
  csrfToken = token;
}

export function getCsrfToken() {
  return csrfToken;
}

export function clearCsrfToken() {
  csrfToken = null;
}

function isInvalidCsrfMessage(detail: string): boolean {
  return /invalid csrf token/i.test(detail);
}

/**
 * Re-read CSRF from the signed session cookie via GET /auth/me.
 * Used after timeouts / invalid CSRF and before mutations when the in-memory
 * token was never set (cached-session first paint).
 */
export async function bootstrapCsrfToken(): Promise<string | null> {
  if (csrfToken) {
    return csrfToken;
  }
  if (csrfBootstrapInFlight) {
    return csrfBootstrapInFlight;
  }
  csrfBootstrapInFlight = (async () => {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), COLD_START_GET_TIMEOUT_MS);
    try {
      const response = await fetch(`${API_BASE}/auth/me`, {
        credentials: "include",
        signal: controller.signal,
      });
      if (!response.ok) {
        return null;
      }
      const body = (await response.json()) as { csrf_token?: unknown };
      if (typeof body.csrf_token !== "string" || !body.csrf_token) {
        return null;
      }
      csrfToken = body.csrf_token;
      return csrfToken;
    } catch {
      return null;
    } finally {
      clearTimeout(timer);
      csrfBootstrapInFlight = null;
    }
  })();
  return csrfBootstrapInFlight;
}

export function resolveTimeoutMs(path: string, method?: string): number {
  if (isLiveRefreshPath(path)) {
    return LIVE_REFRESH_TIMEOUT_MS;
  }
  if (isQuickFileForceFullSyncPath(path) && method && method !== "GET") {
    return QUICKFILE_FORCE_FULL_SYNC_TIMEOUT_MS;
  }
  if (method && method !== "GET") {
    return MUTATION_TIMEOUT_MS;
  }
  const bare = barePath(path);
  if (COLD_START_GET_PATHS.has(bare)) {
    return COLD_START_GET_TIMEOUT_MS;
  }
  if (isReportsPath(path) || isActiveBudgetsPath(path)) {
    return REPORTS_GET_TIMEOUT_MS;
  }
  return DEFAULT_GET_TIMEOUT_MS;
}

async function parseErrorDetail(response: Response): Promise<string> {
  let detail = response.statusText;
  try {
    const body = await response.json();
    const raw = body.detail ?? body.error?.message ?? body.message ?? detail;
    if (typeof raw === "string") {
      detail = raw;
    } else if (Array.isArray(raw)) {
      detail = raw
        .map((item) => {
          if (typeof item === "string") return item;
          if (item && typeof item === "object" && "msg" in item) {
            return String((item as { msg: unknown }).msg);
          }
          return JSON.stringify(item);
        })
        .join("; ");
    } else if (raw != null) {
      detail = String(raw);
    }
  } catch {
    // ignore parse errors
  }
  return detail;
}

type RequestOptions = RequestInit & {
  /** Internal: already retried after CSRF bootstrap — do not loop. */
  _csrfRetried?: boolean;
};

async function request<T>(path: string, init?: RequestOptions): Promise<T> {
  const method = (init?.method ?? "GET").toUpperCase();
  const bare = barePath(path);
  const allowCsrfRecovery = !NO_CSRF_RECOVERY_PATHS.has(bare);

  if (isMutationMethod(method) && !csrfToken && allowCsrfRecovery) {
    await bootstrapCsrfToken();
  }

  const headers = new Headers(init?.headers ?? {});
  if (!headers.has("Content-Type") && init?.body) {
    headers.set("Content-Type", "application/json");
  }
  if (csrfToken && isMutationMethod(method)) {
    headers.set("X-CSRF-Token", csrfToken);
  }

  const timeoutMs = resolveTimeoutMs(path, init?.method);
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers,
      credentials: "include",
      signal: init?.signal ?? controller.signal,
    });
  } catch (err) {
    if (err instanceof Error && err.name === "AbortError") {
      // Stale in-memory CSRF must not be reused after an abort mid-flight.
      clearCsrfToken();
      throw new ApiError("The server took too long to respond.", 504);
    }
    throw new ApiError("Cannot reach the finance server. Is it running?", 503);
  } finally {
    clearTimeout(timer);
  }

  if (!response.ok) {
    let detail = await parseErrorDetail(response);
    if (
      isQuickFileForceFullSyncPath(path)
      && (response.status === 504 || /FUNCTION_INVOCATION_TIMEOUT/i.test(detail))
    ) {
      detail =
        "The server timed out before the import finished. Any year chunks already "
        + "saved are kept — click Import full history again to continue.";
    }

    const invalidCsrf =
      response.status === 403 && isInvalidCsrfMessage(detail);
    if (invalidCsrf || response.status === 504) {
      clearCsrfToken();
    }

    if (
      invalidCsrf
      && isMutationMethod(method)
      && allowCsrfRecovery
      && !init?._csrfRetried
    ) {
      const refreshed = await bootstrapCsrfToken();
      if (refreshed) {
        return request<T>(path, { ...init, _csrfRetried: true });
      }
    }

    throw new ApiError(String(detail), response.status);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

export const apiClient = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, {
      method: "POST",
      body: body ? JSON.stringify(body) : undefined,
    }),
  put: <T>(path: string, body?: unknown) =>
    request<T>(path, {
      method: "PUT",
      body: body ? JSON.stringify(body) : undefined,
    }),
  patch: <T>(path: string, body?: unknown) =>
    request<T>(path, {
      method: "PATCH",
      body: body ? JSON.stringify(body) : undefined,
    }),
  delete: <T>(path: string) => request<T>(path, { method: "DELETE" }),
  postForm: async <T>(path: string, form: FormData): Promise<T> => {
    if (!csrfToken && !NO_CSRF_RECOVERY_PATHS.has(barePath(path))) {
      await bootstrapCsrfToken();
    }
    const headers = new Headers();
    if (csrfToken) {
      headers.set("X-CSRF-Token", csrfToken);
    }
    const response = await fetch(`${API_BASE}${path}`, {
      method: "POST",
      headers,
      body: form,
      credentials: "include",
    });
    if (!response.ok) {
      let detail = await parseErrorDetail(response);
      if (response.status === 403 && isInvalidCsrfMessage(detail)) {
        clearCsrfToken();
        const refreshed = await bootstrapCsrfToken();
        if (refreshed) {
          const retryHeaders = new Headers();
          retryHeaders.set("X-CSRF-Token", refreshed);
          const retry = await fetch(`${API_BASE}${path}`, {
            method: "POST",
            headers: retryHeaders,
            body: form,
            credentials: "include",
          });
          if (retry.ok) {
            return retry.json() as Promise<T>;
          }
          detail = await parseErrorDetail(retry);
          throw new ApiError(String(detail), retry.status);
        }
      }
      throw new ApiError(String(detail), response.status);
    }
    return response.json() as Promise<T>;
  },
};
