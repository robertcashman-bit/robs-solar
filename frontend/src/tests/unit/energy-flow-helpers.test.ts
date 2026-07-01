import { describe, expect, it } from "vitest";

import { gridDisplayState, gridHeroLabel } from "@/lib/energy-flow";

describe("energy-flow helpers", () => {
  it("gridDisplayState shows small import above noise floor", () => {
    const state = gridDisplayState({ grid_import_w: 13, grid_export_w: 0 });
    expect(state.value).toBe("13 W");
    expect(state.sublabel).toBe("Importing");
    expect(state.importing).toBe(true);
    expect(state.importAnimating).toBe(false);
  });

  it("gridHeroLabel shows small import instead of grid idle", () => {
    const label = gridHeroLabel({ grid_import_w: 13, grid_export_w: 0 });
    expect(label.text).toBe("Import 13 W");
    expect(label.tone).toBe("import");
  });

  it("gridDisplayState treats sub-noise grid as idle", () => {
    const state = gridDisplayState({ grid_import_w: 3, grid_export_w: 0 });
    expect(state.value).toBe("0 W");
    expect(state.sublabel).toBe("Idle");
  });
});
