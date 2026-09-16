/**
 * 对话发送与 SSE 消费流程（D1 拆分第 4 步，todo §8.4/§8.3）。
 * 状态在 stores/chat.ts；本 composable 负责：附件上传 → 消息种子 →
 * 流式消费（打字机上屏）→ 首 token 超时 → 错误归类，并在宿主组件卸载时清理计时器。
 */
import { onBeforeUnmount } from 'vue'
import { ElMessage } from '@/utils/toast'
import {
  getAgentHistory,
  streamAgentChat,
  uploadAgentDocument,
  waitForAgentJob,
  type AgentAttachmentItem,
  type AgentHistoryItem,
} from '@/serve/agent'
import { createTypewriter } from '@/utils/typewriter'
import { cloneAttachmentForMessage, hydrateAttachmentFromPayload } from '@/utils/attachment'
import { useChatStore, type AgentMessage } from '@/stores/chat'
import { useProjectStore } from '@/stores/project'
import { useTaskStore } from '@/stores/tasks'
import { useWorkflowStore } from '@/stores/workflow'
import type { WorkflowDraft } from '@/serve/workflow'

const AGENT_FIRST_TOKEN_TIMEOUT_MS = 10000
// 防卡死看门狗：首个事件到达后，任何事件（content/tool/snapshot/done）
// 都会重置 60s 计时；超时就主动中断并给用户一句明确的错误结果。
const AGENT_STREAM_IDLE_TIMEOUT_MS = 60000

interface UseAgentChatOptions {
  /** 消息有更新时由宿主组件滚动到底部 */
  scrollToBottom: () => void | Promise<void>
}

export function useAgentChat(options: UseAgentChatOptions) {
  const chatStore = useChatStore()
  const projectStore = useProjectStore()
  const taskStore = useTaskStore()
  const workflowStore = useWorkflowStore()

  let thinkingTimer: number | null = null
  let firstTokenTimeout: number | null = null
  let streamIdleTimeout: number | null = null

  function startThinking() {
    stopThinking()
    chatStore.hasAgentStartedReplying = false
    chatStore.thinkingSeconds = 0
    thinkingTimer = window.setInterval(() => {
      chatStore.thinkingSeconds += 1
    }, 1000)
  }

  function stopThinking() {
    chatStore.hasAgentStartedReplying = false
    chatStore.thinkingSeconds = 0
    if (thinkingTimer !== null) {
      window.clearInterval(thinkingTimer)
      thinkingTimer = null
    }
    clearFirstTokenTimeout()
  }

  function clearFirstTokenTimeout() {
    if (firstTokenTimeout !== null) {
      window.clearTimeout(firstTokenTimeout)
      firstTokenTimeout = null
    }
  }

  function clearStreamIdleTimeout() {
    if (streamIdleTimeout !== null) {
      window.clearTimeout(streamIdleTimeout)
      streamIdleTimeout = null
    }
  }

  /** 每个 SSE 事件都要叫一次；60s 内没有新事件视为上游卡死，主动中断。 */
  function armStreamIdleTimeout(controller: AbortController) {
    clearStreamIdleTimeout()
    streamIdleTimeout = window.setTimeout(() => {
      controller.abort('STREAM_IDLE_TIMEOUT')
    }, AGENT_STREAM_IDLE_TIMEOUT_MS)
  }

  function hydrateHistoryItem(item: AgentHistoryItem): AgentMessage {
    return {
      id: chatStore.nextMessageId(),
      role: item.role,
      content: item.content,
      attachments: item.attachments?.map(hydrateAttachmentFromPayload),
      citations: item.citations,
    }
  }

  /** 按当前项目加载服务端历史；令牌与项目双重校验，忽略迟到响应 */
  async function loadHistory() {
    const token = chatStore.nextLoadToken()
    const targetProjectId = projectStore.id
    const history = await getAgentHistory(targetProjectId)
    if (!chatStore.isCurrentLoadToken(token) || targetProjectId !== projectStore.id) {
      return false
    }
    chatStore.setMessagesFromHistory(history, hydrateHistoryItem)
    void options.scrollToBottom()
    return true
  }

  async function sendMessage() {
    const message = chatStore.draft.trim()
    const pendingAttachments = [...chatStore.uploadedAttachments]
    if (
      (!message && !pendingAttachments.length) ||
      chatStore.isSending ||
      chatStore.isUploadingAttachment
    ) {
      return
    }

    const attachmentPayloads: AgentAttachmentItem[] = []
    if (pendingAttachments.length) {
      if (projectStore.id == null) {
        ElMessage.warning('请先进入一个工程，再发送带附件的消息')
        return
      }

      chatStore.isUploadingAttachment = true
      try {
        for (const attachment of pendingAttachments) {
          if (!attachment.file) continue
          const result = await uploadAgentDocument(attachment.file, projectStore.id)
          if (result.status !== 'accepted' && result.status !== 'success') {
            throw new Error(result.message || `附件上传失败：${attachment.name}`)
          }
          if (result.job) {
            await waitForAgentJob(result.job.id)
          }
          attachmentPayloads.push({
            name: attachment.name,
            kind: attachment.kind,
            badge: attachment.badge,
            meta: attachment.meta,
          })
        }
        void taskStore.load(projectStore.id)
      } catch (error) {
        const errorMessage = error instanceof Error ? error.message : '附件发送失败'
        ElMessage.error(errorMessage)
        chatStore.isUploadingAttachment = false
        return
      }
      chatStore.isUploadingAttachment = false
    }

    const userMessage: AgentMessage = {
      id: chatStore.nextMessageId(),
      role: 'user',
      content: message || '已发送附件',
      attachments: pendingAttachments.map(cloneAttachmentForMessage),
    }
    const assistantMessageSeed: AgentMessage = {
      id: chatStore.nextMessageId(),
      role: 'assistant',
      content: '',
      toolName: null,
      isPending: true,
    }

    chatStore.messages = [...chatStore.messages, userMessage, assistantMessageSeed]
    // 流式回调必须改数组里的响应式代理对象；直接改 seed 原始对象绕过 Vue 响应式（B1 教训）
    const assistantMessage = chatStore.messages[chatStore.messages.length - 1]
    // token 是一簇一簇到达的，经打字机缓冲后按帧匀速上屏，消除跳字感
    const typewriter = createTypewriter((text) => {
      if (assistantMessage.isPending) {
        assistantMessage.isPending = false
      }
      assistantMessage.content += text
      void options.scrollToBottom()
    })

    chatStore.draft = ''
    chatStore.clearUploadedAttachments()
    chatStore.isSending = true
    chatStore.activeToolName = ''
    startThinking()

    const controller = new AbortController()
    chatStore.abortController = controller
    firstTokenTimeout = window.setTimeout(() => {
      if (!chatStore.hasAgentStartedReplying) {
        controller.abort('FIRST_TOKEN_TIMEOUT')
      }
    }, AGENT_FIRST_TOKEN_TIMEOUT_MS)
    armStreamIdleTimeout(controller)
    await options.scrollToBottom()

    try {
      await streamAgentChat(
        {
          message,
          project_id: projectStore.id,
          attachments: attachmentPayloads,
        },
        {
          onTool(event) {
            clearFirstTokenTimeout()
            armStreamIdleTimeout(controller)
            chatStore.activeToolName = event.tool_name
            assistantMessage.toolName = event.tool_name
            void options.scrollToBottom()
          },
          onContent(event) {
            clearFirstTokenTimeout()
            armStreamIdleTimeout(controller)
            if (!chatStore.hasAgentStartedReplying) {
              chatStore.hasAgentStartedReplying = true
            }
            typewriter.push(event.content)
          },
          onWorkflowSnapshot(event) {
            armStreamIdleTimeout(controller)
            // AI 通过后端的 Workflow 命令改动画布：把 Draft 快照交给 workflow store，
            // 同时桥接成左侧 Block 实例，参数/结果/状态与画布节点同步。
            workflowStore.applyWorkflowSnapshot(event.snapshot as WorkflowDraft)
          },
          async onDone(event) {
            clearStreamIdleTimeout()
            // 等缓冲吐完再用服务端历史整体替换消息列表，避免文字瞬间跳到全量
            await typewriter.finish()
            chatStore.activeToolName = ''
            chatStore.setMessagesFromHistory(event.history, hydrateHistoryItem)
            void options.scrollToBottom()
          },
        },
        controller.signal,
      )
    } catch (error) {
      typewriter.cancel()

      // 切换项目导致的取消：直接静默返回，消息列表随新项目历史重建（§8.3）
      if (controller.signal.aborted && controller.signal.reason === 'PROJECT_SWITCH') {
        return
      }

      const isFirstTokenTimeout =
        controller.signal.aborted && controller.signal.reason === 'FIRST_TOKEN_TIMEOUT'
      const isStreamIdleTimeout =
        controller.signal.aborted && controller.signal.reason === 'STREAM_IDLE_TIMEOUT'
      assistantMessage.isPending = false
      assistantMessage.isError = true
      assistantMessage.toolName = null
      assistantMessage.content = isFirstTokenTimeout
        ? '10 秒内未收到模型返回，已自动暂停本次响应。请检查后端日志、接口耗时或重试。'
        : isStreamIdleTimeout
          ? '超过 60 秒没有新的响应，已自动中断（可能是上游模型或工具卡住）。请重试。'
          : error instanceof Error
            ? error.message
            : 'Neyria 响应失败'
      ElMessage.error(
        isFirstTokenTimeout
          ? '10 秒内未收到模型返回，已自动暂停'
          : isStreamIdleTimeout
            ? '响应超时，已自动中断'
            : assistantMessage.content,
      )
      clearStreamIdleTimeout()
      await options.scrollToBottom()
    } finally {
      clearStreamIdleTimeout()
      chatStore.isSending = false
      chatStore.isUploadingAttachment = false
      chatStore.activeToolName = ''
      stopThinking()
      if (chatStore.abortController === controller) {
        chatStore.abortController = null
      }
    }
  }

  onBeforeUnmount(() => {
    stopThinking()
  })

  return {
    sendMessage,
    loadHistory,
  }
}
