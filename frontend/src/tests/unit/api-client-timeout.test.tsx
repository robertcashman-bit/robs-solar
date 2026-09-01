import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  ApiError,
  COLD_START_GET_TIMEOUT_MS,
  DEFAULT_GET_TIMEOUT_MS,
  LIVE_REFRESH_TIMEOUT_MS,
  MUTATION_TIMEOUT_MS,
  QUICKFILE_FORCE_FULL_SYNC_TIMEOUT_MS,
  REPORTS_GET_TIMEOUT_MS,
  apiClient,
  bootstrapCsrfToken,
  clearCsrfToken,
  getCsrfToken,
  resolveTimeoutMs,
  setCsrfToken,
} from "@/lib/api-client";

describe("apiClient timeouts", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    clearCsrfToken();
    vi.stubGlobal(
      "fetch",
      vi.fn((_url: string, init?: RequestInit) => {
        return new Promise((_resolve, reject) => {
          const abort = () => {
            const err = new Error("Aborted");
            err.name = "AbortError";
            reject(err);
          };
          if (init?.signal?.aborted) {
            abort();
            return;
          }
          init?.signal?.addEventListener("abort", abort, { once: true });
        });
      }),
    );
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    clearCsrfToken();
  });

  it("gives /auth/me and /health a cold-start tolerant GET timeout", () => {
    expect(resolveTimeoutMs("/auth/me")).toBe(COLD_START_GET_TIMEOUT_MS);
    expect(resolveTimeoutMs("/health")).toBe(COLD_START_GET_TIMEOUT_MS);
    expect(resolveTimeoutMs("/auth/magic-code/status")).toBe(COLD_START_GET_TIMEOUT_MS);
    expect(resolveTimeoutMs("/finance/overview")).toBe(DEFAULT_GET_TIMEOUT_MS);
  });

  it("gives finance reports a longer GET timeout", () => {
    expect(resolveTimeoutMs("/finance/reports")).toBe(REPORTS_GET_TIMEOUT_MS);
    expect(resolveTimeoutMs("/finance/reports?month=2026-08")).toBe(REPORTS_GET_TIMEOUT_MS);
  });

  it("gives active budgets the same longer GET timeout as reports", () => {
    expect(resolveTimeoutMs("/finance/budgets/active")).toBe(REPORTS_GET_TIMEOUT_MS);
    expect(resolveTimeoutMs("/finance/budgets/active?scope=personal")).toBe(REPORTS_GET_TIMEOUT_MS);
  });

  it("bounds live-refresh POSTs so Refresh cannot hang on the default mutation window", () => {
    expect(resolveTimeoutMs("/finance/live-refresh", "POST")).toBe(LIVE_REFRESH_TIMEOUT_MS);
    expect(LIVE_REFRESH_TIMEOUT_MS).toBeLessThan(MUTATION_TIMEOUT_MS);
  });

  it("gives QuickFile force_full sync a long mutation timeout", () => {
    expect(
      resolveTimeoutMs("/finance/integrations/quickfile/sync?force_full=true", "POST"),
    ).toBe(QUICKFILE_FORCE_FULL_SYNC_TIMEOUT_MS);
    expect(
      resolveTimeoutMs("/finance/integrations/quickfile/sync", "POST"),
    ).toBe(MUTATION_TIMEOUT_MS);
    expect(QUICKFILE_FORCE_FULL_SYNC_TIMEOUT_MS).toBeGreaterThan(MUTATION_TIMEOUT_MS);
  });

  it("surfaces abort as 504, not 401", async () => {
    const pending = apiClient.get("/auth/me");
    const settled = pending.then(
      () => null,
      (error: unknown) => error,
    );
    await vi.advanceTimersByTimeAsync(COLD_START_GET_TIMEOUT_MS);
    const error = await settled;
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({
      status: 504,
      message: "The server took too long to respond.",
    });
    expect(error).not.toMatchObject({ status: 401 });
  });

  it("clears in-memory CSRF after an abort/504", async () => {
    setCsrfToken("stale-csrf");
    const pending = apiClient.get("/finance/overview");
    const settled = pending.then(
      () => null,
      (error: unknown) => error,
    );
    await vi.advanceTimersByTimeAsync(DEFAULT_GET_TIMEOUT_MS);
    await settled;
    expect(getCsrfToken()).toBeNull();
  });

  it("maps Vercel function timeout 504 into a retryable import message", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        new Response(
          JSON.stringify({ error: { code: "FUNCTION_INVOCATION_TIMEOUT" } }),
          { status: 504, headers: { "Content-Type": "application/json" } },
        ),
      ),
    );
    await expect(
      apiClient.post("/finance/integrations/quickfile/sync?force_full=true"),
    ).rejects.toMatchObject({
      status: 504,
      message: expect.stringMatching(/timed out before the import finished/i),
    });
  });

  it("does not rewrite 504 detail on non-force_full paths", async () => {
    setCsrfToken("csrf-ok");
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        new Response(
          JSON.stringify({ detail: "Gateway Timeout" }),
          { status: 504, headers: { "Content-Type": "application/json" } },
        ),
      ),
    );
    await expect(apiClient.post("/finance/live-refresh")).rejects.toMatchObject({
      status: 504,
      message: "Gateway Timeout",
    });
    await expect(
      apiClient.post("/finance/integrations/quickfile/sync"),
    ).rejects.toMatchObject({
      status: 504,
      message: "Gateway Timeout",
    });
  });

  it("re-bootstraps CSRF from /auth/me after Invalid CSRF then retries the mutation once", async () => {
    vi.useRealTimers();
    clearCsrfToken();
    const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
      const href = String(url);
      if (href.endsWith("/auth/me")) {
        return new Response(
          JSON.stringify({
            user: { username: "rob", role: "admin" },
            csrf_token: "fresh-csrf",
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }
      if (href.includes("/finance/live-refresh")) {
        const header = new Headers(init?.headers).get("X-CSRF-Token");
        if (header === "fresh-csrf") {
          return new Response(JSON.stringify({ ok: true }), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          });
        }
        return new Response(JSON.stringify({ detail: "Invalid CSRF token" }), {
          status: 403,
          headers: { "Content-Type": "application/json" },
        });
      }
      throw new Error(`unexpected url ${href}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    // Seed a stale token so the first mutation attempt fails CSRF.
    setCsrfToken("stale-csrf");
    const result = await apiClient.post("/finance/live-refresh", {});
    expect(result).toEqual({ ok: true });
    expect(getCsrfToken()).toBe("fresh-csrf");
    const liveCalls = fetchMock.mock.calls.filter(([url]) =>
      String(url).includes("/finance/live-refresh"),
    );
    expect(liveCalls).toHaveLength(2);
    expect(new Headers(liveCalls[0][1]?.headers).get("X-CSRF-Token")).toBe("stale-csrf");
    expect(new Headers(liveCalls[1][1]?.headers).get("X-CSRF-Token")).toBe("fresh-csrf");
  });

  it("bootstraps CSRF before a mutation when the in-memory token is missing", async () => {
    vi.useRealTimers();
    clearCsrfToken();
    const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
      const href = String(url);
      if (href.endsWith("/auth/me")) {
        return new Response(
          JSON.stringify({
            user: { username: "rob", role: "admin" },
            csrf_token: "boot-csrf",
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }
      if (href.includes("/finance/live-refresh")) {
        expect(new Headers(init?.headers).get("X-CSRF-Token")).toBe("boot-csrf");
        return new Response(JSON.stringify({ ok: true }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      throw new Error(`unexpected url ${href}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    await apiClient.post("/finance/live-refresh", {});
    expect(getCsrfToken()).toBe("boot-csrf");
    expect(fetchMock.mock.calls.some(([url]) => String(url).endsWith("/auth/me"))).toBe(true);
  });

  it("does not loop login codes when CSRF bootstrap fails", async () => {
    vi.useRealTimers();
    clearCsrfToken();
    const fetchMock = vi.fn(async (url: string) => {
      const href = String(url);
      if (href.endsWith("/auth/me")) {
        return new Response(JSON.stringify({ detail: "Unauthorized" }), {
          status: 401,
          headers: { "Content-Type": "application/json" },
        });
      }
      if (href.includes("/auth/magic-code/verify")) {
        return new Response(JSON.stringify({ detail: "Invalid CSRF token" }), {
          status: 403,
          headers: { "Content-Type": "application/json" },
        });
      }
      throw new Error(`unexpected url ${href}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      apiClient.post("/auth/magic-code/verify", { email: "a@b.c", code: "123456" }),
    ).rejects.toMatchObject({
      status: 403,
      message: "Invalid CSRF token",
    });
    expect(
      fetchMock.mock.calls.filter(([url]) => String(url).includes("/auth/magic-code/verify")),
    ).toHaveLength(1);
  });
});

describe("bootstrapCsrfToken", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    clearCsrfToken();
  });

  it("returns the existing token without another /auth/me round-trip", async () => {
    setCsrfToken("already");
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    await expect(bootstrapCsrfToken()).resolves.toBe("already");
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
