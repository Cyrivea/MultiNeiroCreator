import request from '@/utils/request'

export type WorkflowRunStatus = 'idle' | 'running' | 'succeeded' | 'failed' | 'model_unavailable'

export interface WorkflowDraftNode {
  id: string
  kind?: 'endpoint' | 'tool'
  endpoint?: 'input' | 'output'
  toolId?: string
  type?: string
  capability_id?: string
  name?: string
  badge?: string
  description?: string
  color?: string
  x?: number
  y?: number
  params?: Record<string, string>
  runStatus?: WorkflowRunStatus
  result?: { format?: string; content?: string } | null
  error?: string | null
}

export interface WorkflowDraft {
  nodes: WorkflowDraftNode[]
  edges: { source: string; target: string }[]
  endpointPositions?: Record<string, { x: number; y: number }>
}

export interface WorkflowDraftResponse {
  id: number | null
  revision: number
  draft: WorkflowDraft
}

export interface WorkflowRunResponse extends WorkflowDraftResponse {
  run_id: string
  status: WorkflowRunStatus
  result: WorkflowDraftNode['result']
  error: string | null
}

export async function getWorkflowDraft(projectId: number | null) {
  const suffix = projectId != null ? `?project_id=${projectId}` : ''
  return request.get<unknown, WorkflowDraftResponse>(`/workflows/draft${suffix}`)
}

export async function saveWorkflowDraft(
  projectId: number | null,
  draft: WorkflowDraft,
  expectedRevision: number,
) {
  return request.put<unknown, WorkflowDraftResponse>('/workflows/draft', {
    project_id: projectId,
    draft,
    expected_revision: expectedRevision,
  })
}

export async function runWorkflow(projectId: number | null) {
  const suffix = projectId != null ? `?project_id=${projectId}` : ''
  return request.post<unknown, WorkflowRunResponse>(`/workflows/run${suffix}`)
}
