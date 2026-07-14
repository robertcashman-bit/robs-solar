import type { AuditEntry } from "@/lib/schemas";

import { EmptyState } from "@/components/shared/EmptyState";
import { PageLoading } from "@/components/shared/PageLoading";
import { StatusBadge } from "@/components/shared/StatusBadge";

type AuditTableProps = {
  entries: AuditEntry[];
  loading?: boolean;
};

const outcomeTone: Record<string, "positive" | "negative" | "warning" | "neutral"> = {
  success: "positive",
  failed: "negative",
  rejected: "warning",
  validation_error: "warning",
};

export function AuditTable({ entries, loading = false }: AuditTableProps) {
  if (loading) {
    return <PageLoading label="Loading audit log" rows={2} />;
  }

  if (entries.length === 0) {
    return (
      <EmptyState
        title="No audit entries yet"
        description="Control actions attempted on your inverter will be recorded here for review."
      />
    );
  }

  return (
    <div className="overflow-x-auto rounded-2xl border border-[var(--border)] bg-[var(--surface-elevated)] backdrop-blur-sm">
      <table className="min-w-full text-left text-sm">
        <caption className="sr-only">Control action audit log</caption>
        <thead className="sticky top-0 bg-[var(--surface)] backdrop-blur-sm">
          <tr className="border-b border-[var(--border)]">
            <th scope="col" className="px-4 py-3 font-semibold text-[var(--muted)]">
              Time
            </th>
            <th scope="col" className="px-4 py-3 font-semibold text-[var(--muted)]">
              User
            </th>
            <th scope="col" className="px-4 py-3 font-semibold text-[var(--muted)]">
              Action
            </th>
            <th scope="col" className="px-4 py-3 font-semibold text-[var(--muted)]">
              Outcome
            </th>
            <th scope="col" className="hidden px-4 py-3 font-semibold text-[var(--muted)] md:table-cell">
              Details
            </th>
          </tr>
        </thead>
        <tbody>
          {entries.map((entry, index) => (
            <tr
              key={entry.id}
              className={`border-t border-[var(--border)] ${
                index % 2 === 0 ? "bg-transparent" : "bg-[var(--surface)]/50"
              }`}
            >
              <td className="whitespace-nowrap px-4 py-3">
                <time dateTime={entry.timestamp}>
                  {new Date(entry.timestamp).toLocaleString()}
                </time>
              </td>
              <td className="px-4 py-3">
                {entry.username}{" "}
                <span className="text-[var(--muted)]">({entry.role})</span>
              </td>
              <td className="px-4 py-3 font-mono text-xs">{entry.action}</td>
              <td className="px-4 py-3">
                <StatusBadge
                  label={entry.outcome}
                  tone={outcomeTone[entry.outcome] ?? "neutral"}
                  showDot={false}
                />
              </td>
              <td className="hidden px-4 py-3 text-[var(--muted)] md:table-cell">
                {entry.validation_result || "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
