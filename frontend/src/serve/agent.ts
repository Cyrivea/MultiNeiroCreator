import request from '@/utils/request'
import { API_BASE, TOKEN_KEY } from '@/constants'
import { useUserStore } from '@/stores/user'

export interface AgentAttachmentItem {
  name: string
  kind?: string | null
  badge?: string | null
  meta?: string | null
}

export interface AgentCitation {
  source: string
  document_id: string | null
  chunk_index: number
  chunk_count: number
  distance: number | null
}

export interface AgentHistoryItem {
  role: 'user' | 'assistant' | 'system-notice'
  content: string
  attachments?: AgentAttachmentItem[]
  citations?: AgentCitation[]
  /** 服务端标记：该消息生成中途被断开（上游/客户端中断），可与完整消息区别展示 */
  interrupted?: boolean
}

export interface AgentChatPayload {
  message: string
  // 不再发送 history：对话历史以服务端数据库为唯一真源（A5），由后端按 project_id 重建
  project_id?: number | null
  attachments?: AgentAttachmentItem[]
}

export type JobStatus = 'queued' | 'running' | 'succeeded' | 'failed' | 'cancelled'

export interface JobItem {
  id: string
  type: string
  status: JobStatus
  user_id: number
  project_id: number | null
  payload: Record<string, unknown>
  result: Record<string, unknown> | null
  error: string | null
  progress: number
  progress_message: string | null
  attempts: number
  max_attempts: number
  cancel_requested: boolean
  created_at: string
  started_at: string | null
  finished_at: string | null
}

export type DocumentStatus = 'queued' | 'processing' | 'ready' | 'failed' | 'cancelled' | 'deleted'

export interface AgentDocument {
  id: string
  user_id: number
  project_id: number | null
  filename: string
  status: DocumentStatus
  size_bytes: number
  file_hash: string | null
  chunks_count: number
  error: string | null
  job_id: string | null
  created_at: string
  updated_at: string
  indexed_at: string | null
}

export interface AgentDocumentMutationResponse {
  status: string
  message: string
  document: AgentDocument
  job?: JobItem | null
}

export async function getAgentDocuments(projectId?: number | null) {
  const suffix = projectId != null ? `?project_id=${projectId}` : ''
  return request.get<unknown, AgentDocument[]>(`/documents${suffix}`)
}

export async function getAgentJobs(projectId?: number | null) {
  const suffix = projectId != null ? `?project_id=${projectId}` : ''
  return request.get<unknown, JobItem[]>(`/jobs${suffix}`)
}

export async function getAgentJob(jobId: string) {
  return request.get<unknown, JobItem>(`/jobs/${jobId}`)
}

export async function waitForAgentJob(jobId: string, timeoutMs = 5 * 60 * 1000) {
  const deadline = Date.now() + timeoutMs
  while (Date.now() < deadline) {
    const job = await getAgentJob(jobId)
    if (job.status === 'succeeded') return job
    if (job.status === 'failed' || job.status === 'cancelled') {
      throw new Error(
        job.error || (job.status === 'cancelled' ? '文档索引任务已取消' : '文档索引失败'),
      )
    }
    await new Promise((resolve) => window.setTimeout(resolve, 1000))
  }
  throw new Error('文档索引等待超时，请稍后在后台任务面板查看状态')
}

export async function cancelAgentJob(jobId: string) {
  return request.post<unknown, JobItem>(`/jobs/${jobId}/cancel`)
}

export async function retryAgentJob(jobId: string) {
  return request.post<unknown, JobItem>(`/jobs/${jobId}/retry`)
}

export async function reindexAgentDocument(documentId: string) {
  return request.post<unknown, AgentDocumentMutationResponse>(
    `/documents/reindex?document_id=${encodeURIComponent(documentId)}`,
  )
}

export async function uploadAgentDocument(file: File, projectId?: number | null) {
  const formData = new FormData()
  formData.append('file', file)
  const suffix = projectId != null ? `?project_id=${projectId}` : ''
  return request.post<unknown, AgentDocumentMutationResponse>(`/upload${suffix}`, formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  })
}

export async function deleteAgentDocument(documentId: string, projectId?: number | null) {
  return request.delete<unknown, AgentDocumentMutationResponse>('/documents', {
    data: {
      document_id: documentId,
      project_id: projectId,
    },
  })
}

export interface AgentToolEvent {
  type: 'tool'
  tool_name: string
}

export interface AgentContentEvent {
  type: 'content'
  content: string
}

export interface AgentDoneEvent {
  type: 'done'
  history: AgentHistoryItem[]
  tool_used: string | null
  citations: AgentCitation[]
}

export interface AgentWorkflowSnapshotEvent {
  type: 'workflow_snapshot'
  snapshot: unknown
}

type AgentStreamEvent =
  AgentToolEvent | AgentContentEvent | AgentDoneEvent | AgentWorkflowSnapshotEvent

interface AgentStreamHandlers {
  onTool?: (event: AgentToolEvent) => void
  onContent?: (event: AgentContentEvent) => void
  onDone?: (event: AgentDoneEvent) => void
  onWorkflowSnapshot?: (event: AgentWorkflowSnapshotEvent) => void
}

// 解析单个 SSE 块并分发事件。单行损坏（坏 JSON / 未知类型）只丢弃该行，
// 绝不向上抛异常中断整个流（B4）：已收到的内容和后续 token 必须保住。
function dispatchSseBlock(block: string, handlers: AgentStreamHandlers) {
  const line = block.split('\n').find((item) => item.startsWith('data: '))

  if (!line) return

  const payloadText = line.slice(6).trim()
  if (!payloadText) return

  let event: AgentStreamEvent
  try {
    event = JSON.parse(payloadText) as AgentStreamEvent
  } catch {
    console.warn('[SSE] 丢弃无法解析的数据行:', payloadText.slice(0, 200))
    return
  }

  if (event.type === 'tool') handlers.onTool?.(event)
  else if (event.type === 'content') handlers.onContent?.(event)
  else if (event.type === 'done') handlers.onDone?.(event)
  else if (event.type === 'workflow_snapshot') handlers.onWorkflowSnapshot?.(event)
  else console.warn('[SSE] 忽略未知事件类型:', (event as { type?: string }).type)
}

export const getAgentHistory = (projectId?: number | null) => {
  const suffix = projectId != null ? `?project_id=${projectId}` : ''
  return request.get<unknown, AgentHistoryItem[]>(`/history${suffix}`)
}

export async function streamAgentChat(
  payload: AgentChatPayload,
  handlers: AgentStreamHandlers,
  signal?: AbortSignal,
) {
  const token = localStorage.getItem(TOKEN_KEY)
  const response = await fetch(`${API_BASE}/chat`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(payload),
    signal,
  })

  if (!response.ok) {
    let detail = '请求失败'

    try {
      const data = (await response.json()) as { detail?: string }
      detail = data.detail || detail
    } catch {
      detail = response.statusText || detail
    }

    if (response.status === 401) {
      // 与 utils/request.ts 保持一致：只清用户态，不连坐其他 localStorage 数据
      useUserStore().logout()
      window.location.href = '/login'
    }

    throw new Error(detail)
  }

  if (!response.body) {
    throw new Error('聊天流初始化失败')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buffer = ''

  while (true) {
    const { value, done } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const blocks = buffer.split('\n\n')
    buffer = blocks.pop() || ''

    for (const block of blocks) {
      dispatchSseBlock(block, handlers)
    }
  }

  if (!buffer.trim()) return

  dispatchSseBlock(buffer, handlers)
}
