import { createRoot } from 'react-dom/client'
import { expect, test, vi } from 'vitest'
import { page } from 'vitest/browser'
import App from '../src/App'

test('renders repair control tower semantics', async () => {
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
    const url=String(input)
    if(url.includes('/api/settings')) return new Response(JSON.stringify({config:{schemaVersion:1,execution:{mode:'automatic',currentModelId:'claude-haiku',maxConcurrentTasks:3,maxConcurrentLlmCalls:4,maxRepairAttempts:3},executableBindings:{},agentProfiles:[],ticketProviders:[],projects:[]},secrets:{},etag:'test'}),{status:200,headers:{'Content-Type':'application/json'}})
    if(url.includes('/api/readiness')) return new Response(JSON.stringify({ready:true,status:'ready',checks:[]}),{status:200,headers:{'Content-Type':'application/json'}})
    if(url.includes('/api/dashboard')) return new Response(JSON.stringify({metrics:{active:1,queued:0,running:1,completedChanged:0,completedNoChange:0,failed:1},recentTasks:[{id:'task-1',provider_instance_id:'redmine',external_ticket_id:'42',title:'修正边界条件',project_id:'demo',status:'running',result:null,runs:[{id:'run-1',status:'running',stages:[{stage_id:'prepare',status:'completed',started_at:'2026-08-13T08:00:00Z',finished_at:'2026-08-13T08:00:01Z'},{stage_id:'discovery',status:'running',started_at:'2026-08-13T08:00:01Z'}]}]}],attention:[{id:'task-2',title:'交付需要处理',failure:{summary:'PARTIAL DELIVERY · Patch 已保全'}}]}),{status:200,headers:{'Content-Type':'application/json'}})
    return new Response('{}',{status:200,headers:{'Content-Type':'application/json'}})
  }))
  const root = document.createElement('div')
  document.body.appendChild(root)
  createRoot(root).render(<App />)
  await expect.element(page.getByRole('heading', { name: '维修控制台' })).toBeVisible()
  await expect.element(page.getByLabelText('任务阶段').first()).toBeVisible()
  await expect.element(page.getByText('PARTIAL DELIVERY', { exact: false })).toBeVisible()
})
