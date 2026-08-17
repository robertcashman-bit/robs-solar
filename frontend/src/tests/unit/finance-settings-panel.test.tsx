import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { FinanceSettingsPanel } from "@/components/settings/FinanceSettingsPanel";
import { apiClient } from "@/lib/api-client";

vi.mock("@/lib/auth-context", () => ({
  useAuth: () => ({
    user: { username: "admin", role: "admin" },
    loading: false,
  }),
}));

vi.mock("@/lib/api-client", () => ({
  apiClient: {
    get: vi.fn(),
    put: vi.fn(),
    post: vi.fn(),
  },
}));

vi.mock("@/components/settings/AppShortcutPanel", () => ({
  AppShortcutPanel: () => <div>App shortcut</div>,
}));

vi.mock("@/components/finance/BankImportCard", () => ({
  BankImportCard: () => <div>Bank import</div>,
}));

vi.mock("@/components/settings/OpenBankingSettingsPanel", () => ({
  OpenBankingSettingsPanel: () => <div>TrueLayer panel</div>,
}));

vi.mock("@/components/settings/LunchFlowSettingsPanel", () => ({
  LunchFlowSettingsPanel: () => <div>Lunch Flow panel</div>,
}));

vi.mock("@/components/settings/FundingCircleSettingsPanel", () => ({
  FundingCircleSettingsPanel: () => <div>Funding Circle panel</div>,
}));

vi.mock("@/components/settings/QuickFileSettingsPanel", () => ({
  QuickFileSettingsPanel: () => <div>QuickFile panel</div>,
}));

describe("FinanceSettingsPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(apiClient.get).mockImplementation(async (path: string) => {
      if (path === "/finance/integrations") {
        return [
          { id: "manual", label: "Manual entry", status: "active" },
          { id: "quickfile", label: "QuickFile", status: "inactive" },
          { id: "lunchflow", label: "Lunch Flow", status: "inactive" },
          { id: "open_banking", label: "Open Banking", status: "inactive" },
          { id: "funding_circle", label: "Funding Circle", status: "inactive" },
        ];
      }
      if (path === "/auth/oidc/status") {
        return { enabled: false };
      }
      return {};
    });
  });

  it("shows leftover connection copy without Energy", async () => {
    render(<FinanceSettingsPanel />);
    expect(await screen.findByText("What's connected")).toBeInTheDocument();
    expect(screen.getByText(/Destinations/)).toBeInTheDocument();
    expect(screen.getByText(/Connect Personal Finance/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Connect banks" })).toHaveAttribute(
      "href",
      "/finance/connect",
    );
    expect(screen.queryByText(/connect-personal-finance\.sh/)).not.toBeInTheDocument();
    expect(screen.getAllByText(/TrueLayer/).length).toBeGreaterThan(0);
    expect(screen.getByText(/Not connected —/)).toBeInTheDocument();
    expect(screen.queryByText(/Octopus/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Energy →/)).not.toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText(/QuickFile, Lunch Flow, TrueLayer Open Banking/)).toBeInTheDocument();
    });
  });
});
