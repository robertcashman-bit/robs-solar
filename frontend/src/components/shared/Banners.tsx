import { AlertIcon } from "@/components/shared/icons";

type BannerProps = {
  message: string;
};

export function ErrorBanner({ message }: BannerProps) {
  return (
    <div
      role="alert"
      className="flex items-start gap-3 rounded-xl border border-red-300/50 bg-red-50/90 px-4 py-3 text-red-800 dark:border-red-800/50 dark:bg-red-950/40 dark:text-red-300"
    >
      <AlertIcon size={18} className="mt-0.5 shrink-0" />
      <span>{message}</span>
    </div>
  );
}

export function OfflineBanner({ message }: BannerProps) {
  return (
    <div
      role="status"
      className="flex items-start gap-3 rounded-xl border border-amber-300/50 bg-amber-50/90 px-4 py-3 text-amber-900 dark:border-amber-800/50 dark:bg-amber-950/40 dark:text-amber-200"
    >
      <AlertIcon size={18} className="mt-0.5 shrink-0" />
      <span>{message}</span>
    </div>
  );
}
