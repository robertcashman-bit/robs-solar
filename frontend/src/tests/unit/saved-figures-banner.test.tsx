import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { SavedFiguresBanner } from "@/components/finance/SavedFiguresBanner";

describe("SavedFiguresBanner", () => {
  it("labels cached overview as possibly stale", () => {
    render(
      <SavedFiguresBanner
        refreshing={false}
        generatedAt="2026-08-17T12:00:00Z"
        cached
        quickfileSyncedAt="2026-08-17T11:00:00Z"
        lunchflowSyncedAt="2026-08-17T11:05:00Z"
      />,
    );
    expect(screen.getByText(/may be stale until live sync finishes/i)).toBeInTheDocument();
    expect(screen.getByText(/QuickFile synced/i)).toBeInTheDocument();
    expect(screen.getByText(/Lunch Flow synced/i)).toBeInTheDocument();
  });

  it("labels fresh overview as live", () => {
    render(
      <SavedFiguresBanner
        refreshing={false}
        generatedAt="2026-08-17T12:00:00Z"
        cached={false}
      />,
    );
    expect(screen.getByText(/live overview/i)).toBeInTheDocument();
  });
});
