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
  RATE_LIMIT_WRITES_PER_MINUTE: "1000",
};

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: !process.env.CI,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  timeout: 90_000,
  expect: { timeout: 20_000 },
  use: {
    baseURL: "http://127.0.0.1:3000",
    trace: "on-first-retry",
  },
  projects: [
    { name: "setup", testMatch: /auth\.setup\.ts/ },
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
        storageState: "e2e/.auth/admin.json",
      },
      dependencies: ["setup"],
      testIgnore: /\.setup\.ts$/,
    },
  ],
  webServer: [
    {
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
