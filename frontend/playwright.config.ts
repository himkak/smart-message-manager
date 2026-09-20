import { defineConfig, devices } from "@playwright/test";

/**
 * End-to-end tests drive the real Vite dev server against the real backend
 * (which is expected to already be configured with live Azure credentials),
 * matching how earlier phases were verified. Playwright starts both servers
 * automatically (reusing them if already running). Backend port defaults to
 * 8000; override with the BACKEND_PORT environment variable if needed.
 *
 * Run with: npx playwright test
 */
const backendPort = process.env.BACKEND_PORT ?? "8000";

export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  retries: 0,
  reporter: "list",
  use: {
    baseURL: "http://localhost:5173",
    trace: "retain-on-failure",
  },
  webServer: [
    {
      command: "npm run dev",
      url: "http://localhost:5173",
      reuseExistingServer: true,
      timeout: 30_000,
      env: { VITE_API_BASE_URL: `http://127.0.0.1:${backendPort}` },
    },
    {
      command: `".venv\\Scripts\\python.exe" -m uvicorn app.main:app --app-dir backend --port ${backendPort}`,
      cwd: "..",
      url: `http://127.0.0.1:${backendPort}/health`,
      reuseExistingServer: true,
      timeout: 30_000,
    },
  ],
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
