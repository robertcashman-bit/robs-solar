import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { BankConnectionCard } from "@/components/finance/BankConnectionCard";
import type { BankConnectionItem } from "@/lib/finance-schemas";

const baseConnection: BankConnectionItem = {
  id: "lloyds",
  label: "Lloyds",
  method: "open_banking",
  status: "not_connected",
  status_message: "Not connected. Log in via Connect banks to link this account.",
  last_sync_at: null,
  institution: "",
  account_count: 0,
  balance_gbp: 0,
};

describe("BankConnectionCard", () => {
  it("shows bank name, status, and connect button", () => {
    render(
      <BankConnectionCard
        connection={baseConnection}
        writable
        busy={false}
        onConnect={vi.fn()}
        onDisconnect={vi.fn()}
        onSync={vi.fn()}
      />,
    );
    expect(screen.getByText("Lloyds")).toBeInTheDocument();
    expect(screen.getByText("Not Connected")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Connect" })).toBeInTheDocument();
  });

  it("shows sync and disconnect when connected", () => {
    const connected: BankConnectionItem = {
      ...baseConnection,
      status: "connected",
      status_message: "Connected.",
      account_count: 1,
      balance_gbp: 1200,
    };
    render(
      <BankConnectionCard
        connection={connected}
        writable
        busy={false}
        onConnect={vi.fn()}
        onDisconnect={vi.fn()}
        onSync={vi.fn()}
      />,
    );
    expect(screen.getByText("Connected")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Sync now" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Disconnect" })).toBeInTheDocument();
  });

  it("hides disconnect for Lunch Flow-backed connections", () => {
    const connected: BankConnectionItem = {
      ...baseConnection,
      status: "connected",
      status_message: "Synced from Lunch Flow.",
      account_count: 1,
      balance_gbp: 1200,
    };
    render(
      <BankConnectionCard
        connection={connected}
        writable
        busy={false}
        personalProvider="lunch_flow"
        onConnect={vi.fn()}
        onDisconnect={vi.fn()}
        onSync={vi.fn()}
      />,
    );
    expect(screen.getByText("Lunch Flow")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Sync now" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Disconnect" })).not.toBeInTheDocument();
  });
});
