import { formatFinanceGbp, type FinanceAmountRole } from "@/lib/money";

type FinanceAmountProps = {
  value: number | null | undefined;
  role: FinanceAmountRole;
  className?: string;
};

export function FinanceAmount({ value, role, className = "" }: FinanceAmountProps) {
  const formatted = formatFinanceGbp(value, role);
  return (
    <span className={`font-semibold tabular-nums ${formatted.className} ${className}`.trim()}>
      {formatted.text}
    </span>
  );
}
