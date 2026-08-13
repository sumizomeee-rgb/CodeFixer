import { createRoot } from 'react-dom/client'
import { expect, test, vi } from 'vitest'
import { page } from 'vitest/browser'
import App from '../src/App'

const tasks = [
  { id:'task-1', provider_instance_id:'redmine', external_ticket_id:'42', title:'修正边界条件', project_id:'demo', status:'running', result:null, created_at:'2026-08-13T08:00:00Z', updated_at:'2026-08-13T08:00:01Z' },
  { id:'task-2', provider_instance_id:'redmine', external_ticket_id:'43', title:'交付需要处理', project_id:'demo', status:'failed', result:null, created_at:'2026-08-13T07:00:00Z', updated_at:'2026-08-13T07:30:00Z', failure:{code:'delivery_failed',stage:'deliver',summary:'PARTIAL DELIVERY · Patch 已保全'} },
]
const detail = {
  ...tasks[1],
  runs:[{ id:'run-1', status:'failed', stages:[
    { id:1, stage_id:'prepare', attempt:1, status:'completed', started_at:'2026-08-13T08:00:00Z', finished_at:'2026-08-13T08:00:01Z' },
    { id:2, stage_id:'discovery', attempt:1, status:'running', started_at:'2026-08-13T08:00:01Z' },
  ], artifacts:[], delivery_actions:[] }],
  events:[],
}

test('renders repair ledger semantics', async () => {
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
    const url=String(input)
    const json=(data:unknown)=>new Response(JSON.stringify(data),{status:200,headers:{'Content-Type':'application/json'}})
    if(url.includes('/api/settings')) return json({config:{schemaVersion:1,execution:{mode:'automatic',currentModelId:'claude-haiku',maxConcurrentTasks:3,maxConcurrentLlmCalls:4,maxRepairAttempts:3},executableBindings:{},agentProfiles:[],ticketProviders:[],projects:[]},secrets:{},etag:'test'})
    if(url.includes('/api/readiness')) return json({ready:true,status:'ready',checks:[]})
    if(/\/api\/tasks\/[^/]+$/.test(url)) return json(detail)
    if(url.includes('/api/tasks')) return json({items:tasks})
    return json({})
  }))
  const root = document.createElement('div')
  document.body.appendChild(root)
  createRoot(root).render(<App />)

  // 进入系统直接落在账本上，无需点击导航
  await expect.element(page.getByRole('heading', { name: '任务', exact: true })).toBeVisible()
  // 异常置顶：失败任务排在处理中任务之前
  await expect.element(page.getByText('需要处理', { exact: false }).first()).toBeVisible()
  await expect.element(page.getByText('修正边界条件')).toBeVisible()

  // 抽屉里才有完整信号轨与失败摘要
  await page.getByText('交付需要处理').click()
  await expect.element(page.getByLabelText('任务阶段').first()).toBeVisible()
  await expect.element(page.getByText('PARTIAL DELIVERY', { exact: false })).toBeVisible()
})
