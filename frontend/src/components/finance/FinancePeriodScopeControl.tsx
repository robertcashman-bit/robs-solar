"use client";

import {
  FINANCE_PERIOD_KEYS,
  FINANCE_PERIOD_LABELS,
  type FinancePeriodKey,
  type FinancePeriodScope,
  periodLabel,
} from "@/lib/finance-period";

type FinancePeriodScopeControlProps = {
  period: FinancePeriodKey;
  onPeriodChange: (period: FinancePeriodKey) => void;
  scope?: FinancePeriodScope;
  onScopeChange?: (scope: FinancePeriodScope) => void;
  /** Optional second row for Overview dual personal/business periods. */
  personalPeriod?: FinancePeriodKey;
  businessPeriod?: FinancePeriodKey;
  onPersonalPeriodChange?: (period: FinancePeriodKey) => void;
  onBusinessPeriodChange?: (period: FinancePeriodKey) => void;
  dualPeriod?: boolean;
  showScope?: boolean;
  scopeOptions?: FinancePeriodScope[];
  className?: string;
  coverageNote?: string | null;
};

function ChipRow({
  label,
  value,
  onChange,
}: {
  label?: string;
  value: FinancePeriodKey;
  onChange: (period: FinancePeriodKey) => void;
}) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      {label ? (
        <span className="text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">
          {label}
        </span>
      ) : null}
      <div className="flex flex-wrap gap-1 rounded-lg border border-[var(--border)] p-1">
        {FINANCE_PERIOD_KEYS.map((key) => (
          <button
            key={key}
            type="button"
            aria-pressed={value === key}
            className={`rounded-md px-3 py-1 text-sm ${
              value === key ? "bg-emerald-600 text-white" : "text-[var(--muted)]"
            }`}
            onClick={() => onChange(key)}
          >
            {FINANCE_PERIOD_LABELS[key]}
          </button>
        ))}
      </div>
    </div>
  );
}

export function FinancePeriodScopeControl({
  period,
  onPeriodChange,
  scope = "personal",
  onScopeChange,
  personalPeriod,
  businessPeriod,
  onPersonalPeriodChange,
  onBusinessPeriodChange,
  dualPeriod = false,
  showScope = true,
  scopeOptions = ["personal", "business", "both"],
  className,
  coverageNote,
}: FinancePeriodScopeControlProps) {
  return (
    <section
      className={className ?? "space-y-3"}
      aria-label="Historical period"
    >
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold">Historical period</h2>
          <p className="mt-0.5 text-xs text-[var(--muted)]">
            Look back over stored transactions. Point-in-time balances stay current.
          </p>
        </div>
        {showScope && onScopeChange ? (
          <div className="flex gap-1 rounded-lg border border-[var(--border)] p-1">
            {scopeOptions.map((item) => (
              <button
                key={item}
                type="button"
                aria-pressed={scope === item}
                className={`rounded-md px-3 py-1 text-sm capitalize ${
                  scope === item ? "bg-emerald-600 text-white" : "text-[var(--muted)]"
                }`}
                onClick={() => onScopeChange(item)}
              >
                {item}
              </button>
            ))}
          </div>
        ) : null}
      </div>
      {dualPeriod && onPersonalPeriodChange && onBusinessPeriodChange ? (
        <div className="space-y-2">
          <ChipRow
            label="Personal"
            value={personalPeriod ?? period}
            onChange={onPersonalPeriodChange}
          />
          <ChipRow
            label="Business"
            value={businessPeriod ?? period}
            onChange={onBusinessPeriodChange}
          />
        </div>
      ) : (
        <ChipRow value={period} onChange={onPeriodChange} />
      )}
      {coverageNote ? (
        <p className="text-xs text-amber-800 dark:text-amber-200">{coverageNote}</p>
      ) : (
        <p className="text-xs text-[var(--muted)]">
          Selected: {periodLabel(dualPeriod ? (personalPeriod ?? period) : period)}
          {dualPeriod ? ` personal · ${periodLabel(businessPeriod ?? period)} business` : ""}
        </p>
      )}
    </section>
  );
}
