import { act, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AuthProvider, useAuth } from "@/lib/auth-context";
import { ApiError } from "@/lib/api-client";
import { FINANCE_LAST_SESSION_USER_KEY } from "@/lib/finance-local-cache";

const get = vi.fn();
const post = vi.fn();

vi.mock("@/lib/api-client", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api-client")>("@/lib/api-client");
  return {
    ...actual,
    apiClient: {
      get: (path: string) => get(path),
      post: (path: string, body?: unknown) => post(path, body),
    },
  };
});

vi.mock("@/lib/finance-local-cache", async () => {
  const actual = await vi.importActual<typeof import("@/lib/finance-local-cache")>(
    "@/lib/finance-local-cache",
  );
  return {
    ...actual,
    clearFinanceLocalCaches: vi.fn(),
  };
});

function AuthProbe() {
  const { user, loading, authResolved } = useAuth();
  return (
    <div>
      <span data-testid="user">{user?.username ?? "none"}</span>
      <span data-testid="loading">{String(loading)}</span>
      <span data-testid="resolved">{String(authResolved)}</span>
    </div>
  );
}

function LoginProbe() {
  const { user, loading, authResolved, verifyMagicCode, logout } = useAuth();
  return (
    <div>
      <span data-testid="user">{user?.username ?? "none"}</span>
      <span data-testid="loading">{String(loading)}</span>
      <span data-testid="resolved">{String(authResolved)}</span>
      <button
        type="button"
        onClick={() => {
          void verifyMagicCode("rob@example.com", "123456").catch(() => undefined);
        }}
      >
        verify
      </button>
      <button
        type="button"
        onClick={() => {
          void logout();
        }}
      >
        logout
      </button>
    </div>
  );
}

describe("AuthProvider session bootstrap", () => {
  beforeEach(() => {
    get.mockReset();
    post.mockReset();
    window.localStorage.clear();
    window.sessionStorage.clear();
    vi.useFakeTimers({ shouldAdvanceTime: true });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("fail-safe stops loading without clearing a user set by magic-code verify", async () => {
    let resolveBootstrapMe: ((value: unknown) => void) | null = null;
    let meCalls = 0;
    get.mockImplementation((path: string) => {
      if (path === "/auth/me") {
        meCalls += 1;
        if (meCalls === 1) {
          return new Promise((resolve) => {
            resolveBootstrapMe = resolve;
          });
        }
        // Post-verify cookie confirmation.
        return Promise.resolve({
          user: { username: "rob", role: "admin" },
          csrf_token: "csrf-confirmed",
        });
      }
      if (path === "/auth/magic-code/status") {
        return Promise.resolve({ enabled: true, dev_delivery: false });
      }
      return Promise.reject(new Error(`unexpected GET ${path}`));
    });
    post.mockResolvedValue({
      user: { username: "rob", role: "admin" },
      csrf_token: "csrf-after-verify",
    });

    render(
      <AuthProvider>
        <LoginProbe />
      </AuthProvider>,
    );

    expect(screen.getByTestId("user")).toHaveTextContent("none");
    expect(screen.getByTestId("loading")).toHaveTextContent("true");

    await act(async () => {
      screen.getByRole("button", { name: "verify" }).click();
    });

    await waitFor(() => {
      expect(screen.getByTestId("user")).toHaveTextContent("rob");
      expect(screen.getByTestId("resolved")).toHaveTextContent("true");
    });
    expect(post).toHaveBeenCalledWith("/auth/magic-code/verify", {
      email: "rob@example.com",
      code: "123456",
      remember: true,
    });
    expect(meCalls).toBeGreaterThanOrEqual(2);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(10_000);
    });

    expect(screen.getByTestId("user")).toHaveTextContent("rob");
    expect(screen.getByTestId("loading")).toHaveTextContent("false");
    expect(screen.getByTestId("resolved")).toHaveTextContent("true");

    // Late bootstrap timeout must not wipe the verified session.
    await act(async () => {
      resolveBootstrapMe?.(Promise.reject(new ApiError("The server took too long to respond.", 504)));
    });
    await act(async () => {
      await Promise.resolve();
    });

    expect(screen.getByTestId("user")).toHaveTextContent("rob");
    expect(screen.getByTestId("resolved")).toHaveTextContent("true");
  });

  it("rejects magic-code verify when immediate /auth/me is 401 (cookie not stored)", async () => {
    get.mockImplementation((path: string) => {
      if (path === "/auth/me") {
        return Promise.reject(new ApiError("Not authenticated", 401));
      }
      if (path === "/auth/magic-code/status") {
        return Promise.resolve({ enabled: true, dev_delivery: false });
      }
      return Promise.reject(new Error(`unexpected GET ${path}`));
    });
    post.mockResolvedValue({
      user: { username: "rob", role: "admin" },
      csrf_token: "csrf-after-verify",
    });

    render(
      <AuthProvider>
        <LoginProbe />
      </AuthProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("resolved")).toHaveTextContent("true");
    });

    await act(async () => {
      screen.getByRole("button", { name: "verify" }).click();
    });

    await waitFor(() => {
      expect(screen.getByTestId("user")).toHaveTextContent("none");
    });
    expect(screen.getByTestId("resolved")).toHaveTextContent("true");
  });

  it("treats a slow /auth/me timeout as unresolved, not logout", async () => {
    get.mockImplementation((path: string) => {
      if (path === "/auth/me") {
        return Promise.reject(new ApiError("The server took too long to respond.", 504));
      }
      if (path === "/auth/magic-code/status") {
        return Promise.resolve({ enabled: true, dev_delivery: false });
      }
      return Promise.reject(new Error(`unexpected GET ${path}`));
    });

    render(
      <AuthProvider>
        <AuthProbe />
      </AuthProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("loading")).toHaveTextContent("false");
    });

    expect(screen.getByTestId("user")).toHaveTextContent("none");
    expect(screen.getByTestId("resolved")).toHaveTextContent("false");
  });

  it("resolves unauthenticated only on a real 401 from /auth/me", async () => {
    get.mockImplementation((path: string) => {
      if (path === "/auth/me") {
        return Promise.reject(new ApiError("Not authenticated", 401));
      }
      if (path === "/auth/magic-code/status") {
        return Promise.resolve({ enabled: true, dev_delivery: false });
      }
      return Promise.reject(new Error(`unexpected GET ${path}`));
    });

    render(
      <AuthProvider>
        <AuthProbe />
      </AuthProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("resolved")).toHaveTextContent("true");
    });
    expect(screen.getByTestId("user")).toHaveTextContent("none");
  });

  it("logout still clears the user immediately", async () => {
    get.mockImplementation((path: string) => {
      if (path === "/auth/me") {
        return Promise.resolve({
          user: { username: "rob", role: "admin" },
          csrf_token: "csrf",
        });
      }
      if (path === "/auth/magic-code/status") {
        return Promise.resolve({ enabled: true, dev_delivery: false });
      }
      return Promise.reject(new Error(`unexpected GET ${path}`));
    });
    post.mockResolvedValue(undefined);

    render(
      <AuthProvider>
        <LoginProbe />
      </AuthProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("user")).toHaveTextContent("rob");
    });

    await act(async () => {
      screen.getByRole("button", { name: "logout" }).click();
    });

    expect(screen.getByTestId("user")).toHaveTextContent("none");
    expect(screen.getByTestId("resolved")).toHaveTextContent("true");
  });

  it("paints immediately from localStorage session cache while cold /auth/me is pending", async () => {
    window.localStorage.setItem(
      FINANCE_LAST_SESSION_USER_KEY,
      JSON.stringify({ username: "rob", role: "admin" }),
    );
    let resolveMe: ((value: unknown) => void) | null = null;
    get.mockImplementation((path: string) => {
      if (path === "/auth/me") {
        return new Promise((resolve) => {
          resolveMe = resolve;
        });
      }
      if (path === "/auth/magic-code/status") {
        return Promise.resolve({ enabled: true, dev_delivery: false });
      }
      if (path === "/health") {
        return Promise.resolve({ status: "ok" });
      }
      return Promise.reject(new Error(`unexpected GET ${path}`));
    });

    render(
      <AuthProvider>
        <AuthProbe />
      </AuthProvider>,
    );

    expect(screen.getByTestId("user")).toHaveTextContent("rob");
    expect(screen.getByTestId("loading")).toHaveTextContent("false");
    expect(screen.getByTestId("resolved")).toHaveTextContent("false");

    await act(async () => {
      resolveMe?.({
        user: { username: "rob", role: "admin" },
        csrf_token: "csrf-live",
      });
    });
    await waitFor(() => {
      expect(screen.getByTestId("resolved")).toHaveTextContent("true");
    });
    expect(screen.getByTestId("user")).toHaveTextContent("rob");
  });

  it("migrates a legacy sessionStorage session user into localStorage", async () => {
    window.sessionStorage.setItem(
      FINANCE_LAST_SESSION_USER_KEY,
      JSON.stringify({ username: "rob", role: "admin" }),
    );
    get.mockImplementation((path: string) => {
      if (path === "/auth/me") {
        return Promise.resolve({
          user: { username: "rob", role: "admin" },
          csrf_token: "csrf",
        });
      }
      if (path === "/auth/magic-code/status") {
        return Promise.resolve({ enabled: true, dev_delivery: false });
      }
      if (path === "/health") {
        return Promise.resolve({ status: "ok" });
      }
      return Promise.reject(new Error(`unexpected GET ${path}`));
    });

    render(
      <AuthProvider>
        <AuthProbe />
      </AuthProvider>,
    );

    expect(screen.getByTestId("user")).toHaveTextContent("rob");
    expect(screen.getByTestId("loading")).toHaveTextContent("false");
    expect(window.localStorage.getItem(FINANCE_LAST_SESSION_USER_KEY)).toContain("rob");
    expect(window.sessionStorage.getItem(FINANCE_LAST_SESSION_USER_KEY)).toBeNull();
  });

  it("persists confirmed session user to localStorage for the next cold entry", async () => {
    get.mockImplementation((path: string) => {
      if (path === "/auth/me") {
        return Promise.resolve({
          user: { username: "rob", role: "admin" },
          csrf_token: "csrf",
        });
      }
      if (path === "/auth/magic-code/status") {
        return Promise.resolve({ enabled: true, dev_delivery: false });
      }
      if (path === "/health") {
        return Promise.resolve({ status: "ok" });
      }
      return Promise.reject(new Error(`unexpected GET ${path}`));
    });

    render(
      <AuthProvider>
        <AuthProbe />
      </AuthProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("resolved")).toHaveTextContent("true");
    });
    expect(JSON.parse(window.localStorage.getItem(FINANCE_LAST_SESSION_USER_KEY) ?? "{}")).toEqual({
      username: "rob",
      role: "admin",
    });
  });
});
