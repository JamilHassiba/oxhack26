import { defineConfig, devices } from '@playwright/test';
export default defineConfig({
  testDir: './tests',
  fullyParallel: true,
  timeout: 30000,
  use: { baseURL: 'http://127.0.0.1:5173', trace: 'retain-on-failure' },
  webServer: [
    {
      command: 'npm run dev -- --port 5173 --strictPort',
      url: 'http://127.0.0.1:5173',
      env: { VITE_DEMO_MODE: 'true' },
      reuseExistingServer: !process.env.CI,
    },
    {
      command: 'npm run dev -- --port 5174 --strictPort',
      url: 'http://127.0.0.1:5174',
      env: { VITE_DEMO_MODE: 'false' },
      reuseExistingServer: !process.env.CI,
    },
  ],
  projects: [
    { name: 'desktop', testMatch: 'app.spec.ts', use: { ...devices['Desktop Chrome'] } },
    {
      name: 'mobile',
      testMatch: 'app.spec.ts',
      use: { ...devices['iPhone 13'], defaultBrowserType: 'chromium' },
    },
    {
      name: 'api-integration',
      testMatch: 'live.spec.ts',
      use: { ...devices['Desktop Chrome'], baseURL: 'http://127.0.0.1:5174' },
    },
  ],
});
