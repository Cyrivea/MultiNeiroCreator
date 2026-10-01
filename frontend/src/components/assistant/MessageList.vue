<template>
  <div v-if="!chatStore.messages.length" class="agent-empty">
    <div class="agent-empty-orbit" aria-hidden="true"></div>
    <div class="agent-empty-title">Neyria 已就绪</div>
    <div class="agent-empty-meta">现在可以直接描述你的创作目标、风格、结构或具体问题。</div>
    <div class="agent-empty-suggestions" role="list">
      <button
        v-for="suggestion in emptySuggestions"
        :key="suggestion"
        type="button"
        class="agent-empty-suggestion"
        @click="applySuggestion(suggestion)"
      >
        {{ suggestion }}
      </button>
    </div>
  </div>

  <TransitionGroup v-else name="agent-message-float" tag="div" class="agent-message-list">
    <template v-for="message in visibleMessages" :key="message.id">
      <!-- 系统通知（如工作流完成/失败）：居中腹带提示，不走对话气泡 -->
      <div
        v-if="message.role === 'system-notice'"
        :key="`notice-${message.id}`"
        class="agent-message is-system-notice"
      >
        <div class="agent-system-notice-pill">{{ message.content }}</div>
      </div>
      <div
        v-else
        :key="message.id"
        class="agent-message"
        :class="[`is-${message.role}`, { 'is-error': message.isError }]"
      >
        <div class="agent-message-meta">
          <div v-if="message.toolName" class="agent-tool-chip">
            {{ formatToolName(message.toolName) }}
          </div>
        </div>
        <div
          class="agent-message-bubble"
          :class="{ 'is-pending': message.isPending && !message.content }"
        >
          <template v-if="message.isPending && !message.content">
            <span class="agent-thinking-wave" aria-label="Thinking">
              <span
                v-for="(letter, index) in thinkingLetters"
                :key="`${message.id}-${index}`"
                class="agent-thinking-letter"
                :style="{ animationDelay: `${index * 0.06}s` }"
              >
                {{ letter }}
              </span>
            </span>
          </template>
          <template v-else>
            <!-- 用户消息保持纯文本；助手消息走 Markdown 消毒管线（UI1） -->
            <MarkdownBlock v-if="message.role === 'assistant'" :content="message.content" />
            <template v-else>{{ message.content }}</template>
          </template>
          <span v-if="message.interrupted" class="agent-interrupted-mark" title="生成中途被断开">
            （回复被中断，内容不完整）
          </span>
        </div>
        <div v-if="message.citations?.length" class="agent-message-citations">
          <div class="agent-citation-title">引用来源</div>
          <div
            v-for="(citation, index) in message.citations"
            :key="`${message.id}-citation-${citation.document_id || citation.source}-${citation.chunk_index}-${index}`"
            class="agent-citation-item"
          >
            <span class="agent-citation-source">{{ citation.source }}</span>
            <span>· 片段 {{ citation.chunk_index + 1 }}</span>
          </div>
        </div>
        <!-- open-webui 设计：助手消息 hover 时浮出操作栏；复制器输出原文，重新生成只挂最新一轮 -->
        <div
          v-if="message.role === 'assistant' && !message.isPending && message.content"
          class="agent-message-actions"
        >
          <button
            type="button"
            class="agent-action-btn"
            :title="copiedMessageId === message.id ? '已复制' : '复制回复'"
            @click="copyMessageContent(message)"
          >
            <svg
              v-if="copiedMessageId !== message.id"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="1.8"
              stroke-linecap="round"
              stroke-linejoin="round"
              aria-hidden="true"
            >
              <rect x="9" y="9" width="11" height="11" rx="2" />
              <path d="M5 15V5a2 2 0 0 1 2-2h10" />
            </svg>
            <svg
              v-else
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
              stroke-linejoin="round"
              aria-hidden="true"
            >
              <path d="M20 6 9 17l-5-5" />
            </svg>
          </button>
          <button
            v-if="isLastAssistantMessage(message)"
            type="button"
            class="agent-action-btn"
            title="重新生成"
            :disabled="chatStore.isSending"
            @click="emit('regenerate')"
          >
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="1.8"
              stroke-linecap="round"
              stroke-linejoin="round"
              aria-hidden="true"
            >
              <path d="M21 4v6h-6" />
              <path d="M21 10a9 9 0 1 1-2.64-6.36L21 6.5"/>
            </svg>
          </button>
        </div>
        <div v-if="message.attachments?.length" class="agent-message-attachments">
          <article
            v-for="attachment in message.attachments"
            :key="`${message.id}-${attachment.id}`"
            class="message-attachment-chip"
            :class="[`is-${attachment.kind}`]"
          >
            <template v-if="attachment.kind === 'image' && attachment.previewUrl">
              <img
                class="message-attachment-image"
                :src="attachment.previewUrl"
                :alt="attachment.name"
              />
            </template>
            <template v-else>
              <div class="message-attachment-icon" aria-hidden="true">{{ attachment.badge }}</div>
            </template>
            <div class="message-attachment-copy">
              <div class="message-attachment-name">{{ attachment.name }}</div>
              <div class="message-attachment-meta">{{ attachment.meta }}</div>
            </div>
          </article>
        </div>
      </div>
    </template>
  </TransitionGroup>
</template>

<script setup lang="ts">
// 消息列表（D1 拆分第 7 步，todo §8.4）：纯展示，数据来自 chat store。
import { computed, ref } from 'vue'
import { ElMessage } from '@/utils/toast'
import { formatToolName, useChatStore, type AgentMessage } from '@/stores/chat'
import MarkdownBlock from './MarkdownBlock.vue'

const emit = defineEmits<{ (e: 'regenerate'): void }>()

const chatStore = useChatStore()
const thinkingLetters = 'THINKING'.split('')
const copiedMessageId = ref<string | null>(null)
let copiedTimer: number | null = null

// 空状态建议词条：借机把三大 Block 的生产能力前置到第一屏（open-webui Suggestions 设计）
const emptySuggestions = [
  '写一首关于「雨夜霓虹」的 cyberpop 歌词，两段主歌一次副歌',
  '帮我把「歌词 → 封面图」的工作流搭好，参数配好先别运行',
  '生成一张 16:9 的赛博朋克风专辑封面图',
  '跑一遍当前工作流，完事了告诉我结果',
]

function applySuggestion(text: string) {
  chatStore.draft = text
}

/** 仅允许对最新一条回复重新生成（后端按尾轮截断，中间消息重生成会导致上下文漂移） */
function isLastAssistantMessage(message: AgentMessage) {
  for (let i = visibleMessages.value.length - 1; i >= 0; i--) {
    const item = visibleMessages.value[i]
    if (item.role === 'assistant') return item.id === message.id
  }
  return false
}

async function copyMessageContent(message: AgentMessage) {
  try {
    await navigator.clipboard.writeText(message.content)
  } catch {
    ElMessage.error('复制失败，请检查浏览器剪贴板权限')
    return
  }
  copiedMessageId.value = message.id
  if (copiedTimer !== null) window.clearTimeout(copiedTimer)
  copiedTimer = window.setTimeout(() => {
    copiedMessageId.value = null
    copiedTimer = null
  }, 1500)
}

// 空气泡防御：历史里可能存在早期遗留的空 assistant 消息（模型只调工具未说话的年代），
// 已读过且既无内容又无工具标记的一律不渲染。
const visibleMessages = computed(() =>
  chatStore.messages.filter(
    (message) =>
      !(
        message.role === 'assistant' &&
        !message.isPending &&
        !message.isError &&
        !message.content?.trim() &&
        !message.toolName
      ),
  ),
)
</script>

<style scoped>
.agent-empty {
  min-height: 100%;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  gap: 6px;
  padding: 20px 14px;
  text-align: center;
}

.agent-empty-orbit {
  width: 60px;
  height: 60px;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  position: relative;
  background: radial-gradient(circle, rgba(255, 255, 255, 0.06), transparent 62%);
}

.agent-empty-orbit::before,
.agent-empty-orbit::after {
  content: '';
  position: absolute;
  inset: 9px;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.06);
}

.agent-empty-orbit::after {
  inset: -1px;
  border-top-color: rgba(255, 255, 255, 0.36);
  border-right-color: transparent;
  border-bottom-color: transparent;
  border-left-color: transparent;
  animation: agent-empty-orbit-spin 5s linear infinite;
}

.agent-empty-title {
  color: var(--text-secondary);
  font-size: 14px;
  font-weight: 400;
}

.agent-empty-meta {
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.6;
  max-width: 268px;
}

.agent-message-list {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding-bottom: 12px;
  min-height: min-content;
  position: relative;
  z-index: 1;
}

.agent-message {
  display: flex;
  flex-direction: column;
  gap: 6px;
  will-change: transform, opacity, filter;
}

.agent-message.is-user {
  align-items: flex-end;
}

.agent-message.is-assistant,
.agent-message.is-error {
  align-items: flex-start;
}

/* B28：后台任务终态的系统通知（工作流完成/失败），居中腹带提示 */
.agent-message.is-system-notice {
  align-items: center;
}

.agent-system-notice-pill {
  max-width: 92%;
  padding: 6px 14px;
  border-radius: 999px;
  font-size: 12px;
  line-height: 1.6;
  text-align: center;
  color: var(--text-secondary, rgba(255, 255, 255, 0.62));
  background: rgba(122, 162, 255, 0.08);
  border: 1px solid rgba(122, 162, 255, 0.18);
}

.agent-message-meta {
  min-height: 16px;
  display: flex;
  align-items: center;
}

.agent-message-bubble {
  max-width: min(92%, 100%);
  padding: 11px 13px;
  border-radius: 18px;
  border: 1px solid rgba(255, 255, 255, 0.06);
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.045), rgba(255, 255, 255, 0.022)),
    rgba(255, 255, 255, 0.02);
  color: var(--text-primary);
  font-size: 14px;
  line-height: 1.65;
  white-space: pre-wrap;
  word-break: break-word;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.03);
  transition:
    transform 220ms cubic-bezier(0.22, 1, 0.36, 1),
    border-color 180ms ease,
    background 180ms ease,
    box-shadow 180ms ease;
}

.agent-message-bubble:hover {
  transform: translateY(-1px);
  border-color: rgba(255, 255, 255, 0.09);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.04),
    0 10px 24px rgba(0, 0, 0, 0.16);
}

.agent-interrupted-mark {
  display: block;
  margin-top: 6px;
  font-size: 10px;
  color: #f0a860;
}

.agent-message-bubble.is-pending {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  min-width: 132px;
  min-height: 48px;
  padding-inline: 14px;
}

.agent-thinking-wave {
  display: inline-flex;
  align-items: center;
  gap: 1px;
}

.agent-thinking-letter {
  display: inline-block;
  color: rgba(255, 255, 255, 0.86);
  font-size: 11px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  animation: thinking-letter-wave 1.28s ease-in-out infinite;
  will-change: transform, opacity;
}

/* ------- 悬停操作栏（open-webui 设计） ------- */
.agent-message-actions {
  display: flex;
  gap: 4px;
  opacity: 0;
  transform: translateY(-2px);
  transition:
    opacity 160ms ease,
    transform 160ms ease;
  pointer-events: none;
}

.agent-message:hover .agent-message-actions,
.agent-message-actions:focus-within {
  opacity: 1;
  transform: translateY(0);
  pointer-events: auto;
}

.agent-action-btn {
  width: 26px;
  height: 26px;
  display: grid;
  place-items: center;
  border-radius: 8px;
  color: var(--text-secondary);
  background: transparent;
  border: 1px solid transparent;
  cursor: pointer;
  transition:
    background 150ms ease,
    color 150ms ease;
}

.agent-action-btn:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.08);
  color: var(--text-primary);
}

.agent-action-btn:disabled {
  opacity: 0.45;
  cursor: default;
}

.agent-action-btn svg {
  width: 14px;
  height: 14px;
}

/* ------- 空状态建议词条 ------- */
.agent-empty-suggestions {
  margin-top: 16px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;
  max-width: 340px;
}

.agent-empty-suggestion {
  padding: 9px 14px;
  border-radius: 14px;
  text-align: left;
  font-size: 12.5px;
  line-height: 1.55;
  color: var(--text-secondary);
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.07);
  cursor: pointer;
  transition:
    background 160ms ease,
    color 160ms ease,
    border-color 160ms ease,
    transform 160ms ease;
}

.agent-empty-suggestion:hover {
  background: rgba(255, 255, 255, 0.07);
  border-color: rgba(255, 255, 255, 0.12);
  color: var(--text-primary);
  transform: translateY(-1px);
}

.agent-message.is-user .agent-message-bubble {
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.075), rgba(255, 255, 255, 0.05)),
    rgba(255, 255, 255, 0.035);
  border-color: rgba(255, 255, 255, 0.09);
}

.agent-message.is-error .agent-message-bubble {
  border-color: rgba(173, 72, 72, 0.24);
  background: rgba(143, 45, 45, 0.1);
  color: #f0d8d8;
}

.agent-message-citations {
  display: flex;
  flex-direction: column;
  gap: 3px;
  max-width: min(92%, 100%);
  padding: 7px 10px;
  border-left: 2px solid rgba(167, 139, 250, 0.45);
  color: var(--text-secondary);
  font-size: 11px;
  line-height: 1.45;
}

.agent-citation-title {
  color: rgba(196, 181, 253, 0.9);
  font-size: 10px;
  letter-spacing: 0.08em;
}

.agent-citation-item {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.agent-citation-source {
  color: var(--text-primary);
}

.agent-message-attachments {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-width: min(92%, 100%);
}

.message-attachment-chip {
  min-width: 0;
  max-width: 100%;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 16px;
  border: 1px solid rgba(255, 255, 255, 0.06) !important;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.04), rgba(255, 255, 255, 0.018)),
    rgba(255, 255, 255, 0.02);
}

.agent-message.is-user .message-attachment-chip {
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.065), rgba(255, 255, 255, 0.028)),
    rgba(255, 255, 255, 0.026);
}

.message-attachment-chip.is-image {
  align-items: stretch;
}

.message-attachment-image,
.message-attachment-icon {
  flex: 0 0 auto;
}

.message-attachment-image {
  width: 42px;
  height: 42px;
  border-radius: 12px;
  object-fit: cover;
  filter: grayscale(1);
}

.message-attachment-icon {
  width: 42px;
  height: 42px;
  border-radius: 12px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid rgba(255, 255, 255, 0.08);
  color: rgba(255, 255, 255, 0.88);
  font-size: 10px;
  letter-spacing: 0.08em;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.08), rgba(255, 255, 255, 0.03)),
    rgba(255, 255, 255, 0.03);
}

.message-attachment-copy {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.message-attachment-name {
  color: var(--text-primary);
  font-size: 12px;
  line-height: 1.45;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.message-attachment-meta {
  color: var(--text-secondary);
  font-size: 11px;
  line-height: 1.4;
}

.agent-tool-chip {
  color: var(--text-secondary);
  font-size: 12px;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 0 1px;
  text-transform: uppercase;
  letter-spacing: 0.06em;
}

.agent-tool-chip::before {
  content: '';
  width: 5px;
  height: 5px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.42);
}

@keyframes agent-empty-orbit-spin {
  from {
    transform: rotate(0deg);
  }

  to {
    transform: rotate(360deg);
  }
}

@keyframes thinking-letter-wave {
  0%,
  100% {
    opacity: 0.28;
    transform: translateY(0);
  }

  35% {
    opacity: 1;
    transform: translateY(-3px);
  }

  60% {
    opacity: 0.7;
    transform: translateY(1px);
  }
}

.agent-message-float-enter-active,
.agent-message-float-leave-active {
  transition:
    opacity 320ms cubic-bezier(0.16, 1, 0.3, 1),
    transform 320ms cubic-bezier(0.16, 1, 0.3, 1),
    filter 320ms cubic-bezier(0.16, 1, 0.3, 1);
}

.agent-message-float-enter-from,
.agent-message-float-leave-to {
  opacity: 0;
  transform: translateY(10px) scale(0.985);
  filter: blur(6px);
}

.agent-message-float-enter-to,
.agent-message-float-leave-from {
  opacity: 1;
  transform: translateY(0) scale(1);
  filter: blur(0);
}

@media (max-width: 1480px) {
  .agent-message-bubble {
    max-width: 100%;
  }
}

@media (max-width: 1320px) {
  .agent-empty-meta,
  .agent-message-bubble {
    font-size: 13px;
  }
}
</style>
