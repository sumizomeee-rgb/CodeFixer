export type TaskStatus = 'awaiting_start'|'queued'|'running'|'cancel_requested'|'completed'|'failed'|'canceled'
export type TaskResult = 'changed'|'no_change'|null
export type TaskRun = { id:string; status:string; execution_mode_snapshot:string; created_at:string; started_at?:string|null; finished_at?:string|null }
export type TaskEvent = { id:number; event_type:string; created_at:string; payload:Record<string,unknown> }
export type TaskRecord = {
  id:string; project_id:string; status:TaskStatus; result:TaskResult; provider_instance_id:string; external_ticket_id:string; title:string;
  current_run_id?:string|null; created_at:string; updated_at:string; runs?:TaskRun[]; events?:TaskEvent[]
}
