import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { MetricCard, MetricCardSkeleton } from "@/components/dashboard/MetricCard";

describe("MetricCard", () => {
  it("renders metric label and value", () => {
    render(<MetricCard label="PV generation" value="4,200 W" hint="Live" />);
    expect(screen.getByText("PV generation")).toBeInTheDocument();
    expect(screen.getByText("4,200 W")).toBeInTheDocument();
    expect(screen.getByText("Live")).toBeInTheDocument();
  });

  it("renders loading skeleton", () => {
    render(<MetricCardSkeleton />);
    expect(document.querySelector(".solar-skeleton")).toBeTruthy();
  });
});
