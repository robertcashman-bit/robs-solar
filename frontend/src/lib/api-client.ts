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
 * Auth bootstrap and health warmup must outlast a Vercel Python cold start
 * (~20–30s). A short abort looks like “logged out” and kicks the user to /login.
 */
export const COLD_START_GET_TIMEOUT_MS = 45_000;

const COLD_START_GET_PATHS = new Set([
  "/auth/me",
  "/health",
  "/auth/magic-code/status",
]);

function isReportsPath(path: string): boolean {
  const bare = path.split("?")[0] ?? path;
  return bare === "/finance/reports" || bare.startsWith("/finance/reports/");
}

function isLiveRefreshPath(path: string): boolean {
  const bare = path.split("?")[0] ?? path;
  return bare === "/finance/live-refresh";
}

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

let csrfToken: string | null = null;

export function setCsrfToken(token: string | null) {
  csrfToken = token;
}

export function getCsrfToken() {
  return csrfToken;
}

export function resolveTimeoutMs(path: string, method?: string): number {
  if (isLiveRefreshPath(path)) {
    return LIVE_REFRESH_TIMEOUT_MS;
  }
  if (method && method !== "GET") {
    return MUTATION_TIMEOUT_MS;
  }
  const bare = path.split("?")[0] ?? path;
  if (COLD_START_GET_PATHS.has(bare)) {
    return COLD_START_GET_TIMEOUT_MS;
  }
  if (isReportsPath(path)) {
    return REPORTS_GET_TIMEOUT_MS;
  }
  return DEFAULT_GET_TIMEOUT_MS;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers ?? {});
  if (!headers.has("Content-Type") && init?.body) {
    headers.set("Content-Type", "application/json");
  }
  if (csrfToken && init?.method && init.method !== "GET") {
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
      throw new ApiError("The server took too long to respond.", 504);
    }
    throw new ApiError("Cannot reach the finance server. Is it running?", 503);
  } finally {
    clearTimeout(timer);
  }

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      const raw = body.detail ?? detail;
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
      let detail = response.statusText;
      try {
        const body = await response.json();
        detail = typeof body.detail === "string" ? body.detail : detail;
      } catch {
        // ignore
      }
      throw new ApiError(String(detail), response.status);
    }
    return response.json() as Promise<T>;
  },
};
