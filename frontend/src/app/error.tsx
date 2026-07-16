"use client";

import { useEffect } from "react";

type ErrorPageProps = {
  error: Error & { digest?: string };
  reset: () => void;
};

export default function ErrorPage({ error, reset }: ErrorPageProps) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div className="flex min-h-[50vh] flex-col items-center justify-center px-4 py-16 text-center">
      <p className="text-xs font-semibold uppercase tracking-wider text-[var(--muted)]">
        Something went wrong
      </p>
      <h1 className="mt-2 text-2xl font-semibold text-[var(--foreground)]">This page hit an error</h1>
      <p className="mt-2 max-w-md text-sm text-[var(--muted)]">
        You can try again. If it keeps happening, refresh the page or sign in again.
      </p>
      {error.digest ? (
        <p className="mt-3 font-mono text-xs text-[var(--muted)]">Ref: {error.digest}</p>
      ) : null}
      <button type="button" className="solar-btn-primary mt-6" onClick={() => reset()}>
        Try again
      </button>
    </div>
  );
}
