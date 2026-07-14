import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AuditTable } from "@/components/audit/AuditTable";
import { EmptyState } from "@/components/shared/EmptyState";
import { InfoBanner } from "@/components/shared/InfoBanner";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { PageLoading } from "@/components/shared/PageLoading";

describe("AuditTable", () => {
  it("renders empty state", () => {
    render(<AuditTable entries={[]} />);
    expect(screen.getByText("No audit entries yet")).toBeInTheDocument();
  });

  it("renders loading state", () => {
    render(<AuditTable entries={[]} loading />);
    expect(screen.getByLabelText("Loading audit log")).toBeInTheDocument();
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

describe("EmptyState", () => {
  it("renders title and description", () => {
    render(<EmptyState title="Nothing here" description="Try adding a record." />);
    expect(screen.getByRole("status", { name: "Nothing here" })).toBeInTheDocument();
    expect(screen.getByText("Try adding a record.")).toBeInTheDocument();
  });
});

describe("InfoBanner", () => {
  it("renders status message", () => {
    render(<InfoBanner>System is in read-only mode.</InfoBanner>);
    expect(screen.getByRole("status")).toHaveTextContent("read-only mode");
  });
});

describe("StatusBadge", () => {
  it("renders label text for accessibility", () => {
    render(<StatusBadge label="Live writes on" tone="positive" />);
    expect(screen.getByText("Live writes on")).toBeInTheDocument();
  });
});

describe("PageLoading", () => {
  it("renders skeleton with accessible label", () => {
    render(<PageLoading label="Loading alerts" rows={1} />);
    expect(screen.getByLabelText("Loading alerts")).toBeInTheDocument();
  });
});
