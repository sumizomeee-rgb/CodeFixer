import { expect, test } from '@playwright/test'

test('control tower is interactive', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByRole('heading', { name: '维修控制台' })).toBeVisible()
  await expect(page.getByText('系统就绪')).toBeVisible()
  await expect(page.getByText('PARTIAL DELIVERY', { exact: false })).toBeVisible()
  await page.getByRole('button', { name: '切换主题' }).click()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')
  await page.getByRole('button', { name: '项目' }).click()
  await expect(page.getByRole('heading', { name: '项目', exact: true })).toBeVisible()
  await expect(page.getByText('还没有项目')).toBeVisible()
})

test('@visual dashboard light', async ({ page }) => {
  await page.route('**/api/settings', async route => {
    await route.fulfill({ json: { config: { schemaVersion: 1, execution: { mode: 'automatic', maxConcurrentTasks: 3, maxRepairAttempts: 3 }, pathBindings: {}, executableBindings: {}, agentProfiles: [], projects: [] }, secrets: {}, etag: 'visual' } })
  })
  await page.goto('/')
  await expect(page.getByText('系统就绪')).toBeVisible()
  await expect(page).toHaveScreenshot('dashboard-light.png', { fullPage: true })
})
