import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { DispatchWindows } from "@/components/scheduler/DispatchWindows";

const dispatches = {
  off_peak_window: { start: "23:30", end: "05:30" },
  planned: [
    {
      start: "2026-06-30T12:00:00+00:00",
      end: "2026-06-30T13:00:00+00:00",
      source: "smart",
      delta_kwh: 5,
    },
  ],
  completed: [],
  tariff_family: "IOG",
};

describe("DispatchWindows", () => {
  it("shows off-peak window and planned dispatch", () => {
    render(<DispatchWindows dispatches={dispatches} />);
    expect(screen.getByText(/23:30 – 05:30/)).toBeInTheDocument();
    expect(screen.getByText(/Upcoming dispatches/i)).toBeInTheDocument();
  });
});
