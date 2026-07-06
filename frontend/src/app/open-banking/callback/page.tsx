"use client";

import { Suspense, useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";

function OpenBankingCallbackInner() {
  const router = useRouter();
  const searchParams = useSearchParams();

  useEffect(() => {
    const params = new URLSearchParams(searchParams.toString());
    params.set("open_banking", "callback");
    router.replace(`/finance/open-banking/setup?${params.toString()}`);
  }, [router, searchParams]);

  return (
    <main className="flex min-h-[40vh] items-center justify-center p-6">
      <p className="text-sm text-muted-foreground">Completing bank connection…</p>
    </main>
  );
}

/** Enable Banking redirect target (no query params in CP whitelist). */
export default function OpenBankingCallbackPage() {
  return (
    <Suspense
      fallback={
        <main className="flex min-h-[40vh] items-center justify-center p-6">
          <p className="text-sm text-muted-foreground">Completing bank connection…</p>
        </main>
      }
    >
      <OpenBankingCallbackInner />
    </Suspense>
  );
}
