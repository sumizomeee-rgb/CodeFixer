import { expect, test } from '@playwright/test'
import { mkdir } from 'node:fs/promises'

async function proof(page: import('@playwright/test').Page, name: string) {
  await mkdir('test-results/proof', { recursive: true })
  await page.screenshot({ path: `test-results/proof/${name}.png`, fullPage: true })
}

test('control tower surfaces real task facts and configuration tools', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByRole('heading', { name: '维修控制台' })).toBeVisible()
  await expect(page.getByText('系统正常')).toBeVisible()
  await expect(page.getByText('【4.7】【商城】购买礼包后偶现红点未刷新')).toBeVisible()
  await expect(page.getByText('release/4.7 cherry-pick 冲突')).toBeVisible()
  await proof(page, 'dashboard-light')

  await page.getByRole('button', { name: '切换主题' }).click()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')
  await proof(page, 'dashboard-dark')

  await page.getByRole('button', { name: '任务', exact: true }).click()
  await expect(page.getByRole('heading', { name: '任务', exact: true })).toBeVisible()
  await page.getByText('【4.7】【商城】购买礼包后偶现红点未刷新').click()
  await expect(page.getByRole('dialog')).toBeVisible()
  await expect(page.getByText('修复', { exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: '取消任务' })).toBeVisible()
  await proof(page, 'task-drawer-dark')
  await page.getByRole('button', { name: '关闭' }).click()

  await page.getByRole('button', { name: '来源', exact: true }).click()
  await expect(page.getByRole('heading', { name: '工单来源', exact: true })).toBeVisible()
  await page.getByRole('button', { name: '添加来源' }).click()
  await expect(page.getByRole('heading', { name: '添加工单来源' })).toBeVisible()
  await page.getByRole('button', { name: '取消' }).click()

  await page.getByRole('button', { name: '项目', exact: true }).click()
  await expect(page.getByRole('heading', { name: '项目', exact: true })).toBeVisible()
  await page.getByRole('button', { name: '新建项目' }).click()
  await expect(page.getByRole('heading', { name: '创建修复通道' })).toBeVisible()
  await expect(page.getByText('01')).toBeVisible()
  await expect(page.getByRole('button', { name: /最终交付/ })).toBeVisible()
  await page.getByRole('button', { name: '取消' }).click()

  await page.getByRole('button', { name: '设置', exact: true }).click()
  await expect(page.getByRole('heading', { name: '设置', exact: true })).toBeVisible()
  await expect(page.getByRole('heading', { name: '运行方式' })).toBeVisible()
  await expect(page.getByRole('heading', { name: '当前模型' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'AI 并发池' })).toBeVisible()
  await expect(page.getByRole('heading', { name: '运行环境' })).toBeVisible()
})

test('@visual dashboard light', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByText('【4.7】【商城】购买礼包后偶现红点未刷新')).toBeVisible()
  await expect(page).toHaveScreenshot('dashboard-light.png', { fullPage: true })
})
