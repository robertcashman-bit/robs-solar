import { act, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AuthProvider, useAuth } from "@/lib/auth-context";
import { ApiError } from "@/lib/api-client";

const get = vi.fn();
const post = vi.fn();

vi.mock("@/lib/api-client", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api-client")>("@/lib/api-client");
  return {
    ...actual,
    apiClient: {
      get: (...args: unknown[]) => get(...args),
      post: (...args: unknown[]) => post(...args),
    },
  };
});

vi.mock("@/lib/finance-local-cache", () => ({
  clearFinanceLocalCaches: vi.fn(),
}));

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
          void verifyMagicCode("rob@example.com", "123456");
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
    vi.useFakeTimers({ shouldAdvanceTime: true });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("fail-safe stops loading without clearing a user set by magic-code verify", async () => {
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

    await act(async () => {
      await vi.advanceTimersByTimeAsync(10_000);
    });

    expect(screen.getByTestId("user")).toHaveTextContent("rob");
    expect(screen.getByTestId("loading")).toHaveTextContent("false");
    expect(screen.getByTestId("resolved")).toHaveTextContent("true");

    // Late bootstrap timeout must not wipe the verified session.
    await act(async () => {
      resolveMe?.(Promise.reject(new ApiError("The server took too long to respond.", 504)));
    });
    // The mock returns a Promise that rejects — settle microtasks.
    await act(async () => {
      await Promise.resolve();
    });

    expect(screen.getByTestId("user")).toHaveTextContent("rob");
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
});
