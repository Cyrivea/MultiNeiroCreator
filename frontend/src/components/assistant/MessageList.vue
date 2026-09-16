<template>
  <div v-if="!chatStore.messages.length" class="agent-empty">
    <div class="agent-empty-orbit" aria-hidden="true"></div>
    <div class="agent-empty-title">Neyria 已就绪</div>
    <div class="agent-empty-meta">现在可以直接描述你的创作目标、风格、结构或具体问题。</div>
  </div>

  <TransitionGroup v-else name="agent-message-float" tag="div" class="agent-message-list">
    <div
      v-for="message in visibleMessages"
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
        <template v-else>{{ message.content }}</template>
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
  </TransitionGroup>
</template>

<script setup lang="ts">
// 消息列表（D1 拆分第 7 步，todo §8.4）：纯展示，数据来自 chat store。
import { computed } from 'vue'
import { formatToolName, useChatStore } from '@/stores/chat'

const chatStore = useChatStore()
const thinkingLetters = 'THINKING'.split('')

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
