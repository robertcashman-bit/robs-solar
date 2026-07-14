"use client";

import { Suspense, useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";

/** Legacy OB Setup URL — merged into Connect banks. */
function OpenBankingSetupRedirectInner() {
  const router = useRouter();
  const searchParams = useSearchParams();

  useEffect(() => {
    const params = searchParams.toString();
    router.replace(params ? `/finance/connect?${params}` : "/finance/connect");
  }, [router, searchParams]);

  return null;
}

export default function OpenBankingSetupRoute() {
  return (
    <Suspense fallback={null}>
      <OpenBankingSetupRedirectInner />
    </Suspense>
  );
}
