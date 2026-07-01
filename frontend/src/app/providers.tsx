"use client";

import { AuthProvider } from "@/lib/auth-context";
import { ServiceWorkerUpdate } from "@/components/shared/ServiceWorkerUpdate";

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <AuthProvider>
      <ServiceWorkerUpdate />
      {children}
    </AuthProvider>
  );
}
