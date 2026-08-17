import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import SettingsPage from "@/app/settings/page";

vi.mock("@/lib/auth-context", () => ({
  useAuth: () => ({
    user: { username: "admin", role: "admin" },
    loading: false,
  }),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn() }),
  usePathname: () => "/settings",
}));

vi.mock("@/components/settings/FinanceSettingsPanel", () => ({
  FinanceSettingsPanel: () => <div>Finance integrations</div>,
}));

describe("SettingsPage", () => {
  it("shows finance settings only", () => {
    render(<SettingsPage />);
    expect(screen.getByRole("heading", { name: "Settings" })).toBeInTheDocument();
    expect(screen.getByText("Finance integrations")).toBeInTheDocument();
    expect(screen.queryByRole("tab", { name: "Energy / Solar" })).not.toBeInTheDocument();
  });
});
