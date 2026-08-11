import { createRoot } from 'react-dom/client'
import { expect, test, vi } from 'vitest'
import { page } from 'vitest/browser'
import App from '../src/App'

test('renders repair control tower semantics', async () => {
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
    const url=String(input)
    if(url.includes('/api/settings')) return new Response(JSON.stringify({config:{schemaVersion:1,execution:{mode:'automatic',maxConcurrentTasks:3,maxRepairAttempts:3},pathBindings:{},executableBindings:{},agentProfiles:[],projects:[]},secrets:{},etag:'test'}),{status:200,headers:{'Content-Type':'application/json'}})
    if(url.includes('/api/readiness')) return new Response(JSON.stringify({ready:true,status:'ready',checks:[]}),{status:200,headers:{'Content-Type':'application/json'}})
    return new Response('{}',{status:200,headers:{'Content-Type':'application/json'}})
  }))
  const root = document.createElement('div')
  document.body.appendChild(root)
  createRoot(root).render(<App />)
  await expect.element(page.getByRole('heading', { name: '维修控制台' })).toBeVisible()
  await expect.element(page.getByLabelText('任务阶段').first()).toBeVisible()
  await expect.element(page.getByText('PARTIAL DELIVERY', { exact: false })).toBeVisible()
})
