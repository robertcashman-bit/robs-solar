import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { LiveDataRequiredPanel } from "@/components/dashboard/LiveDataRequiredPanel";

describe("LiveDataRequiredPanel", () => {
  it("blocks the dashboard when simulator mode is active", () => {
    render(<LiveDataRequiredPanel adapterMode="simulator" />);
    expect(
      screen.getByRole("heading", { name: "Live inverter data required" }),
    ).toBeInTheDocument();
    expect(screen.getByText(/Simulated adapter mode is enabled \(simulator\)/)).toBeInTheDocument();
  });
});
