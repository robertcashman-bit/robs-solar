import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  ApiError,
  COLD_START_GET_TIMEOUT_MS,
  DEFAULT_GET_TIMEOUT_MS,
  LIVE_REFRESH_TIMEOUT_MS,
  MUTATION_TIMEOUT_MS,
  REPORTS_GET_TIMEOUT_MS,
  apiClient,
  resolveTimeoutMs,
} from "@/lib/api-client";

describe("apiClient timeouts", () => {
  beforeEach(() => {
    vi.useFakeTimers();
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

  it("bounds live-refresh POSTs so Refresh cannot hang on the default mutation window", () => {
    expect(resolveTimeoutMs("/finance/live-refresh", "POST")).toBe(LIVE_REFRESH_TIMEOUT_MS);
    expect(LIVE_REFRESH_TIMEOUT_MS).toBeLessThan(MUTATION_TIMEOUT_MS);
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
});
