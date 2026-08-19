import { AlertIcon } from "@/components/shared/icons";

type BannerProps = {
  message: string;
};

export function ErrorBanner({ message }: BannerProps) {
  return (
    <div
      role="alert"
      className="flex items-start gap-3 rounded-xl border border-red-400/50 bg-red-500/15 px-4 py-3 text-[var(--foreground)]"
    >
      <AlertIcon size={18} className="mt-0.5 shrink-0 text-red-400" />
      <span>{message}</span>
    </div>
  );
}

export function SuccessBanner({ message }: BannerProps) {
  return (
    <div
      role="status"
      className="flex items-start gap-3 rounded-xl border border-emerald-400/50 bg-emerald-500/15 px-4 py-3 text-[var(--foreground)]"
    >
      <span>{message}</span>
    </div>
  );
}

export function OfflineBanner({ message }: BannerProps) {
  return (
    <div
      role="status"
      className="flex items-start gap-3 rounded-xl border border-amber-400/50 bg-amber-500/15 px-4 py-3 text-[var(--foreground)]"
    >
      <AlertIcon size={18} className="mt-0.5 shrink-0 text-amber-400" />
      <span>{message}</span>
    </div>
  );
}
