export type ExecutionMode = 'automatic' | 'awaitingStart'
export type AgentRuntime = 'claudeCode' | 'codex' | 'opencode'
export type RoutingOperator = 'eq' | 'neq' | 'contains' | 'in' | 'exists'
export type VcsKind = 'git' | 'svn' | 'unknown'
export type HostingKind = 'gitlab' | 'github' | 'other' | 'none' | 'ambiguous'

export type ExecutableBinding = { command?: string[]; versionArgs?: string[]; versionConstraint?: string | null; versionRegex?: string }
export type AgentProfileConfig = { id:string; runtime:AgentRuntime; executableRef:string; model?:string; effort?:string; timeoutSeconds?:number; maxBudgetUsd?:number; extraArgs?:string[] }
export type TicketProviderConfig = Record<string, unknown> & { id:string; type:'redmine'|'tapd'; enabled?:boolean; pollIntervalSeconds?:number }
export type RoutingRule = { id:string; providerRef:string; priority:number; catchAll?:boolean; conditions?:Array<{field:string;operator:RoutingOperator;value?:unknown}> }
export type VerificationStepConfig = { id:string; executableRef:string; args:string[]; workingDirectory?:string; timeoutSeconds?:number; required?:boolean }

export type LocalizationSourceConfig = {
  id:string
  path:string
  type?:'directory'|'repository'|'knowledge'
  readOnly?:boolean
}

export type ModificationWorkspaceConfig = {
  id:string
  path:string
  vcsKind?:VcsKind
  hostingKind?:HostingKind
  repositoryRoot?:string
  remoteUrl?:string
  allowedRoots?:string[]
  deniedRoots?:string[]
  allowedExtensions?:string[]
}

export type PatchActionConfig = { id:string; type:'patch'; outputDirectory?:string; filenameTemplate?:string; overwrite?:boolean; required?:boolean }
export type GitLabMrActionConfig = { id:string; type:'gitlabMr'; targetBranches:string[]; titleTemplate?:string; descriptionTemplate?:string; required?:boolean }
export type GitHubPrActionConfig = { id:string; type:'githubPr'; targetBranches:string[]; titleTemplate?:string; descriptionTemplate?:string; required?:boolean }
export type FinalActionConfig = PatchActionConfig | GitLabMrActionConfig | GitHubPrActionConfig

export type AppConfig = {
  schemaVersion:number
  server:{host:string;port:number}
  storage:{dataRoot:string}
  execution:{mode:ExecutionMode;currentModelId:string;maxConcurrentTasks:number;maxConcurrentLlmCalls:number;baselineCohortWindowMs:number;maxRepairAttempts:number}
  executableBindings:Record<string,ExecutableBinding>
  ticketProviders:TicketProviderConfig[]
  agentProfiles:AgentProfileConfig[]
  knowledgeProviders:Array<Record<string,unknown>&{id?:string}>
  projects:ProjectConfig[]
}

export type ProjectConfig = {
  id:string
  name?:string
  enabled?:boolean
  routingRules?:RoutingRule[]
  localizationSource?:LocalizationSourceConfig
  modificationWorkspace?:ModificationWorkspaceConfig
  verification?:{timeoutSeconds?:number;steps?:VerificationStepConfig[];allowNoAutomatedTests?:boolean;reason?:string}
  finalActions?:FinalActionConfig[]
}

export type SettingsResponse={config:AppConfig;secrets:Record<string,{configured:boolean}>;etag:string}
export type PreflightCheck={id:string;status:'ready'|'warning'|'failed';summary:string;detail?:unknown;suggestion?:string}
export type PreflightResult={projectId:string;ready:boolean;status:'ready'|'not_ready';checks:PreflightCheck[]}
export type ReadinessCheck={id:string;status:'ready'|'warning'|'failed'|'inactive';summary:string;detail?:unknown;suggestion?:string;dependencyId?:string;required?:boolean;command?:string;path?:string;version?:string|null}
export type ReadinessResponse={ready:boolean;status:'ready'|'warning'|'not_ready';checks:ReadinessCheck[];environment:string}
export type WorkspaceDetection={
  path:string
  ready:boolean
  vcsKind:VcsKind
  hostingKind:HostingKind
  repositoryRoot?:string
  remoteUrl?:string
  summary:string
  checks:Array<{id:string;status:'ready'|'warning'|'failed';summary:string;detail?:unknown}>
}
