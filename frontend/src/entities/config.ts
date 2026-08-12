export type ExecutionMode = 'automatic' | 'awaitingStart'
export type AgentRuntime = 'claudeCode' | 'codex' | 'opencode'
export type RoutingOperator = 'eq' | 'neq' | 'contains' | 'in' | 'exists'

export type ExecutableBinding = { command?: string[]; versionArgs?: string[]; versionConstraint?: string | null; versionRegex?: string }
export type AgentProfileConfig = { id:string; runtime:AgentRuntime; executableRef:string; model?:string; effort?:string; timeoutSeconds?:number; maxBudgetUsd?:number; extraArgs?:string[] }
export type TicketProviderConfig = Record<string, unknown> & { id:string; type:'redmine'|'tapd'; enabled?:boolean; pollIntervalSeconds?:number }
export type ConnectionConfig = { id:string; type:'gitlab'; baseUrl:string; tokenSecretRef:string }
export type RoutingRule = { id:string; providerRef:string; priority:number; catchAll?:boolean; conditions?:Array<{field:string;operator:RoutingOperator;value?:unknown}> }
export type VerificationStepConfig = { id:string; executableRef:string; args:string[]; workingDirectory?:string; timeoutSeconds?:number; required?:boolean }
export type PatchActionConfig = { id:string; type:'patch'; outputDirectoryRef:string; filenameTemplate?:string; overwrite?:boolean }
export type GitLabMrActionConfig = { id:string; type:'gitlabMr'; connectionRef:string; projectPath:string; materializationRepositoryRef:string; gitExecutableRef?:string; targetBranches:string[]; pathMappings?:Array<{from:string;to:string}>; titleTemplate?:string; descriptionTemplate?:string }
export type FinalActionConfig = PatchActionConfig | GitLabMrActionConfig

export type AppConfig = {
  schemaVersion:number
  server:{host:string;port:number}
  storage:{dataRoot:string}
  execution:{mode:ExecutionMode;maxConcurrentTasks:number;maxRepairAttempts:number}
  pathBindings:Record<string,string>
  executableBindings:Record<string,ExecutableBinding>
  ticketProviders:TicketProviderConfig[]
  agentProfiles:AgentProfileConfig[]
  connections:ConnectionConfig[]
  knowledgeProviders:Array<Record<string,unknown>&{id?:string}>
  projects:ProjectConfig[]
}

export type ProjectConfig = {
  id:string; name?:string; enabled?:boolean; routingRules?:RoutingRule[]
  modificationSource?:{id?:string;type?:'git'|'svn';repositoryRef?:string;executableRef?:string;allowedRoots?:string[];deniedRoots?:string[];allowedExtensions?:string[]}
  agents?:{discovery?:string;repair?:string;review?:string}
  verification?:{timeoutSeconds?:number;steps?:VerificationStepConfig[];allowNoAutomatedTests?:boolean;reason?:string}
  finalActions?:FinalActionConfig[]
}
export type SettingsResponse={config:AppConfig;secrets:Record<string,{configured:boolean}>;etag:string}
export type PreflightCheck={id:string;status:'ready'|'warning'|'failed';summary:string;suggestion?:string}
export type PreflightResult={projectId:string;ready:boolean;status:'ready'|'not_ready';checks:PreflightCheck[]}
