"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

/** Legacy URL — Open Banking setup now lives on Connect banks. */
export default function OpenBankingSettingsRedirect() {
  const router = useRouter();
  useEffect(() => {
    router.replace("/finance/connect#open-banking-setup");
  }, [router]);
  return null;
}
