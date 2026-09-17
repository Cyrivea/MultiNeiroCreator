/**
 * 会话状态唯一真源（D2，todo §8.3）。
 * Store 管理 messages / sending / tool state / 附件 / abort controller；
 * 发送与 SSE 消费流程在 composables/useAgentChat.ts；组件只负责展示和用户操作。
 */
import { computed, ref, shallowRef } from 'vue'
import { defineStore } from 'pinia'
import type { AgentCitation, AgentHistoryItem } from '@/serve/agent'
import {
  buildUploadedAttachment,
  revokeAttachmentPreview,
  type UploadedAttachment,
} from '@/utils/attachment'

export interface AgentMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  toolName?: string | null
  isError?: boolean
  isPending?: boolean
  attachments?: UploadedAttachment[]
  citations?: AgentCitation[]
  interrupted?: boolean
}

export function formatToolName(toolName: string) {
  const toolMap: Record<string, string> = {
    calculate: '计算工具',
    get_current_time: '时间工具',
    search_web: '联网搜索',
    generate_lyrics_block: '歌词生成',
    configure_lyrics_workflow: '歌词工作流',
    run_current_workflow: '运行工作流',
  }

  return toolMap[toolName] || toolName
}

export const useChatStore = defineStore('chat', () => {
  const messages = ref<AgentMessage[]>([])
  const uploadedAttachments = ref<UploadedAttachment[]>([])
  const draft = ref('')
  const isSending = ref(false)
  const isUploadingAttachment = ref(false)
  const activeToolName = ref('')
  const hasAgentStartedReplying = ref(false)
  const thinkingSeconds = ref(0)
  const selectedModel = ref('glm-4-flash')
  // 流控制句柄与自增 id 收进 store，消灭模块级 let（重挂载后不再丢状态）
  const abortController = shallowRef<AbortController | null>(null)
  let messageIdSeed = 0
  // 加载令牌：切项目时丢弃迟到的历史响应
  let loadToken = 0

  const hasUploadedAttachments = computed(() => uploadedAttachments.value.length > 0)

  const thinkingStatusText = computed(() => {
    if (!isSending.value) return ''
    if (activeToolName.value) return `正在调用 ${formatToolName(activeToolName.value)}`
    if (hasAgentStartedReplying.value) return `正在输出回复 · 已思考 ${thinkingSeconds.value}s`
    return `正在思考 · 已思考 ${thinkingSeconds.value}s`
  })

  function nextMessageId() {
    return `agent-${messageIdSeed++}`
  }

  function nextLoadToken() {
    return ++loadToken
  }

  function isCurrentLoadToken(token: number) {
    return token === loadToken
  }

  /** 替换消息列表前统一释放消息里的 blob: 预览（solved.md 第 19 条） */
  function clearMessages() {
    for (const message of messages.value) {
      message.attachments?.forEach(revokeAttachmentPreview)
    }
    messages.value = []
  }

  function setMessagesFromHistory(
    history: AgentHistoryItem[],
    hydrate: (item: AgentHistoryItem) => AgentMessage,
  ) {
    clearMessages()
    messages.value = history.map(hydrate)
  }

  function clearUploadedAttachments() {
    uploadedAttachments.value.forEach(revokeAttachmentPreview)
    uploadedAttachments.value = []
  }

  function upsertUploadedAttachment(file: File) {
    const nextAttachment = buildUploadedAttachment(file)
    const existingIndex = uploadedAttachments.value.findIndex(
      (item) => item.name === nextAttachment.name,
    )

    if (existingIndex >= 0) {
      revokeAttachmentPreview(uploadedAttachments.value[existingIndex])
      uploadedAttachments.value.splice(existingIndex, 1, nextAttachment)
      return
    }

    uploadedAttachments.value = [nextAttachment, ...uploadedAttachments.value]
  }

  function removeUploadedAttachment(attachmentId: string) {
    const nextAttachments: UploadedAttachment[] = []
    for (const attachment of uploadedAttachments.value) {
      if (attachment.id === attachmentId) {
        revokeAttachmentPreview(attachment)
        continue
      }
      nextAttachments.push(attachment)
    }
    uploadedAttachments.value = nextAttachments
  }

  function abortActiveStream(reason?: string) {
    abortController.value?.abort(reason)
    abortController.value = null
  }

  /** 切换项目 / 重置面板：取消旧流、清空输入与消息（含 blob 回收） */
  function resetForProjectSwitch() {
    nextLoadToken()
    abortActiveStream('PROJECT_SWITCH')
    isSending.value = false
    isUploadingAttachment.value = false
    hasAgentStartedReplying.value = false
    activeToolName.value = ''
    thinkingSeconds.value = 0
    draft.value = ''
    clearUploadedAttachments()
    clearMessages()
  }

  return {
    messages,
    uploadedAttachments,
    draft,
    isSending,
    isUploadingAttachment,
    activeToolName,
    hasAgentStartedReplying,
    thinkingSeconds,
    selectedModel,
    abortController,
    hasUploadedAttachments,
    thinkingStatusText,
    nextMessageId,
    nextLoadToken,
    isCurrentLoadToken,
    clearMessages,
    setMessagesFromHistory,
    clearUploadedAttachments,
    upsertUploadedAttachment,
    removeUploadedAttachment,
    abortActiveStream,
    resetForProjectSwitch,
  }
})
