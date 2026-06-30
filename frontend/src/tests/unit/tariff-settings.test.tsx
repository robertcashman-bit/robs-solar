import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { TariffSettingsForm } from "@/components/settings/TariffSettingsForm";

describe("TariffSettingsForm", () => {
  it("shows tariff fields", () => {
    render(
      <TariffSettingsForm
        initial={{ import_rate: 0.28, export_rate: 0.15, currency: "GBP" }}
        onSubmit={vi.fn()}
      />,
    );
    expect(screen.getByText("Electricity tariff")).toBeInTheDocument();
    expect(screen.getByLabelText(/Import rate/i)).toBeInTheDocument();
  });

  it("disables submit in read-only mode", () => {
    render(
      <TariffSettingsForm
        initial={{ import_rate: 0.28, export_rate: 0.15, currency: "GBP" }}
        readOnly
        onSubmit={vi.fn()}
      />,
    );
    expect(screen.queryByRole("button", { name: "Review change" })).not.toBeInTheDocument();
  });

  it("shows confirmation dialog", async () => {
    const user = userEvent.setup();
    render(
      <TariffSettingsForm
        initial={{ import_rate: 0.28, export_rate: 0.15, currency: "GBP" }}
        onSubmit={vi.fn()}
      />,
    );
    await user.click(screen.getByRole("button", { name: "Review change" }));
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });
});
