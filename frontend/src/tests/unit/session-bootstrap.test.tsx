import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AuthProvider } from "@/lib/auth-context";
import { useRequireAuth } from "@/lib/use-require-auth";
import { AuthLoadingShell } from "@/components/shared/AuthLoadingShell";

const get = vi.fn();
const replace = vi.fn();

vi.mock("@/lib/api-client", () => ({
  apiClient: {
    get: (...args: unknown[]) => get(...args),
    post: vi.fn(),
  },
  setCsrfToken: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace }),
}));

function GateProbe() {
  const { gated, redirecting } = useRequireAuth();
  if (gated) {
    return <AuthLoadingShell redirecting={redirecting} />;
  }
  return <p>dashboard</p>;
}

describe("session bootstrap gate", () => {
  beforeEach(() => {
    get.mockReset();
    replace.mockReset();
  });

  it("does not stay on Loading session when /auth/me never resolves", async () => {
    get.mockImplementation(
      () =>
        new Promise(() => {
          // hung request — fail-safe in AuthProvider must clear loading
        }),
    );

    vi.useFakeTimers();
    render(
      <AuthProvider>
        <GateProbe />
      </AuthProvider>,
    );

    expect(screen.getByRole("status", { name: "Loading session" })).toBeInTheDocument();

    await vi.advanceTimersByTimeAsync(10000);
    await waitFor(() => {
      expect(screen.getByRole("status", { name: "Redirecting to sign in" })).toBeInTheDocument();
    });
    expect(replace).toHaveBeenCalledWith("/login");
    expect(screen.queryByText("Loading session…")).not.toBeInTheDocument();

    await vi.advanceTimersByTimeAsync(1500);
    vi.useRealTimers();
  });

  it("redirects to login after a finished unauthenticated bootstrap", async () => {
    get.mockImplementation(async (path: string) => {
      if (path === "/auth/me") {
        const err = Object.assign(new Error("Not authenticated"), { status: 401 });
        throw err;
      }
      if (path === "/auth/magic-code/status") {
        return {
          enabled: true,
          password_login_enabled: true,
          email_delivery_configured: false,
          dev_delivery: false,
        };
      }
      throw new Error(`unexpected ${path}`);
    });

    render(
      <AuthProvider>
        <GateProbe />
      </AuthProvider>,
    );

    await waitFor(() => {
      expect(screen.getByRole("status", { name: "Redirecting to sign in" })).toBeInTheDocument();
    });
    expect(replace).toHaveBeenCalledWith("/login");
  });
});
