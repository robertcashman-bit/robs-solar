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
  usePathname: () => "/energy",
  useRouter: () => ({ push: vi.fn() }),
}));

describe("AppShell energy context", () => {
  it("shows energy branding on energy routes", () => {
    render(
      <AppShell>
        <p>Energy content</p>
      </AppShell>,
    );
    expect(screen.getByText("Energy & Solar")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Energy & Solar/i })).toHaveAttribute("href", "/energy");
    expect(screen.getByRole("link", { name: "Skip to main content" })).toHaveAttribute(
      "href",
      "#main-content",
    );
  });
});
