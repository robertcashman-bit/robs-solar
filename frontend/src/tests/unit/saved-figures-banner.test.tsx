import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { SavedFiguresBanner } from "@/components/finance/SavedFiguresBanner";

describe("SavedFiguresBanner", () => {
  it("labels cached overview as possibly stale", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-08-17T12:30:00Z"));
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
    expect(screen.getByText(/QuickFile \(Defence Legal books\)/i)).toBeInTheDocument();
    expect(screen.getByText(/Lunch Flow \(personal banks\)/i)).toBeInTheDocument();
    vi.useRealTimers();
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
