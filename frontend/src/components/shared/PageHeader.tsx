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
    <div className="flex flex-wrap items-end justify-between gap-4">
      <div className="flex items-start gap-4">
        {icon ? (
          <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br from-amber-400/20 to-orange-500/20 text-[var(--solar-dark)] ring-1 ring-[var(--border)]">
            {icon}
          </div>
        ) : null}
        <div>
          <p className="solar-eyebrow text-[var(--solar-dark)]">{eyebrow}</p>
          <h2 className="mt-1 text-3xl font-bold tracking-tight">{title}</h2>
          {description ? <p className="mt-1 text-sm text-[var(--muted)]">{description}</p> : null}
        </div>
      </div>
      {actions ? <div className="flex flex-wrap gap-2">{actions}</div> : null}
    </div>
  );
}
