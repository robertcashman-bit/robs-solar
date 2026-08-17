import { render, screen, waitFor, act } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AuthLoadingShell } from "@/components/shared/AuthLoadingShell";
import { useRequireAuth } from "@/lib/use-require-auth";

const replace = vi.fn();
let authState = {
  user: null as null | { username: string; role: "admin" | "viewer" },
  loading: true,
};

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace }),
}));

vi.mock("@/lib/auth-context", () => ({
  useAuth: () => authState,
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
    replace.mockReset();
    authState = { user: null, loading: true };
    vi.stubGlobal("location", {
      ...window.location,
      pathname: "/",
      replace: vi.fn(),
    });
  });

  it("shows Loading session only while auth is unresolved", () => {
    render(<GateProbe />);
    expect(screen.getByRole("status", { name: "Loading session" })).toBeInTheDocument();
    expect(replace).not.toHaveBeenCalled();
  });

  it("leaves Loading session and redirects when there is no session", async () => {
    const { rerender } = render(<GateProbe />);
    expect(screen.getByRole("status", { name: "Loading session" })).toBeInTheDocument();

    authState = { user: null, loading: false };
    rerender(<GateProbe />);

    expect(screen.getByRole("status", { name: "Redirecting to sign in" })).toBeInTheDocument();
    expect(screen.queryByRole("status", { name: "Loading session" })).not.toBeInTheDocument();
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/login"));

    await act(async () => {
      await new Promise((r) => setTimeout(r, 1600));
    });
    expect(window.location.replace).toHaveBeenCalledWith("/login");
  });

  it("shows the dashboard once a session exists", () => {
    authState = { user: { username: "rob", role: "admin" }, loading: false };
    render(<GateProbe />);
    expect(screen.getByText("dashboard")).toBeInTheDocument();
    expect(replace).not.toHaveBeenCalled();
  });
});
