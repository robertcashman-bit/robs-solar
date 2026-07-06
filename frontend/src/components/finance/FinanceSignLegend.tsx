import { FINANCE_SIGN_LEGEND } from "@/lib/money";

export function FinanceSignLegend() {
  return (
    <p className="rounded-xl border border-[var(--border)] bg-[var(--surface)] px-4 py-3 text-sm text-[var(--muted)]">
      <span className={`font-semibold ${"text-emerald-600 dark:text-emerald-400"}`}>+ Credit / asset</span>
      {" — "}
      money you have or receive (bank balance, property, pension, income).
      {" "}
      <span className={`font-semibold ${"text-red-600 dark:text-red-400"}`}>− Debit / debt</span>
      {" — "}
      money you owe or pay out (mortgage, credit cards, spending, bills).
      {" "}
      {FINANCE_SIGN_LEGEND}
    </p>
  );
}
