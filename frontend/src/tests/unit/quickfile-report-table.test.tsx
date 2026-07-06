import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { QuickFileReportTable } from "@/components/finance/QuickFileReportTable";

describe("QuickFileReportTable", () => {
  it("shows nominal codes with account names like QuickFile", () => {
    render(
      <QuickFileReportTable
        items={[
          { key: "h", label: "Turnover", sectionHeader: true },
          {
            key: "l1",
            label: "General Sales",
            nominalCode: "4000",
            indent: true,
            amount: 1000,
            role: "inflow",
          },
          { key: "t", label: "Turnover", amount: 1000, role: "inflow", total: true },
        ]}
      />,
    );

    expect(screen.getByText("4000 General Sales")).toBeInTheDocument();
    expect(screen.getAllByText("Turnover").length).toBeGreaterThanOrEqual(2);
    expect(screen.getAllByText("+£1,000.00").length).toBeGreaterThanOrEqual(1);
  });
});
