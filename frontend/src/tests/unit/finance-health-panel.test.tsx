import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { FinanceHealthPanel } from "@/components/finance/FinanceHealthPanel";

vi.mock("@/lib/api-client", () => ({
  apiClient: {
    get: vi.fn(async (path: string) => {
      if (path === "/finance/health" || path.startsWith("/finance/health?")) {
        return {
          ok: true,
          db_read: true,
          light: true,
          data_source: "finance",
          database_backend: "sqlite",
          ephemeral_database: true,
          web_backup_configured: false,
          finance_bank_reads_ready: true,
          needs_review: true,
          integrations: {
            quickfile: {
              configured: true,
            },
            lunchflow: {
              configured: true,
            },
          },
        };
      }
      return {};
    }),
    post: vi.fn(),
  },
}));

describe("FinanceHealthPanel", () => {
  it("shows persistence warning and self-heal action", async () => {
    render(<FinanceHealthPanel canEdit />);
    expect(await screen.findByText("Finance health")).toBeInTheDocument();
    expect(await screen.findByText(/wiped on deploy/i)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Self-heal caches" }),
    ).toBeInTheDocument();
    // Light health omits import/backup facts — do not fabricate "none yet".
    expect(
      screen.queryByText(/none yet — tap Backup now/i),
    ).not.toBeInTheDocument();
    expect(screen.queryByText(/Last import:/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/last sync/i)).not.toBeInTheDocument();
    expect(screen.getByText(/Database: sqlite read ok/i)).toBeInTheDocument();
    expect(screen.getByText(/Data source: finance/i)).toBeInTheDocument();
    expect(screen.getByText(/QuickFile: configured/i)).toBeInTheDocument();
    expect(screen.getByText(/Lunch Flow: configured/i)).toBeInTheDocument();
    expect(screen.queryByText(/TrueLayer/i)).not.toBeInTheDocument();
    expect(
      screen.getByText(/do not mean bank balances are simulated/i),
    ).toBeInTheDocument();
  });
});
