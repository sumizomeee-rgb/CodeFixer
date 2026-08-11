import { createRoot } from 'react-dom/client'
import { expect, test } from 'vitest'
import { page } from 'vitest/browser'
import App from '../src/App'

test('renders repair control tower semantics', async () => {
  const root = document.createElement('div')
  document.body.appendChild(root)
  createRoot(root).render(<App />)
  await expect.element(page.getByRole('heading', { name: '维修控制台' })).toBeVisible()
  await expect.element(page.getByLabelText('任务阶段').first()).toBeVisible()
  await expect.element(page.getByText('PARTIAL DELIVERY', { exact: false })).toBeVisible()
})
