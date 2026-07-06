"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

/** Legacy URL — redirects to the Open Banking Setup page. */
export default function OpenBankingSettingsRedirect() {
  const router = useRouter();
  useEffect(() => {
    router.replace("/finance/open-banking/setup");
  }, [router]);
  return null;
}
