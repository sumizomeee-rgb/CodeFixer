export type ExecutionMode = 'automatic' | 'awaitingStart'

export type AppConfig = {
  schemaVersion: number
  execution: {
    mode: ExecutionMode
    maxConcurrentTasks: number
    maxRepairAttempts: number
  }
  pathBindings: Record<string, string>
  executableBindings: Record<string, { command?: string[]; versionArgs?: string[]; versionConstraint?: string | null }>
  agentProfiles: Array<Record<string, unknown> & { id?: string }>
  projects: ProjectConfig[]
}

export type ProjectConfig = {
  id: string
  name?: string
  enabled?: boolean
  modificationSource?: {
    type?: 'git' | 'svn'
    repositoryRef?: string
    executableRef?: string
  }
  agents?: {
    discovery?: string
    repair?: string
    review?: string
  }
  verification?: {
    steps?: unknown[]
    allowNoAutomatedTests?: boolean
    reason?: string
  }
  finalActions?: Array<Record<string, unknown> & { id?: string; type?: 'patch' | 'gitlabMr' }>
}

export type SettingsResponse = {
  config: AppConfig
  secrets: Record<string, { configured: boolean }>
  etag: string
}

export type PreflightCheck = {
  id: string
  status: 'ready' | 'warning' | 'failed'
  summary: string
  suggestion?: string
}

export type PreflightResult = {
  projectId: string
  ready: boolean
  status: 'ready' | 'not_ready'
  checks: PreflightCheck[]
}
