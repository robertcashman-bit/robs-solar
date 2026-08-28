import { MetricTile } from "@/components/finance/MetricTile";
import { OfWhichBreakdown } from "@/components/finance/OfWhichBreakdown";
import { MORTGAGE_HINT, round2 } from "@/lib/finance-debt-groups";
import { COMPANY_NAME, PERSONAL_NAME } from "@/lib/finance-branding";
import { formatGbp } from "@/lib/money";

export type DebtStackLines = {
  creditCardsGbp: number;
  loansGbp: number;
  mortgageGbp?: number;
  overdraftGbp: number;
  registerDebtGbp: number;
  mortgageConfigured?: boolean;
};

type DlaSide = {
  directorOwesCompanyGbp: number;
  companyOwesDirectorGbp: number;
};

type DebtStackPanelProps = {
  scope: "personal" | "business";
  lines: DebtStackLines;
  dla: DlaSide;
  className?: string;
};

export function debtStackTotal(lines: DebtStackLines): number {
  return round2(lines.registerDebtGbp + lines.overdraftGbp);
}

export function DebtStackPanel({ scope, lines, dla, className }: DebtStackPanelProps) {
  const isPersonal = scope === "personal";
  const total = debtStackTotal(lines);
  const tone = isPersonal
    ? "text-emerald-700 dark:text-emerald-400"
    : "text-teal-700 dark:text-teal-400";
  const title = isPersonal ? PERSONAL_NAME : COMPANY_NAME;
  const eyebrow = isPersonal ? "Personal debt stack" : "Business debt stack";

  const ofWhich = isPersonal
    ? [
        {
          label: "Personal credit cards",
          value: lines.creditCardsGbp > 0 ? lines.creditCardsGbp : null,
        },
        {
          label: "Personal loans",
          value: lines.loansGbp > 0 ? lines.loansGbp : null,
        },
        {
          label: "House mortgage",
          value:
            lines.mortgageConfigured === false
              ? null
              : (lines.mortgageGbp ?? 0) > 0
                ? lines.mortgageGbp
                : null,
          hint:
            lines.mortgageConfigured === false
              ? "Add a mortgage to track this"
              : MORTGAGE_HINT,
        },
        {
          label: "Personal overdraft",
          value: lines.overdraftGbp > 0 ? lines.overdraftGbp : null,
          hint: "Also reflected in the personal bank tile (net of overdraft)",
        },
      ]
    : [
        {
          label: "Business credit cards",
          value: lines.creditCardsGbp > 0 ? lines.creditCardsGbp : null,
        },
        {
          label: "Business loans",
          value: lines.loansGbp > 0 ? lines.loansGbp : null,
        },
        {
          label: "Business overdraft",
          value: lines.overdraftGbp > 0 ? lines.overdraftGbp : null,
          hint: "Also reflected in the business bank tile (net of overdraft)",
        },
      ];

  const dlaLabel =
    dla.directorOwesCompanyGbp > 0
      ? "Robert owes the company"
      : dla.companyOwesDirectorGbp > 0
        ? "Company owes Robert"
        : "Director's loan";
  const dlaValue =
    dla.directorOwesCompanyGbp > 0
      ? dla.directorOwesCompanyGbp
      : dla.companyOwesDirectorGbp > 0
        ? dla.companyOwesDirectorGbp
        : 0;
  const dlaHint =
    dla.directorOwesCompanyGbp > 0
      ? "Internal IOU — not a lender to repay. Cancels in combined net worth."
      : dla.companyOwesDirectorGbp > 0
        ? "Internal IOU — company owes Robert. Not external debt. Cancels in combined."
        : "Internal Robert ↔ company. Excluded from this stack total.";

  return (
    <div
      className={`rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-4 sm:p-5 ${className ?? ""}`}
      aria-label={eyebrow}
    >
      <p className={`text-[0.65rem] font-bold uppercase tracking-[0.14em] ${tone}`}>{eyebrow}</p>
      <h3 className="mt-1 text-lg font-semibold">{title}</h3>
      <p className="mt-1 text-xs text-[var(--muted)]">
        External debts only. Director&apos;s loan is separate below — never a third pile.
      </p>
      <div className="mt-4">
        <MetricTile
          label={isPersonal ? "Personal external debt" : "Business external debt"}
          value={total}
          warning={total > 0}
          hint={
            lines.overdraftGbp > 0
              ? `Register ${formatGbp(lines.registerDebtGbp)} + overdraft ${formatGbp(lines.overdraftGbp)}`
              : "Cards, loans, and mortgage from the register"
          }
        />
        <OfWhichBreakdown
          ariaLabel={`${eyebrow} groups`}
          items={ofWhich}
        />
      </div>
      {dlaValue > 0 ? (
        <div className="mt-4">
          <MetricTile
            label={dlaLabel}
            value={dlaValue}
            positive={dla.companyOwesDirectorGbp > 0}
            warning={dla.directorOwesCompanyGbp > 0}
            hint={dlaHint}
          />
        </div>
      ) : null}
    </div>
  );
}
