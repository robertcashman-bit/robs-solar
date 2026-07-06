import { buildBusinessAccountSections } from "@/components/finance/business-account-statement";
import { FinanceItemList } from "@/components/finance/FinanceItemList";
import { QuickFileStatements } from "@/components/finance/QuickFileStatements";
import type { FinanceAccount, QuickFileReports } from "@/lib/finance-schemas";

type QuickFileFallbackPl = {
  turnover_gbp: number;
  expenses_gbp: number;
  net_profit_gbp: number;
};

type BusinessFinanceViewProps = {
  accounts: FinanceAccount[];
  quickfileReports?: QuickFileReports | null;
  fallbackPl?: QuickFileFallbackPl;
};

export function BusinessFinanceView({
  accounts,
  quickfileReports,
  fallbackPl,
}: BusinessFinanceViewProps) {
  const sections = buildBusinessAccountSections(accounts);

  return (
    <div className="space-y-8">
      <QuickFileStatements
        reports={quickfileReports}
        fallbackPl={fallbackPl}
        hideZero
        variant="document"
      />

      {sections.length > 0 ? (
        <div className="space-y-4">
          <div>
            <h2 className="solar-section-title">Bank accounts &amp; loans</h2>
            <p className="mt-1 text-sm text-[var(--muted)]">
              Live balances from QuickFile — sorted like the balance sheet. Zero balances hidden.
            </p>
          </div>
          {sections.map((section) => (
            <FinanceItemList
              key={section.bucket}
              title={section.title}
              items={[
                ...section.items,
                {
                  key: `${section.bucket}-subtotal`,
                  label: `Total ${section.title.toLowerCase()}`,
                  amount: section.subtotal,
                  role: section.bucket === "current_assets" ? "asset" : "debt",
                  total: true,
                },
              ]}
            />
          ))}
        </div>
      ) : null}
    </div>
  );
}
