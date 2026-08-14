export type ExecutionMode = 'automatic' | 'awaitingStart'
export type AgentRuntime = 'claudeCode' | 'codex' | 'opencode'
export type RoutingOperator = 'eq' | 'neq' | 'contains' | 'in' | 'exists'
export type VcsKind = 'git' | 'svn' | 'unknown'
export type HostingKind = 'gitlab' | 'github' | 'other' | 'none' | 'ambiguous'
export type WorkspaceLocationType = 'local' | 'remote'

export type ExecutableBinding = { command?: string[]; versionArgs?: string[]; versionConstraint?: string | null; versionRegex?: string }
export type AgentProfileConfig = { id:string; runtime:AgentRuntime; executableRef:string; model?:string; effort?:string; timeoutSeconds?:number; maxBudgetUsd?:number; extraArgs?:string[] }
export type TicketProviderConfig = Record<string, unknown> & { id:string; name:string; type:'redmine'|'tapd'; enabled?:boolean; pollIntervalSeconds?:number }
export type ProviderVersion = { id:string; name:string }
export type VersionFilter = { mode:'all'|'selected'; versions:ProviderVersion[] }
export type RoutingRule = { id:string; providerRef:string; priority:number; catchAll?:boolean; conditions?:Array<{field:string;operator:RoutingOperator;value?:unknown}>; versionFilter?:VersionFilter }
export type VerificationStepConfig = { id:string; executableRef:string; args:string[]; workingDirectory?:string; timeoutSeconds?:number; required?:boolean }

export type LocalizationSourceConfig = {
  id:string
  path:string
  type?:'directory'|'repository'|'knowledge'
  readOnly?:boolean
}

export type ModificationWorkspaceConfig = {
  id:string
  locationType:WorkspaceLocationType
  localPath?:string
  vcsKind?:VcsKind
  hostingKind?:HostingKind
  remoteUrl?:string
  webBaseUrl?:string
  allowedRoots?:string[]
  deniedRoots?:string[]
  allowedExtensions?:string[]
}

export type PatchActionConfig = { id:string; type:'patch'; outputDirectory?:string; overwrite?:boolean; required?:boolean }
export type GitLabPushActionConfig = { id:string; type:'gitlabPush'; required?:boolean }
export type GitHubPrActionConfig = { id:string; type:'githubPr'; targetBranches:string[]; titleTemplate?:string; descriptionTemplate?:string; required?:boolean }
export type FinalActionConfig = PatchActionConfig | GitLabPushActionConfig | GitHubPrActionConfig
export type DeliveryLogConfig = { technologyTag:string; submitterName:string }

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
  intakeStartedAt?:string
  routingRules?:RoutingRule[]
  localizationSource?:LocalizationSourceConfig
  modificationWorkspace?:ModificationWorkspaceConfig
  verification?:{timeoutSeconds?:number;steps?:VerificationStepConfig[];allowNoAutomatedTests?:boolean;reason?:string}
  deliveryLog?:DeliveryLogConfig
  finalActions?:FinalActionConfig[]
}

export type SettingsResponse={config:AppConfig;secrets:Record<string,{configured:boolean}>;etag:string}
export type PreflightCheck={id:string;status:'ready'|'warning'|'failed';summary:string;detail?:unknown;suggestion?:string}
export type PreflightResult={projectId:string;ready:boolean;status:'ready'|'not_ready';checks:PreflightCheck[]}
export type ReadinessCheck={id:string;status:'ready'|'warning'|'failed'|'inactive';summary:string;detail?:unknown;suggestion?:string;dependencyId?:string;required?:boolean;command?:string;path?:string;version?:string|null}
export type ReadinessResponse={ready:boolean;status:'ready'|'warning'|'not_ready';checks:ReadinessCheck[];environment:string}
export type WorkspaceDetection={
  locationType:WorkspaceLocationType
  location:string
  ready:boolean
  vcsKind:VcsKind
  hostingKind:HostingKind
  repositoryRoot?:string
  remoteUrl?:string
  webBaseUrl?:string
  summary:string
  checks:Array<{id:string;status:'ready'|'warning'|'failed';summary:string;detail?:unknown}>
}
