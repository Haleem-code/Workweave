export type EvidenceReference = { id: string; title: string; source_id: string; location: string; version: string; excerpt: string; current?: boolean }
export type Finding = { id: string; title: string; explanation: string; entity_id: string; owner: string; severity: string; evidence_ids: string[] }
export type GraphPath = { nodes: { id: string; label: string; type: string }[]; edges: { source: string; target: string; label: string }[] }
export type RunStatus = { id: string; query: string; entity_id?: string; status: 'queued'|'running'|'blocked'|'completed'; checkpoint: string; findings: Finding[]; paths: GraphPath[]; evidence_ids?: string[]; answer?: string; error?: string; provider?: string; demo?: boolean; conversation_id: string; created_at: number; events?: { type: string; data: Record<string, unknown>; at: number }[] }
export type Task = { id: string; title: string; owner: string; status: string; run_id: string; description?: string; evidence_ids: string[] }
export type MemoryEntry = { id: string; summary: string; outcome: string; evidence_ids: string[]; created_at: number }
export type Company = { id: string; name: string }
export type Source = { id: string; name: string; version: string; active: boolean; record_count: number; chunk_count: number; embedded_count: number; semantic_status: string; drive_file_id?: string }
export type Mapping = { table: string; entity_type: string; key_column: string; fields: Record<string,string> }
export type Preview = { id: string; filename: string; version: string; warnings: string[]; sections: { location: string; text: string }[]; tables: { name: string; headers: string[]; rows: string[][]; row_count: number; suggested_mapping: Mapping }[] }
export type Profile = { description: string; responsibilities: string; procedure: string; confirmed: boolean; evidence_ids?: string[]; industry?: string; onboarding_step?: 'sources'|'review'|'complete'; products_services?: string; customers?: string; process_flow?: string; dependencies_rules?: string; workflow_priority?: string; data_sources?: string; missing_information?: string }
export type Readiness = { database: {status: string; mode: string; tls: boolean}; platform_admin: boolean }
export type Policy = { allowed: string[]; local_only: boolean; cloud_consent: boolean }
export type ProviderSettings = { policy: Policy; providers: { id: string; label?: string; model: string; ready: boolean; destination: string; disabled: boolean; configuration_warning?: string }[]; private_drive_enabled: boolean }
export type Message = { id: string; role: string; content: string; evidence_ids?: string[]; claims?: {text:string;evidence_ids:string[]}[]; provider?: string }
export class ApiError extends Error {
  constructor(message: string, public status: number) { super(message); this.name = 'ApiError' }
}
export async function api<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
  const response = await fetch('/api/v1' + path, { method, credentials: 'same-origin', headers: body instanceof FormData ? undefined : { 'Content-Type': 'application/json' }, body: body === undefined ? undefined : body instanceof FormData ? body : JSON.stringify(body) })
  if (!response.ok) { const data = await response.json().catch(() => ({})); throw new ApiError(typeof data.detail === 'string' ? data.detail : 'The request could not be completed.', response.status) }
  return response.json()
}


