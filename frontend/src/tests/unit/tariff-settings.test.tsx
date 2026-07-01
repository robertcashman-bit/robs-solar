import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { TariffSettingsForm } from "@/components/settings/TariffSettingsForm";

const fullInitial = {
  import_rate: 0.28,
  export_rate: 0.15,
  currency: "GBP",
  standing_charge_gbp: 0.45,
  include_standing_charge: true,
  off_peak_start: "23:30",
  off_peak_end: "05:30",
  peak_start: "07:00",
  peak_end: "23:00",
  battery_capacity_kwh: 16.1,
  battery_minimum_reserve_pct: 20,
  maximum_charge_pct: 100,
  warning_import_threshold_w: 300,
  warning_battery_soc_threshold_pct: 90,
};

describe("TariffSettingsForm", () => {
  it("shows tariff fields", () => {
    render(
      <TariffSettingsForm
        initial={fullInitial}
        onSubmit={vi.fn()}
      />,
    );
    expect(screen.getByText("Electricity tariff")).toBeInTheDocument();
    expect(screen.getByLabelText(/^Import rate \(per kWh\)/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Daily standing charge/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Off-peak start/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Battery capacity/i)).toBeInTheDocument();
  });

  it("disables submit in read-only mode", () => {
    render(
      <TariffSettingsForm
        initial={fullInitial}
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
        initial={fullInitial}
        onSubmit={vi.fn()}
      />,
    );
    await user.click(screen.getByRole("button", { name: "Review change" }));
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });
});
