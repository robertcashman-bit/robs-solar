import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AuditTable } from "@/components/audit/AuditTable";

describe("AuditTable", () => {
  it("renders empty state", () => {
    render(<AuditTable entries={[]} />);
    expect(screen.getByText("No audit entries yet")).toBeInTheDocument();
  });

  it("renders audit rows", () => {
    render(
      <AuditTable
        entries={[
          {
            id: 1,
            timestamp: "2026-06-28T12:00:00Z",
            username: "admin",
            role: "admin",
            action: "set_export_limit",
            request_payload: { limit_w: 3000 },
            validation_result: "valid",
            adapter_response: '{"export_limit_w":3000}',
            outcome: "success",
          },
        ]}
      />,
    );
    expect(screen.getByText("set_export_limit")).toBeInTheDocument();
    expect(screen.getByText("success")).toBeInTheDocument();
  });
});
