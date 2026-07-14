import type { ReactNode } from "react";

type InfoBannerVariant = "info" | "warning" | "success" | "neutral";

type InfoBannerProps = {
  children: ReactNode;
  variant?: InfoBannerVariant;
  role?: "status" | "alert";
};

const variantStyles: Record<InfoBannerVariant, string> = {
  info: "border-sky-300/40 bg-sky-50/80 text-sky-900 dark:bg-sky-950/30 dark:text-sky-200",
  warning:
    "border-amber-300/40 bg-amber-50/80 text-amber-900 dark:bg-amber-950/30 dark:text-amber-200",
  success:
    "border-emerald-300/40 bg-emerald-50/80 text-emerald-900 dark:bg-emerald-950/30 dark:text-emerald-200",
  neutral: "border-[var(--border)] bg-[var(--surface)] text-[var(--foreground)]",
};

export function InfoBanner({ children, variant = "info", role = "status" }: InfoBannerProps) {
  return (
    <p role={role} className={`rounded-xl border px-4 py-3 text-sm ${variantStyles[variant]}`}>
      {children}
    </p>
  );
}
