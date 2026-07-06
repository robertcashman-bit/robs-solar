const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "/backend";

export class ApiError extends Error {
  status: number;
  code?: string;

  constructor(message: string, status: number, code?: string) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

let csrfToken: string | null = null;

export function setCsrfToken(token: string | null) {
  csrfToken = token;
}

export function getCsrfToken() {
  return csrfToken;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers ?? {});
  if (!headers.has("Content-Type") && init?.body) {
    headers.set("Content-Type", "application/json");
  }
  if (csrfToken && init?.method && init.method !== "GET") {
    headers.set("X-CSRF-Token", csrfToken);
  }

  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers,
    credentials: "include",
  });

  if (!response.ok) {
    let detail = response.statusText;
    let code: string | undefined;
    try {
      const body = await response.json();
      const rawDetail = body.detail;
      if (typeof rawDetail === "object" && rawDetail !== null && "message" in rawDetail) {
        detail = String(rawDetail.message);
        if ("status" in rawDetail && rawDetail.status) {
          code = String(rawDetail.status);
        }
      } else if (rawDetail !== undefined) {
        detail = String(rawDetail);
      }
    } catch {
      // ignore parse errors
    }
    throw new ApiError(String(detail), response.status, code);
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
  delete: <T>(path: string) => request<T>(path, { method: "DELETE" }),
};
