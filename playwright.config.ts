import { defineConfig, devices } from '@playwright/test';

// Cross-browser e2e config for the Starter Lab vanilla build.
// Runs every spec in tests/e2e against Chromium, WebKit (Safari engine) and Firefox.
//   Setup once:  npm i -D @playwright/test && npx playwright install
//   Run:         npm run test:e2e            (or: npx playwright test)
// The webServer block auto-starts app/server.py (:4788) in CI and reuses a running one in dev.
export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  // The app shares one Web Worker + a single dev server; run serially so parallel
  // browsers don't contend for them and make the reveal/recompute timing flaky.
  workers: 1,
  retries: process.env.CI ? 2 : 1,
  reporter: process.env.CI ? [['github'], ['list']] : 'list',
  use: {
    // 127.0.0.1 (not "localhost"): the Python server binds IPv4 only, and WebKit/Firefox
    // try IPv6 ::1 first for "localhost", which hangs the navigation.
    baseURL: 'http://127.0.0.1:4788',
    trace: 'on-first-retry',
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
    { name: 'webkit', use: { ...devices['Desktop Safari'] } },
    { name: 'firefox', use: { ...devices['Desktop Firefox'] } },
  ],
  webServer: {
    command: 'python3 server.py',
    cwd: 'app',
    url: 'http://127.0.0.1:4788/lab.built.html',
    reuseExistingServer: !process.env.CI,
    timeout: 30_000,
  },
});
