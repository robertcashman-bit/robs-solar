import { defineConfig, devices } from "@playwright/test";

const backendEnv = {
  SECRET_KEY: "e2e-test-secret",
  DATABASE_URL: "sqlite+aiosqlite:///./data/e2e_robs_solar.db",
  READ_ONLY: "false",
  ADAPTER_MODE: "simulator",
  ADMIN_USERNAME: "admin",
  ADMIN_PASSWORD: "change-me-admin",
  VIEWER_USERNAME: "viewer",
  VIEWER_PASSWORD: "change-me-viewer",
  METRICS_SAMPLER_ENABLED: "true",
  METRICS_SAMPLE_INTERVAL_SECONDS: "2",
  // Parallel specs share one backend; the default 10 writes/min trips spurious
  // 429s, so lift the ceiling well above the suite's write volume.
  RATE_LIMIT_WRITES_PER_MINUTE: "1000",
};

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  // The dev server compiles each route on first hit; cap parallelism so a burst
  // of cold compiles doesn't thrash CPU and time out the login step.
  workers: process.env.CI ? 4 : undefined,
  timeout: 60_000,
  expect: { timeout: 10_000 },
  use: {
    baseURL: "http://127.0.0.1:3000",
    trace: "on-first-retry",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      // Invoke the venv interpreter directly: CI runs /bin/sh (dash), which has
      // no `source` builtin, so activating the venv fails with exit 127.
      command:
        "cd ../backend && .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000",
      url: "http://127.0.0.1:8000/health",
      reuseExistingServer: !process.env.CI,
      env: backendEnv,
    },
    {
      command: "npm run dev -- --port 3000",
      url: "http://127.0.0.1:3000",
      reuseExistingServer: !process.env.CI,
    },
  ],
});
