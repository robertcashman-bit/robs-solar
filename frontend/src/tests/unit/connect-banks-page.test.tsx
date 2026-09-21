import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import ConnectBanksPage from "@/app/(finance)/finance/connect/page";

vi.mock("@/lib/auth-context", () => ({
  useAuth: () => ({
    user: { username: "admin", role: "admin" },
    loading: false,
    authResolved: true,
  }),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn() }),
  usePathname: () => "/finance/connect",
}));

vi.mock("@/lib/use-connection-statuses", () => ({
  useConnectionStatuses: () => ({
    statuses: null,
    error: null,
    loading: false,
    reload: async () => undefined,
  }),
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

vi.mock("@/components/finance/FinanceHealthPanel", () => ({
  FinanceHealthPanel: () => <div>Finance health panel</div>,
}));

describe("ConnectBanksPage", () => {
  it("renders Lunch Flow and QuickFile without TrueLayer", () => {
    render(<ConnectBanksPage />);
    expect(screen.getByRole("heading", { name: "Connections" })).toBeInTheDocument();
    expect(screen.getByText("Finance health panel")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Open Banking" })).not.toBeInTheDocument();
    expect(screen.queryByText(/TrueLayer/i)).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Lunch Flow" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "QuickFile" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Funding Circle" })).toBeInTheDocument();
  });
});
