import type { AuditEntry } from "@/lib/schemas";

type AuditTableProps = {
  entries: AuditEntry[];
};

const outcomeStyles: Record<string, string> = {
  success: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300",
  failed: "bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300",
  rejected: "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300",
  validation_error: "bg-orange-100 text-orange-800 dark:bg-orange-900/40 dark:text-orange-300",
};

export function AuditTable({ entries }: AuditTableProps) {
  if (entries.length === 0) {
    return (
      <div className="solar-card text-[var(--muted)]">
        No audit entries yet.
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-2xl border border-[var(--border)] bg-[var(--surface-elevated)] backdrop-blur-sm">
      <table className="min-w-full text-left text-sm">
        <thead className="sticky top-0 bg-[var(--surface)] backdrop-blur-sm">
          <tr className="border-b border-[var(--border)]">
            <th className="px-4 py-3 font-semibold text-[var(--muted)]">Time</th>
            <th className="px-4 py-3 font-semibold text-[var(--muted)]">User</th>
            <th className="px-4 py-3 font-semibold text-[var(--muted)]">Action</th>
            <th className="px-4 py-3 font-semibold text-[var(--muted)]">Outcome</th>
            <th className="px-4 py-3 font-semibold text-[var(--muted)]">Details</th>
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
              <td className="px-4 py-3 whitespace-nowrap">
                {new Date(entry.timestamp).toLocaleString()}
              </td>
              <td className="px-4 py-3">
                {entry.username}{" "}
                <span className="text-[var(--muted)]">({entry.role})</span>
              </td>
              <td className="px-4 py-3 font-mono text-xs">{entry.action}</td>
              <td className="px-4 py-3">
                <span
                  className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-medium ${
                    outcomeStyles[entry.outcome] ?? "bg-zinc-100 text-zinc-700"
                  }`}
                >
                  {entry.outcome}
                </span>
              </td>
              <td className="px-4 py-3 text-[var(--muted)]">{entry.validation_result}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
