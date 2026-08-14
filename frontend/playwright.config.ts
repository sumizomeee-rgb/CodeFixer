import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './e2e',
  timeout: 30_000,
  snapshotPathTemplate: '{testDir}/{testFilePath}-snapshots/{arg}-{projectName}.png',
  use: {
    baseURL: process.env.CODEFIXER_E2E_URL ?? 'http://127.0.0.1:9522',
    locale: 'zh-CN',
    timezoneId: 'Asia/Singapore',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 900 } } }],
  // 0.006 的容差约等于 1440×900 里的 7776 px，实测能放过「整块文字区消失」这种改动
  // （删掉运行环境卡的摘要行只有 5299 px 差异，旧配置全绿）。同一台机器上连跑三次是
  // 零像素差异，所以这里按确定性渲染收紧：只留抗抗锯齿的单像素色差容忍。
  expect: { toHaveScreenshot: { animations: 'disabled', threshold: 0.2, maxDiffPixelRatio: 0.0005 } },
})
