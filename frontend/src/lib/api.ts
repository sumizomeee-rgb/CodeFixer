import type { ExecutionMode, PreflightResult, ProjectConfig, ProviderVersion, ReadinessResponse, SettingsResponse, TicketProviderConfig, WorkspaceDetection, WorkspaceLocationType } from '../entities/config'
import type { DashboardData, TaskRecord } from '../entities/task'

export class ApiError extends Error { status:number; code:string; constructor(status:number,code:string,message:string){super(message);this.status=status;this.code=code} }
async function request<T>(path:string,init?:RequestInit):Promise<T>{const response=await fetch(path,{...init,headers:{'Content-Type':'application/json',...(init?.headers??{})}});if(!response.ok){const payload=await response.json().catch(()=>null);const error=payload?.error??payload?.detail??{};throw new ApiError(response.status,error.code??'request_failed',error.message??error.reason??`HTTP ${response.status}`)}return response.json() as Promise<T>}
export const api={
  health:()=>request<{status:string;service:string;version:string}>('/api/health'),
  readiness:()=>request<ReadinessResponse>('/api/readiness'),
  dashboard:()=>request<DashboardData>('/api/dashboard'),
  settings:()=>request<SettingsResponse>('/api/settings'),
  putSettings:(config:SettingsResponse['config'],etag:string)=>request<SettingsResponse>('/api/settings',{method:'PUT',headers:{'If-Match':etag},body:JSON.stringify(config)}),
  setExecutionMode:(mode:ExecutionMode,etag:string)=>request<{mode:ExecutionMode;etag:string}>('/api/settings/execution-mode',{method:'PUT',headers:{'If-Match':etag},body:JSON.stringify({mode})}),
  projects:()=>request<{items:ProjectConfig[];etag:string}>('/api/projects'),
  createProject:(project:ProjectConfig,etag:string)=>request<{project:ProjectConfig;etag:string}>('/api/projects',{method:'POST',headers:{'If-Match':etag},body:JSON.stringify(project)}),
  updateProject:(projectId:string,project:ProjectConfig,etag:string)=>request<{project:ProjectConfig;etag:string}>(`/api/projects/${encodeURIComponent(projectId)}`,{method:'PUT',headers:{'If-Match':etag},body:JSON.stringify(project)}),
  setProjectEnabled:(projectId:string,enabled:boolean,etag:string)=>request<{project:ProjectConfig;etag:string}>(`/api/projects/${encodeURIComponent(projectId)}/enabled`,{method:'PUT',headers:{'If-Match':etag},body:JSON.stringify({enabled})}),
  detectWorkspace:(locationType:WorkspaceLocationType,location:string)=>request<WorkspaceDetection>('/api/workspaces/detect',{method:'POST',body:JSON.stringify({locationType,location})}),
  preflight:(projectId:string)=>request<PreflightResult>(`/api/projects/${encodeURIComponent(projectId)}/preflight`,{method:'POST'}),
  providers:()=>request<{items:Array<Record<string,unknown>&{id?:string;type?:string;enabled?:boolean}>}>('/api/providers'),
  createProvider:(provider:Omit<TicketProviderConfig,'id'>,secrets:Record<string,string>,etag:string)=>request<{provider:TicketProviderConfig;etag:string}>('/api/providers',{method:'POST',headers:{'If-Match':etag},body:JSON.stringify({provider,secrets})}),
  updateProvider:(id:string,provider:TicketProviderConfig,secrets:Record<string,string>,etag:string)=>request<{provider:TicketProviderConfig;etag:string}>(`/api/providers/${encodeURIComponent(id)}`,{method:'PUT',headers:{'If-Match':etag},body:JSON.stringify({provider,secrets})}),
  testProvider:(id:string)=>request<Record<string,unknown>>(`/api/providers/${encodeURIComponent(id)}/test`,{method:'POST'}),
  providerVersions:(id:string)=>request<{providerId:string;items:ProviderVersion[]}>(`/api/providers/${encodeURIComponent(id)}/versions`),
  tasks:()=>request<{items:TaskRecord[]}>('/api/tasks'),
  task:(id:string)=>request<TaskRecord>(`/api/tasks/${encodeURIComponent(id)}`),
  startTask:(id:string)=>request<TaskRecord>(`/api/tasks/${encodeURIComponent(id)}/start`,{method:'POST'}),
  cancelTask:(id:string)=>request<TaskRecord>(`/api/tasks/${encodeURIComponent(id)}/cancel`,{method:'POST'}),
  retryDelivery:(id:string)=>request<TaskRecord>(`/api/tasks/${encodeURIComponent(id)}/retry-delivery`,{method:'POST'}),
  setSecret:(key:string,value:string)=>request<{key:string;configured:boolean}>(`/api/secrets/${encodeURIComponent(key)}`,{method:'PUT',body:JSON.stringify({value})}),
}
