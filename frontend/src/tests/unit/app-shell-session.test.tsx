import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AppShell } from "@/components/shared/AppShell";

let authState = {
  user: null as null | { username: string; role: "admin" | "viewer" },
  loading: true,
  logout: vi.fn(),
};

vi.mock("next/navigation", () => ({
  usePathname: () => "/",
}));

vi.mock("next/link", () => ({
  default: ({
    children,
    href,
    ...props
  }: {
    children: React.ReactNode;
    href: string;
  } & React.AnchorHTMLAttributes<HTMLAnchorElement>) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

vi.mock("@/lib/auth-context", () => ({
  useAuth: () => authState,
}));

describe("AppShell session gate", () => {
  beforeEach(() => {
    authState = { user: null, loading: true, logout: vi.fn() };
  });

  it("shows Loading session only when auth is loading and there is no user", () => {
    render(
      <AppShell>
        <p>dashboard body</p>
      </AppShell>,
    );
    expect(screen.getByRole("status", { name: "Loading session" })).toBeInTheDocument();
    expect(screen.queryByText("dashboard body")).not.toBeInTheDocument();
  });

  it("paints children from a cached session user while /auth/me is still loading", () => {
    authState = {
      user: { username: "rob", role: "admin" },
      loading: true,
      logout: vi.fn(),
    };
    render(
      <AppShell>
        <p>dashboard body</p>
      </AppShell>,
    );
    expect(screen.getByText("dashboard body")).toBeInTheDocument();
    expect(screen.queryByRole("status", { name: "Loading session" })).not.toBeInTheDocument();
    expect(screen.getByText("rob")).toBeInTheDocument();
  });
});
