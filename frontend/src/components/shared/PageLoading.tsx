type PageLoadingProps = {
  label?: string;
  rows?: number;
};

export function PageLoading({ label = "Loading…", rows = 3 }: PageLoadingProps) {
  return (
    <div className="space-y-4" role="status" aria-label={label}>
      <p className="sr-only">{label}</p>
      {Array.from({ length: rows }, (_, index) => (
        <div key={index} className="solar-card space-y-3 p-6">
          <div className="solar-skeleton h-4 w-1/3 rounded-md" />
          <div className="solar-skeleton h-3 w-full rounded-md" />
          <div className="solar-skeleton h-3 w-2/3 rounded-md" />
        </div>
      ))}
    </div>
  );
}
