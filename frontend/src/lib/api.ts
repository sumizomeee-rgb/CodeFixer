import type { ExecutionMode, PreflightResult, ProjectConfig, SettingsResponse } from '../entities/config'

export class ApiError extends Error {
  status: number
  code: string

  constructor(status: number, code: string, message: string) {
    super(message)
    this.status = status
    this.code = code
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers ?? {}),
    },
  })
  if (!response.ok) {
    const payload = await response.json().catch(() => null)
    const error = payload?.error ?? payload?.detail ?? {}
    throw new ApiError(response.status, error.code ?? 'request_failed', error.message ?? `HTTP ${response.status}`)
  }
  return response.json() as Promise<T>
}

export const api = {
  health: () => request<{ status: string; service: string; version: string }>('/api/health'),
  readiness: () => request<{ ready: boolean; status: string; checks: unknown[] }>('/api/readiness'),
  settings: () => request<SettingsResponse>('/api/settings'),
  setExecutionMode: (mode: ExecutionMode, etag: string) =>
    request<{ mode: ExecutionMode; etag: string }>('/api/settings/execution-mode', {
      method: 'PUT',
      headers: { 'If-Match': etag },
      body: JSON.stringify({ mode }),
    }),
  projects: () => request<{ items: ProjectConfig[]; etag: string }>('/api/projects'),
  createProject: (project: ProjectConfig, etag: string) =>
    request<{ project: ProjectConfig; etag: string }>('/api/projects', {
      method: 'POST',
      headers: { 'If-Match': etag },
      body: JSON.stringify(project),
    }),
  preflight: (projectId: string) => request<PreflightResult>(`/api/projects/${encodeURIComponent(projectId)}/preflight`, { method: 'POST' }),
  setSecret: (key: string, value: string) => request<{ key: string; configured: boolean }>(`/api/secrets/${encodeURIComponent(key)}`, {
    method: 'PUT',
    body: JSON.stringify({ value }),
  }),
}
