import { expect, test } from '@playwright/test'

test('phase0 control tower is interactive', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByRole('heading', { name: '维修控制台' })).toBeVisible()
  await expect(page.getByText('系统就绪')).toBeVisible()
  await expect(page.getByText('PARTIAL DELIVERY', { exact: false })).toBeVisible()
  await page.getByRole('button', { name: '切换主题' }).click()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')
})

test('@visual dashboard light', async ({ page }) => {
  await page.goto('/')
  await expect(page).toHaveScreenshot('dashboard-light.png', { fullPage: true })
})
