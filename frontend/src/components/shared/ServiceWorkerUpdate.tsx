"use client";

import { useEffect } from "react";

import { registerServiceWorker } from "@/lib/register-service-worker";

/** Activates SW update checks and auto-reload when a new build is deployed. */
export function ServiceWorkerUpdate() {
  useEffect(() => {
    registerServiceWorker();
  }, []);

  return null;
}
