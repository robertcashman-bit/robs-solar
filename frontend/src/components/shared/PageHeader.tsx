import type { ReactNode } from "react";

type PageHeaderProps = {
  eyebrow: string;
  title: ReactNode;
  description?: string;
  icon?: ReactNode;
  actions?: ReactNode;
};

export function PageHeader({ eyebrow, title, description, icon, actions }: PageHeaderProps) {
  return (
    <header className="flex flex-col gap-4 sm:flex-row sm:flex-wrap sm:items-end sm:justify-between">
      <div className="flex min-w-0 items-start gap-4">
        {icon ? (
          <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br from-amber-400/20 to-orange-500/20 text-[var(--solar-dark)] ring-1 ring-[var(--border)]">
            {icon}
          </div>
        ) : null}
        <div className="min-w-0">
          <p className="solar-eyebrow text-[var(--solar-dark)]">{eyebrow}</p>
          <h1 className="mt-1 text-2xl font-bold tracking-tight sm:text-3xl">{title}</h1>
          {description ? (
            <p className="mt-1 max-w-2xl text-sm leading-relaxed text-[var(--muted)]">{description}</p>
          ) : null}
        </div>
      </div>
      {actions ? (
        <div className="flex w-full shrink-0 flex-wrap gap-2 sm:w-auto sm:justify-end">{actions}</div>
      ) : null}
    </header>
  );
}
