import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './e2e',
  timeout: 30_000,
  use: {
    baseURL: process.env.CODEFIXER_E2E_URL ?? 'http://127.0.0.1:9522',
    locale: 'zh-CN',
    timezoneId: 'Asia/Singapore',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 900 } } }],
  expect: { toHaveScreenshot: { animations: 'disabled' } },
})
