import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import SettingsPage from "@/app/settings/page";

vi.mock("@/lib/auth-context", () => ({
  useAuth: () => ({
    user: { username: "admin", role: "admin" },
    loading: false,
    magicCodeEnabled: true,
    magicCodeDevDelivery: false,
  }),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn() }),
  usePathname: () => "/settings",
}));

vi.mock("@/components/settings/FinanceSettingsPanel", () => ({
  FinanceSettingsPanel: () => <div>Finance integrations panel</div>,
}));

vi.mock("@/lib/api-client", () => ({
  apiClient: {
    get: vi.fn(async () => ({})),
  },
}));

describe("SettingsPage", () => {
  beforeEach(() => {
    window.history.pushState({}, "", "/settings");
    window.sessionStorage.clear();
  });

  it("shows finance settings only and hides the Energy tab", async () => {
    render(<SettingsPage />);
    expect(
      await screen.findByText(
        "Finance integrations, banking connections, and account preferences.",
      ),
    ).toBeInTheDocument();
    expect(screen.getByText("Finance integrations panel")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Energy / Solar" })).not.toBeInTheDocument();
    expect(screen.queryByText("Energy settings panel")).not.toBeInTheDocument();
    expect(screen.queryByText(/Sunsynk/i)).not.toBeInTheDocument();
  });

  it("shows a success banner after bank login import", async () => {
    window.history.pushState({}, "", "/settings?imported=1");
    render(<SettingsPage />);
    expect(
      await screen.findByText(
        "Bank login complete. Accounts, cards, and Funding Circle payments have been pulled in.",
      ),
    ).toBeInTheDocument();
  });
});
