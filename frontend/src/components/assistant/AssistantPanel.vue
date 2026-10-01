<template>
  <div class="assistant-panel">
    <div class="assistant-head">
      <div class="assistant-head-top">
        <div class="assistant-head-copy">
          <div class="assistant-title-row">
            <div class="assistant-title">Neyria</div>
            <div class="assistant-presence" aria-hidden="true"></div>
          </div>
          <div class="assistant-meta">为音乐续写篇章</div>
        </div>
        <div class="window-controls" aria-hidden="true">
          <div class="window-dot"></div>
          <div class="window-dot"></div>
          <div class="window-dot"></div>
        </div>
      </div>
      <div class="assistant-head-divider" aria-hidden="true"></div>
    </div>

    <div
      ref="assistantBodyRef"
      class="assistant-body"
      :class="{
        'has-floating-composer': true,
        'has-attachment-dock': chatStore.hasUploadedAttachments,
      }"
    >
      <MessageList @regenerate="handleRegenerate" />

      <div v-if="chatStore.isSending" class="agent-status-line">
        <span class="agent-status-pulse" aria-hidden="true"></span>
        {{ chatStore.thinkingStatusText }}
      </div>
    </div>

    <div
      class="assistant-composer-underlay"
      :class="{ 'has-attachment-dock': chatStore.hasUploadedAttachments }"
      aria-hidden="true"
    ></div>

    <div class="composer-wrap" :class="{ 'has-attachment-dock': chatStore.hasUploadedAttachments }">
      <ChatComposer @send="handleSend" />
    </div>
  </div>
</template>

<script setup lang="ts">
// 助手面板（D1 拆分第 10 步，todo §8.4）：组合消息列表与输入区，
// 持有滚动容器，并实例化 useAgentChat 完成发送/加载流程。
import { nextTick, ref, watch } from 'vue'
import { useChatStore } from '@/stores/chat'
import { useAgentChat } from '@/composables/useAgentChat'
import MessageList from './MessageList.vue'
import ChatComposer from './ChatComposer.vue'

const chatStore = useChatStore()

const assistantBodyRef = ref<HTMLElement | null>(null)

async function scrollToBottom() {
  await nextTick()
  if (!assistantBodyRef.value) return
  assistantBodyRef.value.scrollTop = assistantBodyRef.value.scrollHeight
}

const { sendMessage, loadHistory, regenerateLastMessage } = useAgentChat({ scrollToBottom })

function handleSend() {
  void sendMessage()
}

function handleRegenerate() {
  void regenerateLastMessage()
}

// 历史被整体替换（加载 / done 重建）时保持滚动到底部
watch(
  () => chatStore.messages.length,
  () => {
    void scrollToBottom()
  },
)

defineExpose({ loadHistory, scrollToBottom })
</script>

<style scoped>
.assistant-panel {
  height: 100%;
  min-height: 0;
  position: relative;
  display: grid;
  grid-template-rows: auto minmax(0, 1fr);
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.014), rgba(255, 255, 255, 0)), var(--column-bg);
  overflow: hidden;
}

.assistant-head {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 18px 0 10px;
  background: var(--column-bg);
}

.assistant-head-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 0 14px 0 18px;
}

.assistant-head-copy {
  flex: 1;
  min-width: 0;
}

.assistant-title-row {
  display: inline-flex;
  align-items: center;
  gap: 10px;
}

.assistant-title {
  font-size: 20px;
  letter-spacing: -0.02em;
}

.assistant-presence {
  width: 7px;
  height: 7px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.72);
  box-shadow: 0 0 0 4px rgba(255, 255, 255, 0.04);
  animation: assistant-presence-pulse 2.6s ease-in-out infinite;
}

.assistant-meta {
  font-size: 14px;
  color: var(--text-secondary);
  margin-top: 4px;
}

.assistant-head-divider {
  width: auto;
  margin: 0 6px;
  height: 1px;
  background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.1), transparent);
}

.assistant-body {
  min-height: 0;
  height: 100%;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 14px 14px 10px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  background: var(--column-bg);
  scroll-behavior: smooth;
  scrollbar-gutter: stable;
  scrollbar-width: thin;
  scrollbar-color: rgba(255, 255, 255, 0.22) transparent;
  overscroll-behavior: contain;
  -webkit-overflow-scrolling: touch;
  touch-action: pan-y;
  position: relative;
  z-index: 1;
}

.assistant-body.has-floating-composer {
  padding-bottom: 234px;
}

.assistant-body.has-floating-composer.has-attachment-dock {
  padding-bottom: 332px;
}

.assistant-body::-webkit-scrollbar {
  width: 8px;
}

.assistant-body::-webkit-scrollbar-track {
  background: transparent;
}

.assistant-body::-webkit-scrollbar-thumb {
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.16);
}

.assistant-body::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.24);
}

.agent-status-line {
  color: var(--text-secondary);
  font-size: 12px;
  position: sticky;
  bottom: 0;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  width: fit-content;
  margin: 4px 0 0;
  padding: 8px 10px 2px 4px;
  color: rgba(255, 255, 255, 0.68);
  background: linear-gradient(
    180deg,
    transparent,
    rgba(11, 11, 11, 0.92) 32%,
    rgba(11, 11, 11, 0.98)
  );
  pointer-events: none;
  z-index: 1;
}

.agent-status-pulse {
  width: 6px;
  height: 6px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.76);
  animation: agent-status-pulse 1.6s ease-in-out infinite;
}

.assistant-composer-underlay {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  height: 248px;
  background: var(--column-bg);
  z-index: 2;
  pointer-events: none;
}

.assistant-composer-underlay.has-attachment-dock {
  height: 346px;
}

.assistant-composer-underlay::before {
  content: '';
  position: absolute;
  left: 0;
  right: 0;
  top: -44px;
  height: 44px;
  background: linear-gradient(
    180deg,
    rgba(4, 4, 5, 0),
    var(--column-bg) 82%,
    var(--column-bg) 100%
  );
}

.composer-wrap {
  position: absolute;
  left: 8px;
  right: 8px;
  bottom: 8px;
  padding: 18px 18px 14px;
  border: 1px solid rgba(255, 255, 255, 0.08) !important;
  border-radius: 28px;
  background: linear-gradient(180deg, #171717, #111111 72%, #0b0b0c 100%);
  display: flex;
  flex-direction: column;
  gap: 8px;
  overflow: visible;
  transition:
    padding-top 280ms cubic-bezier(0.22, 1, 0.36, 1),
    background 180ms ease,
    border-color 180ms ease,
    box-shadow 220ms cubic-bezier(0.22, 1, 0.36, 1);
  box-shadow:
    0 -18px 48px rgba(0, 0, 0, 0.28),
    inset 0 1px 0 rgba(255, 255, 255, 0.03);
  z-index: 3;
  pointer-events: none;
}

.composer-wrap::before {
  display: none;
}

.composer-wrap.has-attachment-dock {
  padding-top: 106px;
}

@keyframes assistant-presence-pulse {
  0%,
  100% {
    opacity: 0.55;
    transform: scale(1);
  }

  50% {
    opacity: 1;
    transform: scale(1.08);
  }
}

@keyframes agent-status-pulse {
  0%,
  100% {
    opacity: 0.25;
    transform: scale(1);
  }

  50% {
    opacity: 1;
    transform: scale(1.2);
  }
}

@media (max-width: 1480px) {
  .assistant-head-top {
    padding-inline: 12px;
  }

  .assistant-body {
    padding-inline: 12px;
  }

  .composer-wrap {
    left: 6px;
    right: 6px;
    bottom: 6px;
    padding: 16px 16px 12px;
  }

  .assistant-body.has-floating-composer {
    padding-bottom: 224px;
  }

  .assistant-body.has-floating-composer.has-attachment-dock {
    padding-bottom: 320px;
  }

  .assistant-composer-underlay {
    height: 238px;
  }

  .assistant-composer-underlay.has-attachment-dock {
    height: 336px;
  }

  .composer-wrap.has-attachment-dock {
    padding-top: 102px;
  }
}

@media (max-width: 1320px) {
  .assistant-title {
    font-size: 18px;
  }

  .assistant-meta {
    font-size: 13px;
  }

  .agent-status-line {
    font-size: 11px;
  }
}
</style>
