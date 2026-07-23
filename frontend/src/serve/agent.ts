import request from '@/utils/request'
import { API_BASE, TOKEN_KEY } from '@/constants'

export interface AgentHistoryItem {
  role: 'user' | 'assistant'
  content: string
}

export interface AgentChatPayload {
  message: string
  history: AgentHistoryItem[]
  project_id?: number | null
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
}

type AgentStreamEvent = AgentToolEvent | AgentContentEvent | AgentDoneEvent

export const getAgentHistory = (projectId?: number | null) => {
  const suffix = projectId != null ? `?project_id=${projectId}` : ''
  return request.get<any, AgentHistoryItem[]>(`/history${suffix}`)
}

export async function streamAgentChat(
  payload: AgentChatPayload,
  handlers: {
    onTool?: (event: AgentToolEvent) => void
    onContent?: (event: AgentContentEvent) => void
    onDone?: (event: AgentDoneEvent) => void
  },
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
      localStorage.clear()
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
      const line = block
        .split('\n')
        .find(item => item.startsWith('data: '))

      if (!line) continue

      const payloadText = line.slice(6).trim()
      if (!payloadText) continue

      const event = JSON.parse(payloadText) as AgentStreamEvent

      if (event.type === 'tool') handlers.onTool?.(event)
      if (event.type === 'content') handlers.onContent?.(event)
      if (event.type === 'done') handlers.onDone?.(event)
    }
  }

  if (!buffer.trim()) return

  const line = buffer
    .split('\n')
    .find(item => item.startsWith('data: '))

  if (!line) return

  const payloadText = line.slice(6).trim()
  if (!payloadText) return

  const event = JSON.parse(payloadText) as AgentStreamEvent
  if (event.type === 'tool') handlers.onTool?.(event)
  if (event.type === 'content') handlers.onContent?.(event)
  if (event.type === 'done') handlers.onDone?.(event)
}
