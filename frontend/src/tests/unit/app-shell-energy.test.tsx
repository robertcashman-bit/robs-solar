import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AppShell } from "@/components/shared/AppShell";

vi.mock("@/lib/auth-context", () => ({
  useAuth: () => ({
    user: { username: "admin", role: "admin" },
    loading: false,
    logout: vi.fn(),
  }),
}));

vi.mock("next/navigation", () => ({
  usePathname: () => "/",
  useRouter: () => ({ push: vi.fn() }),
}));

describe("AppShell finance navigation", () => {
  it("stays on the finance dashboard and hides Energy / Solar", () => {
    render(
      <AppShell>
        <p>Finance content</p>
      </AppShell>,
    );
    expect(screen.getByText("Finance Dashboard")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Energy" })).not.toBeInTheDocument();
    expect(screen.queryByText("Energy & Solar")).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Skip to main content" })).toHaveAttribute(
      "href",
      "#main-content",
    );
  });
});
