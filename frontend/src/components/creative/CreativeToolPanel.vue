<template>
  <div class="creative-tool-panel-layer" :class="{ 'is-active': tool }">
    <Transition name="tool-config" mode="out-in">
      <section
        v-if="tool"
        ref="panelRef"
        :key="tool.id"
        class="creative-tool-config"
        role="dialog"
        :aria-label="`${tool.name}参数面板`"
        @click.stop
      >
        <header class="creative-tool-config-head">
          <div class="creative-tool-config-heading">
            <span class="creative-tool-config-mark" :style="{ color: tool.color }">
              {{ artMark(tool.type) }}
            </span>
            <div>
              <div class="creative-tool-config-eyebrow">{{ tool.badge }}</div>
              <h2>{{ tool.name }}</h2>
              <p>{{ tool.description }}</p>
            </div>
          </div>
          <button
            type="button"
            class="creative-tool-config-close"
            aria-label="关闭参数面板"
            @click="saveAndClose"
          >
            ✕
          </button>
        </header>

        <div class="creative-tool-config-body">
          <div class="creative-tool-config-notice">
            <span aria-hidden="true">✦</span>
            <span>{{ tool.inputHint }} · 配置生成参数</span>
          </div>

          <div class="creative-input-section">
            <div class="creative-input-section-head">
              <span>主要输入</span>
              <small>来自输入节点或上一步结果</small>
            </div>
            <div class="creative-main-input-card">
              <span class="creative-input-port-mark">⇥</span>
              <div>
                <strong>{{ mainInputLabel }}</strong>
                <small>{{ mainInputDetail }} · {{ mainInputHint(tool.type) }}</small>
              </div>
              <span class="creative-input-status">等待输入</span>
            </div>
          </div>

          <div class="creative-input-section">
            <div class="creative-input-section-head">
              <span>补充参考</span>
              <small>可添加图片或文本，不替换主要输入</small>
            </div>
            <div v-if="references.length" class="creative-reference-list">
              <div
                v-for="reference in references"
                :key="reference.id"
                class="creative-reference-item"
              >
                <span class="creative-reference-type">{{
                  reference.type === 'image' ? '▧' : 'Aa'
                }}</span>
                <span class="creative-reference-copy">
                  <strong>{{ reference.name }}</strong>
                  <small>{{ reference.detail ?? '用户补充参考' }}</small>
                </span>
                <button
                  type="button"
                  class="creative-reference-remove"
                  :aria-label="`移除${reference.name}`"
                  @click="removeReference(reference.id)"
                >
                  ×
                </button>
              </div>
            </div>
            <div v-else class="creative-reference-empty">
              还没有补充参考，生成时可只使用主要输入。
            </div>
            <div class="creative-reference-actions">
              <label class="creative-reference-add">
                <span>＋ 图片 / 文件</span>
                <input
                  type="file"
                  accept="image/*,.txt,.md,.pdf,.wav,.mp3"
                  @change="handleFileChange"
                />
              </label>
              <button
                type="button"
                class="creative-reference-add"
                @click="textReferenceOpen = !textReferenceOpen"
              >
                ＋ 文本参考
              </button>
            </div>
            <div v-if="textReferenceOpen" class="creative-text-reference-form">
              <textarea
                v-model="textReference"
                rows="2"
                placeholder="输入风格、限制或画面补充说明"
              ></textarea>
              <button type="button" @click="addTextReference">添加</button>
            </div>
          </div>

          <div class="creative-output-preview">
            <span class="creative-output-port-mark">⇥</span>
            <div>
              <strong>输出接口</strong>
              <small>生成后结果会显示在当前面板</small>
            </div>
          </div>

          <template v-if="tool.type === 'lyrics'">
            <label class="creative-field">
              <span>创作主题</span>
              <textarea
                :value="tool.params.theme"
                rows="3"
                @input="update('theme', $event)"
              ></textarea>
            </label>
            <div class="creative-field-grid">
              <label class="creative-field">
                <span>曲风</span>
                <select :value="tool.params.style" @change="update('style', $event)">
                  <option>流行抒情</option>
                  <option>城市民谣</option>
                  <option>电子流行</option>
                  <option>摇滚叙事</option>
                </select>
              </label>
              <label class="creative-field">
                <span>语言</span>
                <select :value="tool.params.language" @change="update('language', $event)">
                  <option>中文</option>
                  <option>英文</option>
                  <option>中英混合</option>
                </select>
              </label>
            </div>
            <label class="creative-field">
              <span>情绪方向</span>
              <select :value="tool.params.mood" @change="update('mood', $event)">
                <option>温柔、克制</option>
                <option>明亮、轻快</option>
                <option>忧郁、克制</option>
                <option>热烈、昂扬</option>
                <option>孤独、怀旧</option>
              </select>
            </label>
          </template>

          <template v-else-if="tool.type === 'image'">
            <label class="creative-field">
              <span>画面描述</span>
              <textarea
                :value="tool.params.prompt"
                rows="4"
                @input="update('prompt', $event)"
              ></textarea>
            </label>
            <div class="creative-field-grid">
              <label class="creative-field">
                <span>视觉风格</span>
                <select :value="tool.params.style" @change="update('style', $event)">
                  <option>电影概念艺术</option>
                  <option>二次元插画</option>
                  <option>写实摄影</option>
                  <option>复古胶片</option>
                </select>
              </label>
              <label class="creative-field">
                <span>画面比例</span>
                <select :value="tool.params.ratio" @change="update('ratio', $event)">
                  <option>16:9</option>
                  <option>1:1</option>
                  <option>9:16</option>
                  <option>4:3</option>
                </select>
              </label>
            </div>
            <label class="creative-field">
              <span>色彩方向</span>
              <input :value="tool.params.palette" @input="update('palette', $event)" />
            </label>
          </template>

          <template v-else-if="tool.type === 'video'">
            <div class="creative-field-grid">
              <label class="creative-field">
                <span>输入方式</span>
                <select :value="tool.params.source" @change="update('source', $event)">
                  <option>文字描述</option>
                  <option>图片驱动</option>
                  <option>音频驱动</option>
                </select>
              </label>
              <label class="creative-field">
                <span>时长</span>
                <select :value="tool.params.duration" @change="update('duration', $event)">
                  <option>5 秒</option>
                  <option>15 秒</option>
                  <option>30 秒</option>
                  <option>60 秒</option>
                </select>
              </label>
            </div>
            <label class="creative-field">
              <span>镜头描述</span>
              <textarea
                :value="tool.params.prompt"
                rows="4"
                @input="update('prompt', $event)"
              ></textarea>
            </label>
            <label class="creative-field">
              <span>运动方式</span>
              <input :value="tool.params.motion" @input="update('motion', $event)" />
            </label>
          </template>

          <template v-else>
            <label class="creative-field">
              <span>输入音频</span>
              <div class="creative-file-input">
                <span>{{ tool.params.source }}</span>
                <button type="button" @click="updateValue('source', 'demo-audio-input.wav')">
                  选择文件
                </button>
              </div>
            </label>
            <label class="creative-field">
              <span>分析特征</span>
              <select :value="tool.params.feature" @change="update('feature', $event)">
                <option>频段与波形质感</option>
                <option>节奏与动态</option>
                <option>音色与空间感</option>
              </select>
            </label>
            <div class="creative-field-grid">
              <label class="creative-field">
                <span>生成强度</span>
                <select :value="tool.params.intensity" @change="update('intensity', $event)">
                  <option>轻微</option>
                  <option>中等</option>
                  <option>强烈</option>
                </select>
              </label>
              <label class="creative-field">
                <span>节奏处理</span>
                <select :value="tool.params.variation" @change="update('variation', $event)">
                  <option>保留原始节奏</option>
                  <option>轻微变化</option>
                  <option>重新编排</option>
                </select>
              </label>
            </div>
          </template>

          <div
            v-if="tool.type === 'lyrics' && toolRun?.status === 'succeeded'"
            class="creative-generation-result"
          >
            <div class="creative-generation-result-head">
              <span>歌词生成结果</span>
              <span>智谱文本模型</span>
            </div>
            <pre>{{ toolRun.content }}</pre>
          </div>
          <div
            v-else-if="tool.type === 'lyrics' && toolRun && toolRun.status !== 'running'"
            class="creative-generation-error"
          >
            {{ toolRun.error ?? '歌词生成失败，请稍后重试' }}
          </div>
        </div>

        <footer class="creative-tool-config-footer">
          <span>参数会自动保存</span>
          <div class="creative-tool-config-actions">
            <button type="button" class="creative-tool-save secondary" @click="saveAndClose">
              保存参数
            </button>
            <button
              v-if="tool.type === 'lyrics'"
              type="button"
              class="creative-tool-save"
              :disabled="isLyricsGenerating"
              @click="generateLyrics"
            >
              {{ isLyricsGenerating ? '生成中…' : '生成歌词' }}
            </button>
            <button v-else type="button" class="creative-tool-save" @click="saveAndClose">
              确定
            </button>
          </div>
        </footer>
      </section>
    </Transition>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { ElMessage } from '@/utils/toast'
import { useCreativeToolsStore } from '@/stores/creativeTools'
import { useToolRunsStore } from '@/stores/toolRuns'
import { useWorkflowStore, WORKFLOW_INPUT_ID } from '@/stores/workflow'

const emit = defineEmits<{ (event: 'close'): void }>()
const creativeToolsStore = useCreativeToolsStore()
const workflowStore = useWorkflowStore()
const toolRunsStore = useToolRunsStore()
const tool = computed(() => creativeToolsStore.activePanelTool)
const references = computed(() => tool.value?.references ?? [])
const toolRun = computed(() => (tool.value ? (toolRunsStore.records[tool.value.id] ?? null) : null))
const isLyricsGenerating = computed(() => toolRun.value?.status === 'running')
const mainInputSource = computed(() => {
  const nodeId = tool.value
    ? (workflowStore.nodes.find((candidate) => candidate.toolId === tool.value!.id)?.id ?? null)
    : null
  const edge = workflowStore.edges.find((item) => item.target === nodeId)
  if (!edge) return null
  if (edge.source === WORKFLOW_INPUT_ID) return '输入节点'
  return workflowStore.nodes.find((node) => node.id === edge.source)?.name ?? '上一步工具'
})
const mainInputLabel = computed(() => mainInputSource.value ?? '等待连接')
const mainInputDetail = computed(() =>
  mainInputSource.value
    ? '连接建立后，将接收上一步选中的单个生产结果'
    : '请从输入节点或上一步工具的输出插孔建立连接',
)
const panelRef = ref<HTMLElement | null>(null)
const textReferenceOpen = ref(false)
const textReference = ref('')

watch(
  () => tool.value?.id,
  () => {
    textReferenceOpen.value = false
    textReference.value = ''
  },
)

function update(key: string, event: Event) {
  const target = event.target as HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement
  if (tool.value) creativeToolsStore.updateParam(tool.value.id, key, target.value)
}

function updateValue(key: string, value: string) {
  if (tool.value) creativeToolsStore.updateParam(tool.value.id, key, value)
}

function mainInputHint(type: string) {
  return (
    {
      lyrics: '输入节点的主题文字或项目资料',
      image: '上一工具的 Prompt / 歌词或图片结果',
      video: '上一工具的图片、分镜或音频结果',
      audio: '输入节点的音频或上一工具的声音结果',
    }[type] ?? '上一工具的生产结果'
  )
}

function handleFileChange(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file || !tool.value) return
  const type = file.type.startsWith('image/') ? 'image' : 'file'
  creativeToolsStore.addReference(tool.value.id, {
    type,
    name: file.name,
    detail: `${Math.ceil(file.size / 1024)} KB · 本地参考文件`,
  })
  input.value = ''
}

function addTextReference() {
  const value = textReference.value.trim()
  if (!value || !tool.value) return
  creativeToolsStore.addReference(tool.value.id, {
    type: 'text',
    name: value.length > 24 ? `${value.slice(0, 24)}…` : value,
    detail: '用户输入的文本参考',
  })
  textReference.value = ''
  textReferenceOpen.value = false
}

function removeReference(referenceId: string) {
  if (tool.value) creativeToolsStore.removeReference(tool.value.id, referenceId)
}

async function generateLyrics() {
  const currentTool = tool.value
  if (!currentTool || currentTool.type !== 'lyrics' || isLyricsGenerating.value) return

  const theme = currentTool.params.theme?.trim()
  if (!theme) {
    ElMessage.warning('请先填写创作主题')
    return
  }

  toolRunsStore.setRecord(currentTool.id, { status: 'running', content: null, error: null })
  creativeToolsStore.saveTool(currentTool.id)
  try {
    const status = await workflowStore.runCurrentWorkflow()
    const record = toolRunsStore.records[currentTool.id]
    if (status === 'succeeded') {
      ElMessage.success('歌词生成完成')
    } else {
      ElMessage.error(record?.error ?? '歌词生成失败，请稍后重试')
    }
  } catch {
    toolRunsStore.setRecord(currentTool.id, {
      status: 'failed',
      content: null,
      error: '歌词生成请求失败，请稍后重试',
    })
    ElMessage.error('歌词生成请求失败，请稍后重试')
  }
}

function saveAndClose() {
  if (!tool.value) return
  creativeToolsStore.saveTool(tool.value.id)
  textReferenceOpen.value = false
  textReference.value = ''
  creativeToolsStore.closePanel()
  emit('close')
  ElMessage.success('参数已保存')
}

function handleDocumentPointerDown(event: PointerEvent) {
  if (!tool.value) return
  const target = event.target as Node | null
  if (target && panelRef.value?.contains(target)) return
  saveAndClose()
}

onMounted(() => document.addEventListener('pointerdown', handleDocumentPointerDown))

onBeforeUnmount(() => {
  document.removeEventListener('pointerdown', handleDocumentPointerDown)
})

function artMark(type: string) {
  return { lyrics: 'Aa', image: '✦', video: '▶', audio: '∿' }[type] ?? '✦'
}
</script>

<style scoped>
.creative-tool-panel-layer {
  position: absolute;
  inset: 0;
  z-index: 3;
  pointer-events: none;
}

.creative-tool-panel-layer.is-active {
  pointer-events: none;
}

.creative-tool-config {
  position: absolute;
  top: 0;
  left: 18px;
  width: min(430px, calc(100% - 36px));
  height: 100%;
  min-height: 0;
  flex-direction: column;
  pointer-events: auto;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 16px;
  background: #151515;
  overflow: hidden;
}

.creative-tool-config-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding: 22px 18px 17px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.creative-tool-config-heading {
  display: flex;
  min-width: 0;
  align-items: flex-start;
  gap: 12px;
}

.creative-tool-config-mark {
  display: grid;
  flex: 0 0 auto;
  width: 34px;
  height: 34px;
  place-items: center;
  border-radius: 8px;
  filter: grayscale(1);
  font-size: 19px;
}

.creative-tool-config-eyebrow {
  color: #888;
  font-size: 10px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.creative-tool-config h2 {
  margin: 2px 0 3px;
  color: #eeeeee;
  font-size: 18px;
  font-weight: 600;
}

.creative-tool-config p {
  margin: 0;
  color: #7e7e7e;
  font-size: 11px;
  line-height: 1.5;
}

.creative-tool-config-close {
  flex: 0 0 auto;
  width: 27px;
  height: 27px;
  border: 1px solid rgba(255, 255, 255, 0.11) !important;
  border-radius: 6px;
  color: #888 !important;
}

.creative-tool-config-close:hover {
  background: rgba(255, 255, 255, 0.07) !important;
  color: #fff !important;
}

.creative-tool-config-body {
  min-height: 0;
  flex: 1;
  overflow-y: auto;
  padding: 15px 18px;
}

.creative-tool-config-notice {
  display: flex;
  align-items: center;
  gap: 7px;
  margin-bottom: 16px;
  padding: 8px 10px;
  border: 1px solid rgba(255, 255, 255, 0.14);
  border-radius: 7px;
  background: rgba(255, 255, 255, 0.055);
  color: #c4c4c4;
  font-size: 10px;
}

.creative-input-section {
  margin-bottom: 15px;
  padding: 11px;
  border: 1px solid rgba(255, 255, 255, 0.09);
  border-radius: 9px;
  background: rgba(255, 255, 255, 0.025);
}

.creative-input-section-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 9px;
  color: #c8c8c8;
  font-size: 11px;
  font-weight: 600;
}

.creative-input-section-head small,
.creative-main-input-card small,
.creative-output-preview small,
.creative-reference-copy small {
  color: #777b84;
  font-size: 9px;
  font-weight: 400;
  line-height: 1.4;
}

.creative-main-input-card,
.creative-output-preview {
  display: flex;
  align-items: center;
  gap: 9px;
  min-height: 45px;
  padding: 8px 9px;
  border: 1px solid rgba(96, 165, 250, 0.28);
  border-radius: 7px;
  background: rgba(96, 165, 250, 0.07);
}

.creative-main-input-card > div,
.creative-output-preview > div {
  display: flex;
  min-width: 0;
  flex: 1;
  flex-direction: column;
  gap: 2px;
}

.creative-main-input-card strong,
.creative-output-preview strong {
  color: #d7e9ff;
  font-size: 11px;
  font-weight: 600;
}

.creative-input-port-mark,
.creative-output-port-mark {
  color: #72b5ff;
  font-size: 18px;
  line-height: 1;
}

.creative-input-status {
  padding: 3px 5px;
  border-radius: 4px;
  background: rgba(255, 255, 255, 0.08);
  color: #aeb9c8;
  font-size: 8px;
}

.creative-reference-list {
  display: grid;
  gap: 5px;
  margin-bottom: 8px;
}

.creative-reference-item {
  display: flex;
  align-items: center;
  gap: 7px;
  min-width: 0;
  padding: 7px 8px;
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.045);
}

.creative-reference-type {
  display: grid;
  width: 24px;
  height: 24px;
  flex: 0 0 auto;
  place-items: center;
  border-radius: 5px;
  background: rgba(255, 255, 255, 0.08);
  color: #d0d7e0;
  font-size: 10px;
}

.creative-reference-copy {
  display: flex;
  min-width: 0;
  flex: 1;
  flex-direction: column;
  gap: 1px;
}

.creative-reference-copy strong {
  overflow: hidden;
  color: #cfd2d8;
  font-size: 10px;
  font-weight: 500;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.creative-reference-remove {
  width: 21px;
  height: 21px;
  flex: 0 0 auto;
  border-radius: 4px;
  color: #888d97 !important;
  font-size: 15px;
}

.creative-reference-remove:hover {
  background: rgba(255, 255, 255, 0.08) !important;
  color: #fff !important;
}

.creative-reference-empty {
  margin-bottom: 8px;
  color: #777b84;
  font-size: 9px;
  line-height: 1.5;
}

.creative-reference-actions {
  display: flex;
  gap: 6px;
}

.creative-reference-add {
  display: inline-flex;
  align-items: center;
  min-height: 27px;
  padding: 0 8px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 5px;
  background: rgba(255, 255, 255, 0.045);
  color: #aeb2ba;
  cursor: pointer;
  font-size: 9px;
}

.creative-reference-add:hover {
  border-color: rgba(255, 255, 255, 0.24);
  background: rgba(255, 255, 255, 0.08);
  color: #f0f0f0;
}

.creative-reference-add input {
  display: none;
}

.creative-text-reference-form {
  display: flex;
  align-items: flex-end;
  gap: 6px;
  margin-top: 8px;
}

.creative-text-reference-form textarea {
  min-width: 0;
  flex: 1;
  padding: 7px;
  border: 1px solid rgba(255, 255, 255, 0.11);
  border-radius: 5px;
  outline: 0;
  resize: vertical;
  background: rgba(255, 255, 255, 0.035);
  color: #dedede;
  font-size: 10px;
}

.creative-text-reference-form button {
  min-height: 29px;
  padding: 0 8px;
  border-radius: 5px;
  background: rgba(255, 255, 255, 0.1) !important;
  color: #d9d9d9 !important;
  font-size: 9px;
}

.creative-output-preview {
  margin-bottom: 15px;
  border-color: rgba(167, 139, 250, 0.3);
  background: rgba(167, 139, 250, 0.07);
}

.creative-output-preview strong {
  color: #e2d9ff;
}

.creative-output-port-mark {
  color: #b8a2ff;
}

.creative-field-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.creative-field {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 13px;
}

.creative-field > span {
  color: #a2a2a2;
  font-size: 11px;
}

.creative-field input,
.creative-field textarea,
.creative-field select {
  width: 100%;
  border: 1px solid rgba(255, 255, 255, 0.11);
  border-radius: 6px;
  outline: 0;
  background: rgba(255, 255, 255, 0.035);
  color: #e1e1e1;
  font-size: 11px;
  line-height: 1.5;
  transition:
    border-color 180ms ease,
    background-color 180ms ease;
}

.creative-field input,
.creative-field select {
  height: 34px;
  padding: 0 9px;
}

.creative-field textarea {
  min-height: 70px;
  resize: vertical;
  padding: 8px 9px;
}

.creative-field input:focus,
.creative-field textarea:focus,
.creative-field select:focus {
  border-color: rgba(220, 220, 220, 0.7);
  background: rgba(255, 255, 255, 0.055);
}

.creative-file-input {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  min-height: 34px;
  padding: 4px 5px 4px 9px;
  border: 1px solid rgba(255, 255, 255, 0.11);
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.035);
  color: #d2d2d2;
  font-size: 11px;
}

.creative-file-input span {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.creative-file-input button {
  flex: 0 0 auto;
  padding: 4px 7px;
  border-radius: 4px;
  background: rgba(255, 255, 255, 0.08) !important;
  color: #c2c2c2 !important;
  font-size: 10px;
}

.creative-generation-result,
.creative-generation-error {
  margin-top: 14px;
  padding: 12px;
  border: 1px solid rgba(159, 182, 222, 0.2);
  border-radius: 8px;
  background: rgba(159, 182, 222, 0.05);
}

.creative-generation-result-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  color: #cbd8ef;
  font-size: 11px;
}

.creative-generation-result-head span:last-child {
  color: #777f8e;
  font-size: 9px;
}

.creative-generation-result pre {
  max-height: 360px;
  margin: 10px 0 0;
  overflow: auto;
  color: #d8d8d8;
  font: inherit;
  font-size: 11px;
  line-height: 1.75;
  white-space: pre-wrap;
}

.creative-generation-error {
  border-color: rgba(220, 170, 170, 0.22);
  color: #d9aaaa;
  font-size: 11px;
  line-height: 1.6;
}

.creative-tool-config-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 13px 18px 17px;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
}

.creative-tool-config-footer > span {
  color: #777;
  font-size: 10px;
}

.creative-tool-config-actions {
  display: flex;
  align-items: center;
  gap: 7px;
}

.creative-tool-save.secondary {
  background: rgba(255, 255, 255, 0.08) !important;
  color: #cfcfcf !important;
}

.creative-tool-save:disabled {
  cursor: wait;
  opacity: 0.55;
}

.creative-tool-save {
  min-width: 68px;
  padding: 7px 13px;
  border-radius: 6px;
  background: #e6e6e6 !important;
  color: #111 !important;
  font-size: 11px;
}

.creative-tool-save:hover {
  background: #fff !important;
}

.tool-config-enter-active,
.tool-config-leave-active {
  transition:
    transform 300ms cubic-bezier(0.16, 1, 0.3, 1),
    opacity 260ms ease;
}

.tool-config-enter-from,
.tool-config-leave-to {
  opacity: 0;
  transform: translateX(-100%);
}

.tool-config-enter-to,
.tool-config-leave-from {
  opacity: 1;
  transform: translateX(0);
}

@media (max-width: 760px) {
  .creative-tool-config {
    width: min(100%, 320px);
  }
}
</style>
