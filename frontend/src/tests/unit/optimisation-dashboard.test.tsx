import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { OptimisationScoreCard } from "@/components/dashboard/OptimisationScoreCard";
import { WarningsPanel } from "@/components/dashboard/WarningsPanel";

describe("OptimisationScoreCard", () => {
  it("shows score out of 100", () => {
    render(
      <OptimisationScoreCard
        score={{
          total: 74,
          components: [],
          lost_points_reasons: ["You lost 6 points on battery discharge"],
          missed_saving_gbp: 1.05,
        }}
        currency="GBP"
      />,
    );
    expect(screen.getByText("74/100")).toBeInTheDocument();
  });
});

describe("WarningsPanel", () => {
  it("renders amber warning with severity styling", () => {
    render(
      <WarningsPanel
        statusHeadline="Warning — test"
        warnings={[
          {
            id: "peak_rate_import",
            severity: "amber",
            title: "Peak-rate import detected",
            message: "Importing during peak rate.",
            category: "import",
          },
        ]}
      />,
    );
    expect(screen.getByText("Peak-rate import detected")).toBeInTheDocument();
  });
});
