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

describe("ConnectBanksPage", () => {
  it("renders the recovered bank connection sections", () => {
    render(<ConnectBanksPage />);
    expect(screen.getByRole("heading", { name: "Connect banks" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Open Banking" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Lunch Flow" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "QuickFile" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Funding Circle" })).toBeInTheDocument();
    expect(screen.getByText("TrueLayer panel")).toBeInTheDocument();
  });
});
