import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { EditableTouBands } from "@/components/scheduler/EditableTouBands";
import type { InverterSettings } from "@/lib/schemas";

const settings: InverterSettings = {
  inverter_sn: "2601315599",
  plant_id: "537603",
  plant_name: "Greenacre",
  plant_permissions: ["inverter.setting.edit"],
  write_allowed: true,
  write_denied_reason: "",
  sys_work_mode: "2",
  sys_work_mode_label: "Selling first",
  energy_mode: "1",
  solar_sell: true,
  export_limit_mode: "2",
  discharge_current_a: 205,
  bands: [
    { slot: 1, start: "00:00", end: "06:20", target_soc_pct: 100, grid_charge_enabled: true, power_w: 8000 },
    { slot: 2, start: "06:20", end: "11:00", target_soc_pct: 20, grid_charge_enabled: false, power_w: 9000 },
  ],
  active_band_slot: 1,
  active_band: null,
  diagnosis: "",
};

describe("EditableTouBands", () => {
  it("submits edited band values", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    render(<EditableTouBands settings={settings} onSubmit={onSubmit} />);

    const cap = screen.getByLabelText("Band 2 target SOC");
    fireEvent.change(cap, { target: { value: "35" } });

    await user.click(screen.getByRole("button", { name: /write to inverter/i }));
    await user.click(screen.getByRole("button", { name: "Write to inverter" }));

    await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(1));
    const bands = onSubmit.mock.calls[0][0];
    const band2 = bands.find((b: { slot: number }) => b.slot === 2);
    expect(band2.target_soc_pct).toBe(35);
  });

  it("disables inputs when disabled", () => {
    render(<EditableTouBands settings={settings} onSubmit={vi.fn()} disabled />);
    expect(screen.getByLabelText("Band 1 start time")).toBeDisabled();
  });

  it("blocks submit and shows an error for an invalid start time", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    render(<EditableTouBands settings={settings} onSubmit={onSubmit} />);

    fireEvent.change(screen.getByLabelText("Band 1 start time"), { target: { value: "" } });
    await user.click(screen.getByRole("button", { name: /write to inverter/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/HH:MM/i);
    expect(onSubmit).not.toHaveBeenCalled();
    expect(screen.queryByRole("button", { name: "Write to inverter" })).not.toBeInTheDocument();
  });

  it("reset restores the original band values", async () => {
    const user = userEvent.setup();
    render(<EditableTouBands settings={settings} onSubmit={vi.fn()} />);

    const cap = screen.getByLabelText("Band 2 target SOC") as HTMLInputElement;
    fireEvent.change(cap, { target: { value: "35" } });
    expect(cap.value).toBe("35");

    await user.click(screen.getByRole("button", { name: "Reset" }));
    expect((screen.getByLabelText("Band 2 target SOC") as HTMLInputElement).value).toBe("20");
  });

  it("success message warns about the Sunsynk read-back delay", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    render(<EditableTouBands settings={settings} onSubmit={onSubmit} />);

    await user.click(screen.getByRole("button", { name: /write to inverter/i }));
    await user.click(screen.getByRole("button", { name: "Write to inverter" }));

    await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(1));
    expect(await screen.findByRole("status")).toHaveTextContent(/up to a minute/i);
  });
});
