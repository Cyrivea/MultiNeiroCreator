<template>
  <Transition name="modal-fade">
    <div v-if="open" class="modal-overlay billing-overlay" role="presentation" @click.self="close">
      <section
        class="modal-card billing-card"
        role="dialog"
        aria-modal="true"
        aria-labelledby="billingTitle"
      >
        <div class="modal-head billing-head">
          <div>
            <div id="billingTitle" class="modal-title">计费面板</div>
            <div class="modal-caption">
              查看额度、套餐与用量明细。
              <span class="billing-preview-badge">预输入数据 · 未接后端</span>
            </div>
          </div>
          <button class="modal-close" type="button" aria-label="关闭计费面板" @click="close">
            ✕
          </button>
        </div>

        <div class="billing-body">
          <!-- 额度总览 -->
          <div class="billing-overview">
            <div class="billing-stat-card">
              <div class="billing-stat-label">套餐剩余额度</div>
              <div class="billing-stat-value">
                62.8<span class="billing-stat-unit">积分</span>
              </div>
              <div class="billing-progress" role="presentation">
                <div class="billing-progress-fill" style="width: 62.8%"></div>
              </div>
              <div class="billing-stat-meta">
                创作者 · 标准版 ｜ 已用 37.2 / 100 ｜ 2026-10-15 到期
              </div>
            </div>
            <div class="billing-stat-card">
              <div class="billing-stat-label">预付余额</div>
              <div class="billing-stat-value">
                25.50<span class="billing-stat-unit">积分</span>
              </div>
              <div class="billing-stat-note">
                套餐额度耗尽后自动扣减，余额不足时调用将被拒绝
              </div>
            </div>
          </div>

          <!-- 本月用量汇总 -->
          <section class="billing-section" aria-labelledby="billingSummaryTitle">
            <div id="billingSummaryTitle" class="billing-section-head">本月用量</div>
            <div class="billing-summary-grid">
              <div
                v-for="item in monthlyUsage"
                :key="item.label"
                class="billing-summary-item"
              >
                <div class="billing-summary-label">{{ item.label }}</div>
                <div class="billing-summary-value">{{ item.credits }} 积分</div>
                <div class="billing-summary-meta">{{ item.count }} 次调用</div>
              </div>
            </div>
          </section>

          <!-- 用量明细 -->
          <section class="billing-section" aria-labelledby="billingUsageTitle">
            <div id="billingUsageTitle" class="billing-section-head">用量明细</div>
            <ul class="billing-usage-list">
              <li
                v-for="record in usageRecords"
                :key="record.id"
                class="billing-usage-item"
                :class="{ failed: record.status === 'failed' }"
              >
                <div class="billing-usage-main">
                  <span class="billing-usage-capability">{{ itemLabel(record.capability) }}</span>
                  <span class="billing-usage-model">{{ record.model }}</span>
                </div>
                <div class="billing-usage-side">
                  <span class="billing-usage-credits">{{ record.creditsText }}</span>
                  <span class="billing-usage-time">{{ record.time }}</span>
                </div>
              </li>
            </ul>
          </section>

          <!-- 消费设置 -->
          <section class="billing-section" aria-labelledby="billingSettingsTitle">
            <div id="billingSettingsTitle" class="billing-section-head">消费设置</div>
            <div class="billing-setting-row">
              <div class="billing-setting-copy">
                <div class="billing-setting-name">超额自动扣费</div>
                <div class="billing-setting-desc">
                  套餐额度用尽后从预付余额扣减；关闭后超额调用将被直接拒绝
                </div>
              </div>
              <button
                class="billing-toggle"
                type="button"
                role="switch"
                aria-checked="true"
                :class="{ on: overchargeEnabled }"
                @click="overchargeEnabled = !overchargeEnabled"
              >
                <span class="billing-toggle-knob" aria-hidden="true"></span>
              </button>
            </div>
            <div class="billing-setting-row">
              <div class="billing-setting-copy">
                <div class="billing-setting-name">月度消费上限</div>
                <div class="billing-setting-desc">达到上限后暂停所有付费调用，次月自动恢复</div>
              </div>
              <div class="billing-limit-value">未设置</div>
            </div>
          </section>

          <!-- 操作 -->
          <div class="billing-actions">
            <button class="billing-action-button primary" type="button">升级套餐</button>
            <button class="billing-action-button" type="button">充值预付余额</button>
            <button class="billing-action-button ghost" type="button">导出账单</button>
          </div>
        </div>
      </section>
    </div>
  </Transition>
</template>

<script setup lang="ts">
/**
 * 计费面板（I8 第一版：预输入 UI）。
 * ⚠️ 当前为设计评审版——所有数据为内置 mock，未接 /billing 接口；
 * 数据结构对齐后端 billing_service 的真实形状（balance/monthly usage/ledger），
 * 接线时只替换数据源，不改版式。
 */
import { ref } from 'vue'

defineProps<{ open: boolean }>()
const emit = defineEmits<{ (e: 'close'): void }>()

const overchargeEnabled = ref(true)

const monthlyUsage = [
  { label: '助手对话', credits: '12.1', count: 128 },
  { label: '歌词生成', credits: '3.3', count: 11 },
  { label: '图像生成', credits: '4.0', count: 2 },
  { label: '文档索引', credits: '0.8', count: 6 },
]

const usageRecords = [
  {
    id: 5,
    capability: 'image.generate',
    model: 'Kwai-Kolors',
    creditsText: '- 2.00 积分',
    time: '今天 09:04',
    status: 'succeeded',
  },
  {
    id: 4,
    capability: 'lyrics.generate',
    model: 'glm-4-flash',
    creditsText: '- 0.30 积分',
    time: '今天 09:04',
    status: 'succeeded',
  },
  {
    id: 3,
    capability: 'assistant.chat',
    model: 'glm-4-flash',
    creditsText: '- 0.42 积分',
    time: '昨天 21:33',
    status: 'succeeded',
  },
  {
    id: 2,
    capability: 'assistant.chat',
    model: 'glm-4-flash',
    creditsText: '- 0.18 积分',
    time: '昨天 21:31',
    status: 'succeeded',
  },
  {
    id: 1,
    capability: 'document.index',
    model: 'BAAI/bge-m3',
    creditsText: '- 0.08 积分',
    time: '09-28 20:05',
    status: 'succeeded',
  },
]

function itemLabel(capability: string): string {
  const labels: Record<string, string> = {
    'assistant.chat': '助手对话',
    'lyrics.generate': '歌词生成',
    'image.generate': '图像生成',
    'document.index': '文档索引',
  }
  return labels[capability] ?? capability
}

function close() {
  emit('close')
}
</script>

<style scoped>
.billing-overlay {
  display: flex;
  align-items: center;
  justify-content: center;
}

.billing-card {
  width: min(640px, calc(100vw - 48px));
  max-height: min(82vh, 760px);
  display: flex;
  flex-direction: column;
}

.billing-head {
  padding-bottom: 14px;
}

.billing-preview-badge {
  display: inline-block;
  margin-left: 8px;
  padding: 1px 8px;
  border: 1px solid rgba(96, 165, 250, 0.4);
  border-radius: 999px;
  color: #60a5fa;
  font-size: 11px;
  letter-spacing: 0.02em;
  vertical-align: 1px;
}

.billing-body {
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 18px;
}

/* ---- 额度总览 ---- */
.billing-overview {
  display: grid;
  grid-template-columns: 1.4fr 1fr;
  gap: 12px;
}

.billing-stat-card {
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 16px;
  padding: 16px 18px;
  background: rgba(255, 255, 255, 0.02);
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.billing-stat-label {
  font-size: 12px;
  color: #6f6f76;
}

.billing-stat-value {
  font-size: 30px;
  font-weight: 700;
  color: var(--text-primary, #f4f4f4);
  line-height: 1.1;
}

.billing-stat-unit {
  margin-left: 6px;
  font-size: 13px;
  font-weight: 400;
  color: #6f6f76;
}

.billing-progress {
  height: 6px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.06);
  overflow: hidden;
}

.billing-progress-fill {
  height: 100%;
  border-radius: 999px;
  background: #60a5fa;
}

.billing-stat-meta {
  font-size: 12px;
  color: #6f6f76;
}

.billing-stat-note {
  font-size: 12px;
  color: #6f6f76;
  line-height: 1.5;
  margin-top: auto;
}

/* ---- 区段 ---- */
.billing-section {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.billing-section-head {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-secondary, #c9cdd6);
  letter-spacing: 0.01em;
}

/* ---- 本月用量 ---- */
.billing-summary-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 10px;
}

.billing-summary-item {
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 12px;
  padding: 10px 12px;
  background: rgba(255, 255, 255, 0.015);
}

.billing-summary-label {
  font-size: 11px;
  color: #6f6f76;
}

.billing-summary-value {
  margin-top: 4px;
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary, #f4f4f4);
}

.billing-summary-meta {
  margin-top: 2px;
  font-size: 11px;
  color: #6f6f76;
}

/* ---- 用量明细 ---- */
.billing-usage-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 12px;
  overflow: hidden;
}

.billing-usage-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 9px 14px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}

.billing-usage-item:last-child {
  border-bottom: none;
}

.billing-usage-item.failed .billing-usage-credits {
  color: #f87171;
}

.billing-usage-main {
  display: flex;
  align-items: baseline;
  gap: 10px;
  min-width: 0;
}

.billing-usage-capability {
  font-size: 13px;
  color: var(--text-primary, #f4f4f4);
}

.billing-usage-model {
  font-size: 11px;
  color: #6f6f76;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.billing-usage-side {
  display: flex;
  align-items: baseline;
  gap: 12px;
  flex-shrink: 0;
}

.billing-usage-credits {
  font-size: 12px;
  color: var(--text-secondary, #c9cdd6);
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
}

.billing-usage-time {
  font-size: 11px;
  color: #6f6f76;
  min-width: 76px;
  text-align: right;
}

/* ---- 消费设置 ---- */
.billing-setting-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 10px 14px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 12px;
}

.billing-setting-row + .billing-setting-row {
  margin-top: 8px;
}

.billing-setting-name {
  font-size: 13px;
  color: var(--text-primary, #f4f4f4);
}

.billing-setting-desc {
  margin-top: 2px;
  font-size: 11px;
  color: #6f6f76;
  line-height: 1.5;
}

.billing-limit-value {
  font-size: 12px;
  color: #6f6f76;
  flex-shrink: 0;
}

.billing-toggle {
  width: 36px;
  height: 20px;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.14);
  background: rgba(255, 255, 255, 0.04);
  position: relative;
  cursor: pointer;
  flex-shrink: 0;
  transition: background 160ms ease, border-color 160ms ease;
  padding: 0;
}

.billing-toggle.on {
  background: #60a5fa;
  border-color: #60a5fa;
}

.billing-toggle-knob {
  position: absolute;
  top: 2px;
  left: 2px;
  width: 14px;
  height: 14px;
  border-radius: 999px;
  background: #f4f4f4;
  transition: transform 160ms ease;
}

.billing-toggle.on .billing-toggle-knob {
  transform: translateX(16px);
}

/* ---- 操作 ---- */
.billing-actions {
  display: flex;
  gap: 10px;
  padding-top: 2px;
}

.billing-action-button {
  flex: 1;
  padding: 9px 12px;
  border-radius: 10px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  background: rgba(255, 255, 255, 0.02);
  color: var(--text-secondary, #c9cdd6);
  font-size: 13px;
  cursor: pointer;
  transition: background 140ms ease, color 140ms ease;
}

.billing-action-button:hover {
  background: var(--hover-bg, rgba(255, 255, 255, 0.05));
  color: var(--text-primary, #f4f4f4);
}

.billing-action-button.primary {
  background: #60a5fa;
  border-color: #60a5fa;
  color: #0a0a0c;
  font-weight: 600;
}

.billing-action-button.primary:hover {
  background: #7cb2fb;
}

.billing-action-button.ghost {
  flex: 0 0 auto;
}

@media (max-width: 560px) {
  .billing-overview,
  .billing-summary-grid {
    grid-template-columns: 1fr 1fr;
  }

  .billing-actions {
    flex-wrap: wrap;
  }
}
</style>
