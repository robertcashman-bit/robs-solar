import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { MetricTile } from "@/components/finance/MetricTile";
import { MetricWithOfWhich, OfWhichBreakdown } from "@/components/finance/OfWhichBreakdown";

describe("OfWhichBreakdown", () => {
  it("renders nested of-which amounts under a parent tile", () => {
    render(
      <MetricWithOfWhich
        items={[
          { label: "Of which house mortgage (placeholder)", value: 175000 },
          { label: "Of which personal credit cards", value: 800 },
          { label: "Hidden zero", value: 0, hideIfZero: true },
        ]}
      >
        <MetricTile label="Personal debts" value={175800} warning />
      </MetricWithOfWhich>,
    );
    expect(screen.getByText("Personal debts")).toBeInTheDocument();
    expect(screen.getByLabelText("Of which breakdown")).toBeInTheDocument();
    expect(screen.getByText("Of which house mortgage (placeholder)")).toBeInTheDocument();
    expect(screen.getByText("£175,000.00")).toBeInTheDocument();
    expect(screen.getByText("Of which personal credit cards")).toBeInTheDocument();
    expect(screen.queryByText("Hidden zero")).not.toBeInTheDocument();
  });

  it("renders nothing when every row is empty", () => {
    const { container } = render(
      <OfWhichBreakdown items={[{ label: "Of which personal loans", value: null }]} />,
    );
    expect(container).toBeEmptyDOMElement();
  });
});
