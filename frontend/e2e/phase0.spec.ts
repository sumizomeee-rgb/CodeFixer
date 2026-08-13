import { expect, test } from '@playwright/test'
import { readFileSync } from 'node:fs'
import { mkdir } from 'node:fs/promises'

const fixture = JSON.parse(readFileSync(new URL('./fixtures/visual-control-tower.json', import.meta.url), 'utf8'))
const tasks = fixture.tasks as Array<Record<string, unknown> & {id:string;status:string;result:string|null}>

test.beforeEach(async ({ page }) => {
  await page.route('**/api/**', async route => {
    const request = route.request()
    const url = new URL(request.url())
    const path = url.pathname
    if (path === '/api/settings') return route.fulfill({ json: fixture.settings })
    if (path === '/api/readiness') return route.fulfill({ json: fixture.readiness })
    if (path === '/api/projects') return route.fulfill({ json: {items:fixture.projects,etag:fixture.settings.etag} })
    if (path === '/api/providers') return route.fulfill({ json: {items:fixture.providers} })
    if (path === '/api/tasks') return route.fulfill({ json: {items:tasks} })
    if (path === '/api/dashboard') return route.fulfill({ json: {
      metrics:{active:1,queued:0,running:1,completedChanged:0,completedNoChange:1,failed:1},
      recentTasks:[tasks[0],tasks[2]],attention:[tasks[1]],
    } })
    const taskMatch = path.match(/^\/api\/tasks\/([^/]+)$/)
    if (taskMatch) return route.fulfill({ json: tasks.find(task => task.id === decodeURIComponent(taskMatch[1])) })
    return route.fulfill({ status: 404, json: {error:{code:'fixture_missing',message:path}} })
  })
})

async function proof(page: import('@playwright/test').Page, name: string) {
  await mkdir('test-results/proof', { recursive: true })
  await page.screenshot({ path: `test-results/proof/${name}.png`, fullPage: true })
}

test('control tower surfaces real task facts and configuration tools', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByRole('heading', { name: '任务', exact: true })).toBeVisible()
  await expect(page.getByText('系统待命')).toBeVisible()
  await expect(page.getByText('【4.7】【商城】购买礼包后偶现红点未刷新')).toBeVisible()
  await proof(page, 'tasks-light')

  await page.getByRole('button', { name: '切换主题' }).click()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')
  await proof(page, 'tasks-dark')

  await page.getByText('【4.7】【商城】购买礼包后偶现红点未刷新').click()
  await expect(page.getByRole('dialog')).toBeVisible()
  await expect(page.getByLabel('任务阶段').getByText('修改', { exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: '取消任务' })).toBeVisible()
  await proof(page, 'task-drawer-dark')
  await page.getByRole('button', { name: '关闭' }).click()

  await page.getByRole('button', { name: '反馈源', exact: true }).click()
  await expect(page.getByRole('heading', { name: '工单反馈来源', exact: true })).toBeVisible()
  await page.getByRole('button', { name: '添加反馈源' }).click()
  await expect(page.getByRole('heading', { name: '添加工单反馈来源' })).toBeVisible()
  await page.getByRole('button', { name: '取消' }).click()

  await page.getByRole('button', { name: '流水线', exact: true }).click()
  await expect(page.getByRole('heading', { name: '流水线', exact: true })).toBeVisible()
  await page.getByRole('button', { name: '新增流水线' }).click()
  await expect(page.getByRole('heading', { name: '新增流水线' })).toBeVisible()
  await expect(page.getByText('01')).toBeVisible()
  await expect(page.getByRole('button', { name: /最终交付/ })).toBeVisible()
  await page.getByRole('button', { name: '取消' }).click()

  await page.getByRole('button', { name: '设置', exact: true }).click()
  await expect(page.getByRole('heading', { name: '设置', exact: true })).toBeVisible()
  await expect(page.getByRole('heading', { name: '运行方式' })).toBeVisible()
  await expect(page.getByRole('heading', { name: '当前模型' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'AI 并发池' })).toBeVisible()
  await expect(page.getByRole('heading', { name: '运行环境' })).toBeVisible()
  const increaseConcurrency = page.getByRole('button', { name: '增加并发' })
  const before = await increaseConcurrency.boundingBox()
  await increaseConcurrency.click()
  await expect(page.getByRole('status')).toHaveText('AI 并行调用数已调整为 5')
  const after = await increaseConcurrency.boundingBox()
  expect(after?.x).toBe(before?.x)
  expect(after?.y).toBe(before?.y)
})

test('refresh keeps the selected navigation tab', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: '流水线', exact: true }).click()
  await expect(page).toHaveURL(/#\/projects$/)
  await expect(page.getByRole('heading', { name: '流水线', exact: true })).toBeVisible()

  await page.reload()

  await expect(page.getByRole('heading', { name: '流水线', exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: '流水线', exact: true })).toHaveClass(/nav-active/)
})

test('terminal task separates AI conclusion from delivery result', async ({ page }) => {
  await page.goto('/')
  await page.getByText('【4.7】【登录】弱网重连后角色列表偶发为空').click()
  await expect(page.getByRole('heading', { name: '已修复弱网重连后的角色列表刷新' })).toBeVisible()
  await expect(page.getByText('重连完成后角色缓存仍沿用旧会话标识。')).toBeVisible()

  await page.getByRole('button', { name: '查看交付结果' }).click()
  await expect(page.getByRole('heading', { name: '交付未完全成功' })).toBeVisible()
  await expect(page.getByText('src/login/RoleList.lua')).toBeVisible()
  await expect(page.getByText('GitLab Commit')).toBeVisible()
  await page.waitForTimeout(300)
  await proof(page, 'task-delivery-result')

  await page.getByRole('button', { name: '← 任务结论' }).click()
  await expect(page.getByRole('heading', { name: '已修复弱网重连后的角色列表刷新' })).toBeVisible()
})

test('@visual approved surfaces', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByText('【4.7】【商城】购买礼包后偶现红点未刷新')).toBeVisible()
  // 异常置顶：失败任务排在处理中任务之前，且有一条分隔标注
  const titles = page.locator('.task-row b')
  await expect(titles.first()).toHaveText('【4.7】【登录】弱网重连后角色列表偶发为空')
  await expect(page.locator('.ledger-divider').first()).toBeVisible()
  await expect(page).toHaveScreenshot('tasks-ledger-light.png', { fullPage: true })

  await page.getByRole('button', { name: '切换主题' }).click()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')
  await expect(page).toHaveScreenshot('tasks-ledger-dark.png', { fullPage: true })

  await page.getByText('【4.7】【登录】弱网重连后角色列表偶发为空').click()
  await expect(page.getByRole('dialog')).toBeVisible()
  await expect(page.getByText('GitLab 任务分支推送失败，保底 Patch 已生成。')).toBeVisible()
  await expect(page).toHaveScreenshot('task-failed-drawer-dark.png', { fullPage: true })
  await page.getByRole('button', { name: '关闭' }).click()
  await page.getByText('【4.7】【背包】空物品格仍显示旧品质边框').click()
  await expect(page.getByText('代码已经满足工单描述')).toBeVisible()
  await expect(page).toHaveScreenshot('task-no-change-drawer-dark.png', { fullPage: true })
})

test('@visual first-run ledger asks for a source instead of claiming standby', async ({ page }) => {
  // 覆盖真机首次启动：零任务 + 零来源 + 零项目
  await page.route('**/api/**', async route => {
    const path = new URL(route.request().url()).pathname
    if (path === '/api/settings') return route.fulfill({ json: fixture.settings })
    if (path === '/api/readiness') return route.fulfill({ json: fixture.readiness })
    if (path === '/api/tasks') return route.fulfill({ json: {items:[]} })
    if (path === '/api/providers') return route.fulfill({ json: {items:[]} })
    if (path === '/api/projects') return route.fulfill({ json: {items:[],etag:fixture.settings.etag} })
    return route.fulfill({ status: 404, json: {error:{code:'fixture_missing',message:path}} })
  })
  await page.goto('/')
  await expect(page.getByRole('heading', { name: '还没有可以收问题的通路' })).toBeVisible()
  // 空账本不摆无账可刷的按钮，也不摆全 0 的计数
  await expect(page.getByRole('button', { name: '刷新账本' })).toHaveCount(0)
  await expect(page.locator('.ledger-summary')).toHaveCount(0)
  await expect(page.locator('.filter-strip')).toHaveCount(0)
  await expect(page).toHaveScreenshot('tasks-first-run-light.png', { fullPage: true })

  // 两步都指向真实去处
  await page.getByRole('listitem').filter({ hasText: '接入工单反馈来源' }).getByRole('button').click()
  await expect(page.getByRole('heading', { name: '工单反馈来源', exact: true })).toBeVisible()
})

test('@visual configuration and responsive surfaces', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: '设置', exact: true }).click()
  await expect(page.getByRole('heading', { name: '运行环境' })).toBeVisible()
  await expect(page).toHaveScreenshot('settings-light.png', { fullPage: true })

  await page.getByRole('button', { name: '流水线', exact: true }).click()
  await expect(page.getByText('客户端 Lua 修复通道')).toBeVisible()
  await expect(page).toHaveScreenshot('projects-light.png', { fullPage: true })
  await page.setViewportSize({ width: 1024, height: 768 })
  await page.getByRole('button', { name: '编辑配置', exact: true }).click()
  await expect(page.getByRole('dialog')).toBeVisible()
  await expect(page).toHaveScreenshot('project-workbench-compact.png', { fullPage: true })
  await page.getByRole('button', { name: '关闭' }).click()

  await page.setViewportSize({ width: 1440, height: 900 })
  await page.getByRole('button', { name: '反馈源', exact: true }).click()
  await expect(page.getByText('Haru TAPD', { exact: true })).toBeVisible()
  await expect(page).toHaveScreenshot('providers-light.png', { fullPage: true })

  await page.setViewportSize({ width: 420, height: 780 })
  await page.getByRole('button', { name: '任务', exact: true }).click()
  await expect(page.getByRole('heading', { name: '任务', exact: true })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true)
  // B4：滚到底后最后一行不能被固定 tabbar 压住
  await page.mouse.wheel(0, 4000)
  await page.waitForTimeout(400)
  const clearance = await page.evaluate(() => {
    const rows = document.querySelectorAll('.task-row')
    const last = rows[rows.length - 1]?.getBoundingClientRect()
    const bar = document.querySelector('.navrail')?.getBoundingClientRect()
    return last && bar ? bar.top - last.bottom : 1
  })
  expect(clearance).toBeGreaterThanOrEqual(0)
  await expect(page).toHaveScreenshot('tasks-mobile-light.png', { fullPage: true })
})
